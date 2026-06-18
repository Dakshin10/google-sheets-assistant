import json
import hashlib
import re
import asyncio
from datetime import datetime, timezone
import pandas as pd
import gspread

from db.database import db_gateway
from services.google_auth import get_google_client
from monitoring.logger import logger
from schema.type_inferrer import infer_sql_type
from schema.schema_builder import build_schema, build_create_sql, build_insert_sql
from sync.schema_diff import diff_schemas
from sync.migration_engine import generate_migration_ddl
from exceptions.sync_exceptions import StagingLoadError, MigrationError

db_client = db_gateway

def parse_spreadsheet_id(url: str) -> str:
    """Extracts the spreadsheet ID from a Google Sheets URL."""
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Google Sheets URL format.")

def sanitize_identifier(name: str) -> str:
    """Sanitizes spreadsheet and worksheet titles to form valid, collision-free SQLite table/column names."""
    # Replace spaces and hyphens with underscores
    s = name.replace(" ", "_").replace("-", "_")
    # Remove any character that is not alphanumeric or underscore
    s = re.sub(r'[^a-zA-Z0-9_]', '', s)
    # Lowercase
    s = s.lower()
    # Ensure it doesn't start with a digit
    if s and s[0].isdigit():
        s = "t_" + s
    # Collapse multiple underscores
    s = re.sub(r'_+', '_', s)
    return s.strip("_")

def compute_row_hash(row_dict: dict) -> str:
    """Computes a stable SHA-256 hash of a row's values."""
    # Sort keys to ensure stable ordering
    serialized = json.dumps(row_dict, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

def detect_primary_key(df: pd.DataFrame) -> str:
    """
    Heuristic to find a unique identifier column in the DataFrame.
    Looks for case-insensitive matches for 'id', 'uuid', 'key', 'email'.
    Verifies that the column contains unique, non-null values.
    """
    potential_keys = ['id', 'uuid', 'key', 'email']
    for col in df.columns:
        if col.lower() in potential_keys:
            # Check uniqueness and non-emptiness
            non_null = df[col].dropna()
            if len(non_null) == len(df) and df[col].nunique() == len(df):
                return col
    return None

async def init_sheet_table(table_name: str, df: pd.DataFrame):
    """Creates the sheet table if it doesn't exist yet, with metadata columns."""
    schema = build_schema(df)
    columns_sql = []
    for col in schema:
        safe_name = col["name"].replace(" ", "_")
        columns_sql.append(f'"{safe_name}" {col["type"]}')
    
    # Add metadata columns
    columns_sql.append("_row_index INTEGER")
    columns_sql.append("_row_hash TEXT")
    columns_sql.append("is_deleted INTEGER DEFAULT 0")
    columns_sql.append("deleted_at TEXT")

    column_sql_str = ",\n    ".join(columns_sql)
    create_sql = f"""CREATE TABLE IF NOT EXISTS "{table_name}" (
        {column_sql_str}
    );"""
    
    logger.info(f"Creating table {table_name} if not exists...")
    await db_client.execute_query(create_sql)

async def handle_schema_evolution(sheet_id: int, table_name: str, df: pd.DataFrame, worksheet_title: str):
    """
    Compares database table schema with DataFrame schema.
    Applies ALTER TABLE for new columns, and handles renames/type changes.
    """
    # 1. Fetch D1 schema for the table
    pragma_res = await db_client.execute_query(f'PRAGMA table_info("{table_name}")')
    if not pragma_res.get("success"):
        raise RuntimeError(f"Failed to fetch schema info for table {table_name}")
    
    d1_columns = pragma_res.get("result", [])
    if not d1_columns:
        # Table doesn't exist, initialize it
        await init_sheet_table(table_name, df)
        return

    # Check for missing metadata columns in the existing table
    existing_column_names = {col["name"].lower() for col in d1_columns}
    missing_metadata = []
    if "_row_index" not in existing_column_names:
        missing_metadata.append("_row_index INTEGER")
    if "_row_hash" not in existing_column_names:
        missing_metadata.append("_row_hash TEXT")
    if "is_deleted" not in existing_column_names:
        missing_metadata.append("is_deleted INTEGER DEFAULT 0")
    if "deleted_at" not in existing_column_names:
        missing_metadata.append("deleted_at TEXT")

    if missing_metadata:
        logger.info(f"Table {table_name} is missing metadata columns. Adding them...")
        alter_queries = []
        for col_def in missing_metadata:
            alter_queries.append(f'ALTER TABLE "{table_name}" ADD COLUMN {col_def}')
        await db_client.execute_batch(alter_queries)
        
        # Re-fetch D1 schema after alteration
        pragma_res = await db_client.execute_query(f'PRAGMA table_info("{table_name}")')
        if not pragma_res.get("success"):
            raise RuntimeError(f"Failed to fetch schema info for table {table_name} after adding metadata columns")
        d1_columns = pragma_res.get("result", [])

    # Map D1 columns, ignoring our metadata columns
    d1_schema = []
    metadata_cols = {"_row_index", "_row_hash", "is_deleted", "deleted_at"}
    for col in d1_columns:
        name = col["name"]
        if name not in metadata_cols:
            d1_schema.append({"name": name, "type": col["type"]})

    new_schema = build_schema(df)
    
    # Calculate schema diff
    diff = diff_schemas(d1_schema, new_schema)
    
    # Check if anything changed
    has_changes = any(diff.values())
    if not has_changes:
        return

    # Handle Renames: Migrate immediately
    if diff.get("renamed"):
        for old_name, new_name, col_type in diff["renamed"]:
            old_name_clean = old_name.replace(" ", "_")
            new_name_clean = new_name.replace(" ", "_")
            details = json.dumps({"old_name": old_name_clean, "new_name": new_name_clean, "type": col_type})
            await db_client.execute_query(
                """
                INSERT INTO pending_schema_changes (sheet_id, worksheet_title, change_type, details, status)
                VALUES (?, ?, 'RENAME', ?, 'APPROVED')
                """,
                [sheet_id, worksheet_title, details]
            )
            sql = f'ALTER TABLE "{table_name}" RENAME COLUMN "{old_name_clean}" TO "{new_name_clean}";'
            logger.info(f"Executing auto column rename: {sql}")
            res = await db_client.execute_query(sql)
            if not res.get("success"):
                raise MigrationError(f"Failed to execute column rename: {res.get('error')}")

    # Handle Type Changes: Migrate immediately
    if diff.get("type_changed"):
        for change in diff["type_changed"]:
            column = change["name"].replace(" ", "_")
            new_type = change["new_type"]
            details = json.dumps({"column": column, "old_type": change["old_type"], "new_type": new_type})
            await db_client.execute_query(
                """
                INSERT INTO pending_schema_changes (sheet_id, worksheet_title, change_type, details, status)
                VALUES (?, ?, 'TYPE_CHANGE', ?, 'APPROVED')
                """,
                [sheet_id, worksheet_title, details]
            )
            # Rebuild table transactionally
            pragma_res = await db_client.execute_query(f'PRAGMA table_info("{table_name}")')
            if not pragma_res.get("success"):
                raise RuntimeError(f"Failed to fetch D1 schema for table {table_name}")
            d1_columns = pragma_res.get("result", [])
            
            staging_cols = []
            select_cols = []
            for col in d1_columns:
                name = col["name"]
                ctype = col["type"]
                if name == column:
                    staging_cols.append(f'"{name}" {new_type}')
                    select_cols.append(f'CAST("{name}" AS {new_type}) AS "{name}"')
                else:
                    staging_cols.append(f'"{name}" {ctype}')
                    select_cols.append(f'"{name}"')

            staging_table = f"{table_name}_staging"
            queries = [
                f'DROP TABLE IF EXISTS "{staging_table}";',
                f'CREATE TABLE "{staging_table}" ({", ".join(staging_cols)});',
                f'INSERT INTO "{staging_table}" SELECT {", ".join(select_cols)} FROM "{table_name}";',
                f'DROP TABLE "{table_name}";',
                f'ALTER TABLE "{staging_table}" RENAME TO "{table_name}";'
            ]
            logger.info(f"Executing auto type change rebuild for {table_name}...")
            res_batch = await db_client.execute_batch(queries)
            for res in res_batch:
                if not res.get("success"):
                    raise MigrationError(f"Failed to execute table type change: {res.get('error')}")

    # Handle Added Columns: Apply ALTER TABLE statements
    if diff.get("added"):
        ddl_statements = generate_migration_ddl(table_name, diff)
        logger.info(f"Applying schema alterations for {table_name}: {ddl_statements}")
        await db_client.execute_batch(ddl_statements)

async def sync_worksheet(sheet_id: int, spreadsheet_id: str, ws: gspread.Worksheet, spreadsheet_name: str):
    """Synchronizes a single worksheet incrementally, handling row inserts, updates, and soft deletes."""
    title = ws.title
    table_name = f"{sanitize_identifier(spreadsheet_name)}_{sanitize_identifier(title)}"
    
    # 1. Fetch worksheet records
    records = ws.get_all_records()
    if not records:
        logger.info(f"Worksheet {title} is empty. Skipping sync.")
        return
        
    df = pd.DataFrame(records)
    
    # 2. Handle schema migration if needed
    await handle_schema_evolution(sheet_id, table_name, df, title)

    # 3. Load previous snapshot from D1
    snapshot_sql = """
        SELECT row_index, row_hash, row_data FROM sheet_snapshots 
        WHERE spreadsheet_id = ? AND worksheet_title = ?
    """
    snap_res = await db_client.execute_query(snapshot_sql, [spreadsheet_id, title])
    if not snap_res.get("success"):
        raise RuntimeError("Failed to fetch previous sheet snapshots.")
        
    prev_snapshots = {row["row_index"]: row for row in snap_res.get("result", [])}

    # 4. Prepare current row representations and hashes
    current_rows = []
    for idx, row in df.iterrows():
        row_index = idx + 1 # 1-based index
        row_dict = row.to_dict()
        row_hash = compute_row_hash(row_dict)
        current_rows.append({
            "row_index": row_index,
            "row_hash": row_hash,
            "row_dict": row_dict
        })

    # 5. Determine primary key (if any)
    pk_col = detect_primary_key(df)
    
    inserts = []
    updates = []
    deletes = [] # list of row indexes to delete
    
    if pk_col:
        # Match using Primary Key column value
        pk_safe = pk_col.replace(" ", "_")
        prev_pk_map = {}
        for row_idx, snap in prev_snapshots.items():
            snap_data = json.loads(snap["row_data"])
            pk_val = snap_data.get(pk_col)
            if pk_val is not None:
                prev_pk_map[pk_val] = snap
                
        curr_pk_map = {}
        for r in current_rows:
            pk_val = r["row_dict"].get(pk_col)
            if pk_val is not None:
                curr_pk_map[pk_val] = r

        # Calculate inserts and updates
        for pk_val, r in curr_pk_map.items():
            if pk_val not in prev_pk_map:
                inserts.append(r)
            else:
                snap = prev_pk_map[pk_val]
                if r["row_hash"] != snap["row_hash"]:
                    # Row index might have changed, update row index as well
                    r["old_row_index"] = snap["row_index"]
                    updates.append(r)

        # Calculate deletes
        for pk_val, snap in prev_pk_map.items():
            if pk_val not in curr_pk_map:
                deletes.append(snap["row_index"])
    else:
        # No PK detected: fallback to row_index-based matching
        max_len = max(len(current_rows), len(prev_snapshots))
        for i in range(1, max_len + 1):
            curr_exists = i <= len(current_rows)
            prev_exists = i in prev_snapshots
            
            if curr_exists and not prev_exists:
                inserts.append(current_rows[i - 1])
            elif curr_exists and prev_exists:
                curr_r = current_rows[i - 1]
                prev_s = prev_snapshots[i]
                if curr_r["row_hash"] != prev_s["row_hash"]:
                    curr_r["old_row_index"] = i
                    updates.append(curr_r)
            elif not curr_exists and prev_exists:
                deletes.append(i)

    # 6. Apply database changes transactionally / sequentially
    db_queries = []
    snapshot_queries = []
    
    columns = [f'"{col.replace(" ", "_")}"' for col in df.columns]
    columns_str = ", ".join(columns)
    
    # A. Inserts
    for r in inserts:
        row_dict = r["row_dict"]
        row_index = r["row_index"]
        row_hash = r["row_hash"]
        
        row_vals = []
        for val in row_dict.values():
            if isinstance(val, str):
                escaped = val.replace("'", "''")
                row_vals.append(f"'{escaped}'")
            elif val is None or (hasattr(val, 'isna') and val.isna()) or str(val) == 'nan' or str(val) == 'None':
                row_vals.append("NULL")
            else:
                row_vals.append(str(val))
                
        row_vals.append(str(row_index))
        row_vals.append(f"'{row_hash}'")
        row_vals.append("0") # is_deleted
        row_vals.append("NULL") # deleted_at
        
        val_str = ", ".join(row_vals)
        db_queries.append(f"""
            INSERT INTO "{table_name}" ({columns_str}, _row_index, _row_hash, is_deleted, deleted_at)
            VALUES ({val_str});
        """)
        
        snapshot_queries.append((
            """
            INSERT OR REPLACE INTO sheet_snapshots (spreadsheet_id, worksheet_title, row_index, row_hash, row_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            [spreadsheet_id, title, row_index, row_hash, json.dumps(row_dict)]
        ))

    # B. Updates
    for r in updates:
        row_dict = r["row_dict"]
        row_index = r["row_index"]
        old_row_index = r.get("old_row_index", row_index)
        row_hash = r["row_hash"]
        
        set_clauses = []
        for k, val in row_dict.items():
            safe_k = k.replace(" ", "_")
            if isinstance(val, str):
                escaped = val.replace("'", "''")
                set_clauses.append(f'"{safe_k}" = \'{escaped}\'')
            elif val is None or (hasattr(val, 'isna') and val.isna()) or str(val) == 'nan' or str(val) == 'None':
                set_clauses.append(f'"{safe_k}" = NULL')
            else:
                set_clauses.append(f'"{safe_k}" = {val}')
                
        set_clauses.append(f"_row_index = {row_index}")
        set_clauses.append(f"_row_hash = '{row_hash}'")
        set_clauses.append("is_deleted = 0")
        set_clauses.append("deleted_at = NULL")
        
        set_str = ", ".join(set_clauses)
        
        # Match either by index or pk (if pk matches)
        if pk_col:
            pk_val = row_dict[pk_col]
            pk_safe = pk_col.replace(" ", "_")
            escaped_pk = str(pk_val).replace("'", "''") if isinstance(pk_val, str) else str(pk_val)
            where_clause = f'"{pk_safe}" = \'{escaped_pk}\'' if isinstance(pk_val, str) else f'"{pk_safe}" = {pk_val}'
        else:
            where_clause = f"_row_index = {old_row_index}"
            
        db_queries.append(f'UPDATE "{table_name}" SET {set_str} WHERE {where_clause};')
        
        snapshot_queries.append((
            """
            INSERT OR REPLACE INTO sheet_snapshots (spreadsheet_id, worksheet_title, row_index, row_hash, row_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            [spreadsheet_id, title, row_index, row_hash, json.dumps(row_dict)]
        ))

    # C. Deletes (Soft Deletes)
    for row_idx in deletes:
        if pk_col:
            snap = prev_snapshots[row_idx]
            snap_data = json.loads(snap["row_data"])
            pk_val = snap_data.get(pk_col)
            pk_safe = pk_col.replace(" ", "_")
            escaped_pk = str(pk_val).replace("'", "''") if isinstance(pk_val, str) else str(pk_val)
            where_clause = f'"{pk_safe}" = \'{escaped_pk}\'' if isinstance(pk_val, str) else f'"{pk_safe}" = {pk_val}'
        else:
            where_clause = f"_row_index = {row_idx}"
            
        now_iso = datetime.now(timezone.utc).isoformat()
        db_queries.append(f'UPDATE "{table_name}" SET is_deleted = 1, deleted_at = \'{now_iso}\' WHERE {where_clause};')
        
        # Remove snapshot record since the row is gone from the spreadsheet
        snapshot_queries.append((
            "DELETE FROM sheet_snapshots WHERE spreadsheet_id = ? AND worksheet_title = ? AND row_index = ?",
            [spreadsheet_id, title, row_idx]
        ))

    # Run queries in a batch/sequential block
    if db_queries:
        logger.info(f"Applying {len(db_queries)} row-level database changes for {table_name}...")
        await db_client.execute_batch(db_queries)
        
    if snapshot_queries:
        logger.info(f"Updating {len(snapshot_queries)} snapshot logs...")
        await db_client.execute_batch(snapshot_queries)

    return len(inserts), len(updates), len(deletes)

async def sync_sheet_by_id(sheet_id: int):
    """Fetches details for sheet_id, executes gspread download and invokes sync engine."""
    # 1. Fetch connection details
    sheet_res = await db_client.execute_query(
        "SELECT id, spreadsheet_id, spreadsheet_name, owner_email, sync_enabled FROM connected_sheets WHERE id = ?",
        [sheet_id]
    )
    if not sheet_res.get("result"):
        logger.warning(f"Connection ID {sheet_id} not found. Skipping sync.")
        return

    sheet = sheet_res["result"][0]
    spreadsheet_id = sheet["spreadsheet_id"]
    
    t_start = datetime.now(timezone.utc)
    
    # Mark status as SYNCING
    await db_client.execute_query(
        "UPDATE connected_sheets SET sync_status = 'SYNCING', last_sync_at = ? WHERE id = ?",
        [t_start.isoformat(), sheet_id]
    )

    client = None
    tot_added, tot_updated, tot_deleted = 0, 0, 0
    try:
        # 2. Get google client
        client = get_google_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        spreadsheet_name = spreadsheet.title
        
        # Sync each worksheet
        for ws in spreadsheet.worksheets():
            added, updated, deleted = await sync_worksheet(sheet_id, spreadsheet_id, ws, spreadsheet_name)
            tot_added += added
            tot_updated += updated
            tot_deleted += deleted
            
        t_finish = datetime.now(timezone.utc)
        
        # 3. Log success
        await db_client.execute_query(
            """
            UPDATE connected_sheets 
            SET sync_status = 'ACTIVE', last_successful_sync = ?, last_sync_at = ?
            WHERE id = ?
            """,
            [t_finish.isoformat(), t_finish.isoformat(), sheet_id]
        )
        
        await db_client.execute_query(
            """
            INSERT INTO sync_logs (sheet_id, sync_started, sync_finished, rows_added, rows_updated, rows_deleted, status)
            VALUES (?, ?, ?, ?, ?, ?, 'SUCCESS')
            """,
            [sheet_id, t_start.isoformat(), t_finish.isoformat(), tot_added, tot_updated, tot_deleted]
        )
        logger.info(f"Synchronized sheet {spreadsheet_id} successfully: +{tot_added} ~{tot_updated} -{tot_deleted}")
        
    except gspread.exceptions.APIError as e:
        err_msg = str(e)
        logger.error(f"Google API Error syncing sheet {sheet_id}: {err_msg}")
        t_finish = datetime.now(timezone.utc)
        status = 'AUTH_ERROR' if 'auth' in err_msg.lower() or 'permission' in err_msg.lower() else 'NETWORK_ERROR'
        
        await db_client.execute_query(
            "UPDATE connected_sheets SET sync_status = ?, last_sync_at = ? WHERE id = ?",
            [status, t_finish.isoformat(), sheet_id]
        )
        await db_client.execute_query(
            """
            INSERT INTO sync_logs (sheet_id, sync_started, sync_finished, status, error_message)
            VALUES (?, ?, ?, 'FAILED', ?)
            """,
            [sheet_id, t_start.isoformat(), t_finish.isoformat(), f"Google API Error: {err_msg}"]
        )
    except MigrationError as e:
        err_msg = str(e)
        logger.error(f"Schema Evolution Pause for sheet {sheet_id}: {err_msg}")
        t_finish = datetime.now(timezone.utc)
        await db_client.execute_query(
            "UPDATE connected_sheets SET sync_status = 'SCHEMA_SUSPENDED', last_sync_at = ? WHERE id = ?",
            [t_finish.isoformat(), sheet_id]
        )
        await db_client.execute_query(
            """
            INSERT INTO sync_logs (sheet_id, sync_started, sync_finished, status, error_message)
            VALUES (?, ?, ?, 'FAILED', ?)
            """,
            [sheet_id, t_start.isoformat(), t_finish.isoformat(), f"Schema Error: {err_msg}"]
        )
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Unexpected Error syncing sheet {sheet_id}: {err_msg}")
        t_finish = datetime.now(timezone.utc)
        await db_client.execute_query(
            "UPDATE connected_sheets SET sync_status = 'FAILED', last_sync_at = ? WHERE id = ?",
            [t_finish.isoformat(), sheet_id]
        )
        await db_client.execute_query(
            """
            INSERT INTO sync_logs (sheet_id, sync_started, sync_finished, status, error_message)
            VALUES (?, ?, ?, 'FAILED', ?)
            """,
            [sheet_id, t_start.isoformat(), t_finish.isoformat(), err_msg]
        )

async def apply_approved_rename(sheet_id: int, pending_change_id: int):
    """Performs the approved rename migration on D1 and marks status APPROVED."""
    # 1. Fetch pending rename details
    change_res = await db_client.execute_query(
        "SELECT id, worksheet_title, details FROM pending_schema_changes WHERE id = ? AND status = 'PENDING'",
        [pending_change_id]
    )
    if not change_res.get("result"):
        raise ValueError(f"Pending rename change {pending_change_id} not found or already processed.")
        
    change = change_res["result"][0]
    worksheet_title = change["worksheet_title"]
    details = json.loads(change["details"])
    old_name = details["old_name"].replace(" ", "_")
    new_name = details["new_name"].replace(" ", "_")
    
    sheet_res = await db_client.execute_query(
        "SELECT spreadsheet_name FROM connected_sheets WHERE id = ?", [sheet_id]
    )
    sp_name = sheet_res["result"][0]["spreadsheet_name"] if sheet_res.get("result") else ""
    table_name = f"{sanitize_identifier(sp_name)}_{sanitize_identifier(worksheet_title)}"

    # 2. Alter table on database
    sql = f'ALTER TABLE "{table_name}" RENAME COLUMN "{old_name}" TO "{new_name}";'
    logger.info(f"Executing approved rename migration: {sql}")
    await db_client.execute_query(sql)

    # 3. Update pending change status
    await db_client.execute_query(
        "UPDATE pending_schema_changes SET status = 'APPROVED' WHERE id = ?",
        [pending_change_id]
    )
    
    # 4. Attempt to resume sync
    await resume_sheet_sync(sheet_id)

async def apply_approved_type_change(sheet_id: int, pending_change_id: int):
    """Rebuilds table transactionally to perform a column data type change in SQLite."""
    # 1. Fetch pending type change details
    change_res = await db_client.execute_query(
        "SELECT id, worksheet_title, details FROM pending_schema_changes WHERE id = ? AND status = 'PENDING'",
        [pending_change_id]
    )
    if not change_res.get("result"):
        raise ValueError(f"Pending type change {pending_change_id} not found or already processed.")
        
    change = change_res["result"][0]
    worksheet_title = change["worksheet_title"]
    details = json.loads(change["details"])
    column = details["column"].replace(" ", "_")
    new_type = details["new_type"]
    
    sheet_res = await db_client.execute_query(
        "SELECT spreadsheet_name FROM connected_sheets WHERE id = ?", [sheet_id]
    )
    sp_name = sheet_res["result"][0]["spreadsheet_name"] if sheet_res.get("result") else ""
    table_name = f"{sanitize_identifier(sp_name)}_{sanitize_identifier(worksheet_title)}"

    # 2. Rebuild the table (staging load and transactional swap strategy)
    # Fetch D1 columns to build the staging table schema
    pragma_res = await db_client.execute_query(f'PRAGMA table_info("{table_name}")')
    if not pragma_res.get("success"):
        raise RuntimeError(f"Failed to fetch D1 schema for table {table_name}")
        
    d1_columns = pragma_res.get("result", [])
    
    # Build columns list for staging table
    staging_cols = []
    select_cols = []
    for col in d1_columns:
        name = col["name"]
        ctype = col["type"]
        if name == column:
            staging_cols.append(f'"{name}" {new_type}')
            select_cols.append(f'CAST("{name}" AS {new_type}) AS "{name}"')
        else:
            staging_cols.append(f'"{name}" {ctype}')
            select_cols.append(f'"{name}"')

    staging_table = f"{table_name}_staging"
    
    # Execute transactional migration
    queries = [
        f'DROP TABLE IF EXISTS "{staging_table}";',
        f'CREATE TABLE "{staging_table}" ({", ".join(staging_cols)});',
        f'INSERT INTO "{staging_table}" SELECT {", ".join(select_cols)} FROM "{table_name}";',
        f'DROP TABLE "{table_name}";',
        f'ALTER TABLE "{staging_table}" RENAME TO "{table_name}";'
    ]
    
    logger.info(f"Executing approved type change rebuild for {table_name}...")
    await db_client.execute_batch(queries)

    # 3. Update pending change status
    await db_client.execute_query(
        "UPDATE pending_schema_changes SET status = 'APPROVED' WHERE id = ?",
        [pending_change_id]
    )
    
    # 4. Resume sync
    await resume_sheet_sync(sheet_id)

async def resume_sheet_sync(sheet_id: int):
    """Checks if there are any remaining PENDING schema changes, if not, sets sync_status to ACTIVE."""
    check_sql = "SELECT id FROM pending_schema_changes WHERE sheet_id = ? AND status = 'PENDING'"
    check_res = await db_client.execute_query(check_sql, [sheet_id])
    if not check_res.get("result"):
        await db_client.execute_query(
            "UPDATE connected_sheets SET sync_status = 'ACTIVE' WHERE id = ?",
            [sheet_id]
        )
