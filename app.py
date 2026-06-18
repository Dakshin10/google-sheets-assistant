import json
import time
import asyncio
import os
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config import GROQ_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE
from db.database import db_gateway, init_db
from services.scheduler import (
    start_scheduler,
    shutdown_scheduler,
    add_sheet_job,
    remove_sheet_job,
    trigger_immediate_sync,
)
from services.sync_engine import (
    parse_spreadsheet_id,
    sync_sheet_by_id,
    sanitize_identifier,
)
from services.websocket_manager import ws_manager
from validation.sql_validator import validate_query_statically, ensure_schema_cache_loaded
from cache.schema_cache import schema_cache
from cache.query_cache import query_cache
from cache.cache_manager import invalidate_all_caches
from retrieval.prompt_builder import compose_system_prompt
from services.llm import llm
from services.sheets_client import get_spreadsheet_data
from exceptions.llm_exceptions import LLMOutputError
from monitoring.logger import logger
from monitoring.metrics import metrics

# ─── Internal-only tables the LLM should never see ───────────────────────────
INTERNAL_TABLES = frozenset({
    "connected_sheets", "sheet_snapshots", "sync_logs",
    "pending_schema_changes", "_cf_kv", "sqlite_sequence",
    "query_approvals", "audit_logs"
})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables, warm schema cache, launch scheduler. Shutdown: stop scheduler."""
    # 1. Ensure metadata tables exist in local SQLite and remote D1
    try:
        init_db()
        await db_gateway.d1_client.initialize_tables()
        logger.info("Metadata tables initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize metadata tables: {e}")

    # 2. Warm the schema cache
    try:
        await schema_cache.refresh()
        logger.info("Schema cache loaded successfully at startup.")
    except Exception as e:
        logger.warning(
            "Could not load schema cache on startup — verify D1 credentials. Details: " + str(e)
        )

    # 3. Launch background scheduler
    await start_scheduler()
    logger.info("Background scheduler started.")

    yield

    # Shutdown: stop scheduler gracefully
    await shutdown_scheduler()
    logger.info("Background scheduler stopped.")


app = FastAPI(title="Google Sheets & D1 SQL Assistant API", lifespan=lifespan)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic Validation Models ────────────────────────────────────────────────

class ConnectionRequest(BaseModel):
    url: str
    sync_frequency_minutes: int = Field(default=5, ge=1, le=60)
    owner_email: Optional[str] = Field(default="unknown")


class QueryRequest(BaseModel):
    question: str
    sheet_id: Optional[int] = None


# ─── Pydantic Structured SQL Response ────────────────────────────────────────

class SQLResponse(BaseModel):
    sql: str = Field(description="Valid SQLite SELECT statement.")
    explanation: str = Field(description="Natural language explanation.", default="")


structured_llm = llm.with_structured_output(SQLResponse)

SYSTEM_INSTRUCTION = """You are a SQLite query assistant.
Convert user requests into valid SQLite queries matching the schema.
Always wrap table and column names in double quotes (e.g. "Table Name", "Column Name") to prevent syntax errors with spaces or special characters.
Only add WHERE is_deleted = 0 (or is_deleted IS NULL OR is_deleted = 0) to filter out soft-deleted rows if the table schema contains an "is_deleted" column.

Schema:
{schema}"""

PROMPT_TEMPLATE = "Convert: {question}\nSQL:"


# ─── SQL Generation Pipeline ──────────────────────────────────────────────────

async def generate_sql_pipeline(question: str, sheet_id: Optional[int] = None) -> SQLResponse:
    t0 = time.perf_counter()

    t_schema = time.perf_counter()
    if sheet_id:
        # Fetch spreadsheet_id and spreadsheet_name
        sheet_res = await db_gateway.execute_query(
            "SELECT spreadsheet_id, spreadsheet_name FROM connected_sheets WHERE id = ?", [sheet_id]
        )
        sheet_tables = []
        if sheet_res.get("result"):
            sp_id = sheet_res["result"][0]["spreadsheet_id"]
            sp_name = sheet_res["result"][0]["spreadsheet_name"]
            snap_res = await db_gateway.execute_query(
                "SELECT DISTINCT worksheet_title FROM sheet_snapshots WHERE spreadsheet_id = ?", [sp_id]
            )
            if snap_res.get("result"):
                sheet_tables = [
                    f"{sanitize_identifier(sp_name)}_{sanitize_identifier(r['worksheet_title'])}"
                    for r in snap_res["result"]
                ]
        
        # Build schema context only for the selected sheet's tables
        from retrieval.prompt_builder import build_compressed_schema_context
        schema_context = build_compressed_schema_context(sheet_tables)
        relevant_tables = sheet_tables
    else:
        schema_context, relevant_tables = compose_system_prompt(question)
        
    schema_ms = (time.perf_counter() - t_schema) * 1000

    if not schema_context:
        return SQLResponse(
            sql="",
            explanation="No tables loaded yet. Connect a Google Sheet first."
        )

    prompt_input = [
        ("system", SYSTEM_INSTRUCTION.format(schema=schema_context)),
        ("human", PROMPT_TEMPLATE.format(question=question))
    ]

    t_llm = time.perf_counter()
    attempts = 2
    for attempt in range(attempts):
        try:
            response = await structured_llm.ainvoke(prompt_input)

            t_val = time.perf_counter()
            valid, err = await validate_query_statically(response.sql)
            val_ms = (time.perf_counter() - t_val) * 1000

            if not valid:
                raise LLMOutputError(f"AST validation failure: {err}")

            llm_ms = (time.perf_counter() - t_llm) * 1000
            total_ms = (time.perf_counter() - t0) * 1000
            logger.info(json.dumps({
                "stage": "generate_sql_pipeline",
                "schema_retrieval_ms": round(schema_ms, 1),
                "llm_ms": round(llm_ms, 1),
                "validation_ms": round(val_ms, 1),
                "total_pipeline_ms": round(total_ms, 1),
                "relevant_tables": relevant_tables,
                "attempt": attempt + 1
            }))
            return response

        except Exception as e:
            if attempt == attempts - 1:
                logger.error(f"SQL generation failed on final attempt: {e}")
                raise LLMOutputError(f"SQL generation failed: {e}")
            prompt_input.append(
                ("system", f"Previous attempt failed: {str(e)}. Correct and retry.")
            )

    raise LLMOutputError("SQL generation pipeline exhausted all attempts.")


# ─── FastAPI REST Endpoints ───────────────────────────────────────────────────

# 1. WebSocket Gateway
@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Wait for client messages (keep-alive)
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        ws_manager.disconnect(websocket)


# 2. Connections APIs
@app.get("/api/connections")
async def get_connections():
    res = await db_gateway.execute_query(
        """
        SELECT id, spreadsheet_name, spreadsheet_id, owner_email,
               sync_enabled, sync_frequency_minutes,
               last_successful_sync, last_sync_at, sync_status
        FROM connected_sheets ORDER BY id
        """
    )
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))
    return res.get("result", [])


@app.post("/api/connections")
async def connect_sheet(req: ConnectionRequest):
    url = req.url
    freq_minutes = req.sync_frequency_minutes
    owner_email = req.owner_email.strip() or "unknown"

    if not url or "docs.google.com/spreadsheets" not in url:
        raise HTTPException(status_code=400, detail="⚠️ Enter a valid Google Sheets URL.")

    try:
        spreadsheet_id = parse_spreadsheet_id(url)

        # Check duplicate
        dup = await db_gateway.execute_query(
            "SELECT id FROM connected_sheets WHERE spreadsheet_id = ?",
            [spreadsheet_id]
        )
        if dup.get("result"):
            raise HTTPException(status_code=400, detail=f"⚠️ Sheet `{spreadsheet_id}` is already connected.")

        # Fetch sheet metadata
        data = get_spreadsheet_data(url)
        spreadsheet_name = data["spreadsheet_name"]

        # Insert registration
        await db_gateway.execute_query(
            """
            INSERT INTO connected_sheets
              (spreadsheet_id, spreadsheet_name, owner_email, sync_frequency_minutes, sync_status)
            VALUES (?, ?, ?, ?, 'PENDING')
            """,
            [spreadsheet_id, spreadsheet_name, owner_email, int(freq_minutes)]
        )
        
        # Retrieve newly created ID
        sheet_res = await db_gateway.execute_query(
            "SELECT id FROM connected_sheets WHERE spreadsheet_id = ?", [spreadsheet_id]
        )
        sheet_id = sheet_res["result"][0]["id"]
        
        # Schedule the recurring job and trigger immediate first run
        add_sheet_job(sheet_id, freq_minutes)
        trigger_immediate_sync(sheet_id)

        await schema_cache.refresh()
        await ws_manager.broadcast("connection_change", {"action": "CONNECT", "sheet_id": sheet_id})

        return {
            "status": "SUCCESS",
            "message": f"✅ Connected **{spreadsheet_name}** — initial sync started in background.",
            "sheet_id": sheet_id
        }

    except Exception as e:
        logger.exception("connect_sheet error")
        raise HTTPException(status_code=500, detail=f"❌ Error connecting sheet: {str(e)}")


@app.post("/api/connections/{sheet_id}/pause")
async def pause_sheet_endpoint(sheet_id: int):
    try:
        await db_gateway.execute_query(
            "UPDATE connected_sheets SET sync_enabled = 0, sync_status = 'PAUSED' WHERE id = ?",
            [sheet_id]
        )
        remove_sheet_job(sheet_id)
        await ws_manager.broadcast("connection_change", {"action": "PAUSE", "sheet_id": sheet_id})
        return {"status": "SUCCESS", "message": f"⏸️ Sync paused for sheet ID {sheet_id}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/connections/{sheet_id}/resume")
async def resume_sheet_endpoint(sheet_id: int):
    try:
        # Retrieve frequency
        sheet_res = await db_gateway.execute_query(
            "SELECT sync_frequency_minutes FROM connected_sheets WHERE id = ?", [sheet_id]
        )
        if not sheet_res.get("result"):
            raise HTTPException(status_code=404, detail="Sheet connection not found.")
        freq = sheet_res["result"][0]["sync_frequency_minutes"]

        await db_gateway.execute_query(
            "UPDATE connected_sheets SET sync_enabled = 1, sync_status = 'ACTIVE' WHERE id = ?",
            [sheet_id]
        )
        add_sheet_job(sheet_id, freq)
        trigger_immediate_sync(sheet_id)
        await ws_manager.broadcast("connection_change", {"action": "RESUME", "sheet_id": sheet_id})
        return {"status": "SUCCESS", "message": f"▶️ Sync resumed for sheet ID {sheet_id}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/connections/{sheet_id}/sync")
async def force_sync_sheet_endpoint(sheet_id: int):
    try:
        trigger_immediate_sync(sheet_id)
        return {"status": "SUCCESS", "message": f"🔄 Immediate sync triggered for sheet ID {sheet_id}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/connections/{sheet_id}")
async def disconnect_sheet_endpoint(sheet_id: int, delete_data: bool = False):
    try:
        # Fetch spreadsheet metadata before deletion
        sheet_info = await db_gateway.execute_query(
            "SELECT spreadsheet_id, spreadsheet_name FROM connected_sheets WHERE id = ?",
            [sheet_id]
        )
        worksheet_titles = []
        sp_name = ""
        if sheet_info.get("result"):
            sp_id = sheet_info["result"][0]["spreadsheet_id"]
            sp_name = sheet_info["result"][0]["spreadsheet_name"]
            snap_res = await db_gateway.execute_query(
                "SELECT DISTINCT worksheet_title FROM sheet_snapshots WHERE spreadsheet_id = ?",
                [sp_id]
            )
            if snap_res.get("success"):
                worksheet_titles = [r["worksheet_title"] for r in snap_res.get("result", [])]

        # Remove registration (cascades to sync_logs and pending_schema_changes in foreign keys)
        remove_sheet_job(sheet_id)
        await db_gateway.execute_query("DELETE FROM connected_sheets WHERE id = ?", [sheet_id])
        await db_gateway.execute_query(
            "DELETE FROM sheet_snapshots WHERE spreadsheet_id NOT IN (SELECT spreadsheet_id FROM connected_sheets)"
        )

        dropped_tables = []
        if delete_data and worksheet_titles and sp_name:
            for title in worksheet_titles:
                table_name = f"{sanitize_identifier(sp_name)}_{sanitize_identifier(title)}"
                await db_gateway.execute_query(f'DROP TABLE IF EXISTS "{table_name}"')
                dropped_tables.append(table_name)

        await schema_cache.refresh()
        await invalidate_all_caches()
        await ws_manager.broadcast("connection_change", {"action": "DISCONNECT", "sheet_id": sheet_id})

        return {
            "status": "SUCCESS",
            "message": f"🔌 Disconnected sheet ID {sheet_id}.",
            "dropped_tables": dropped_tables
        }

    except Exception as e:
        logger.exception("disconnect_sheet error")
        raise HTTPException(status_code=500, detail=str(e))


# 3. Schema Approvals APIs (Deprecated / Auto-applied)


# Admin: Cleanup orphan data tables (tables belonging to disconnected sheets)
@app.post("/api/admin/cleanup-orphan-tables")
async def cleanup_orphan_tables_endpoint():
    """Drops data tables in D1 whose parent spreadsheet is no longer in connected_sheets."""
    try:
        # 1. Get all currently connected sheets
        sheets_res = await db_gateway.execute_query(
            "SELECT spreadsheet_id, spreadsheet_name FROM connected_sheets"
        )
        connected_sheets = sheets_res.get("result", [])

        # 2. Build set of valid table names from snapshots
        valid_tables: set = set()
        for s in connected_sheets:
            snap_res = await db_gateway.execute_query(
                "SELECT DISTINCT worksheet_title FROM sheet_snapshots WHERE spreadsheet_id = ?",
                [s["spreadsheet_id"]]
            )
            for snap in snap_res.get("result", []):
                tname = f"{sanitize_identifier(s['spreadsheet_name'])}_{sanitize_identifier(snap['worksheet_title'])}"
                valid_tables.add(tname)

        # 3. Get all actual user-created tables
        all_res = await db_gateway.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        all_tables = [r["name"] for r in all_res.get("result", [])]

        # 4. Identify and drop orphans
        dropped = []
        for table in all_tables:
            if table in INTERNAL_TABLES or table.lower() in INTERNAL_TABLES:
                continue
            if table not in valid_tables:
                await db_gateway.execute_query(f'DROP TABLE IF EXISTS "{table}"')
                dropped.append(table)
                logger.info(f"Dropped orphan table: {table}")

        # 5. Clean orphan snapshots
        await db_gateway.execute_query(
            "DELETE FROM sheet_snapshots WHERE spreadsheet_id NOT IN (SELECT spreadsheet_id FROM connected_sheets)"
        )

        # 6. Refresh schema cache
        await schema_cache.refresh()
        await invalidate_all_caches()

        return {
            "status": "SUCCESS",
            "dropped_tables": dropped,
            "message": f"Dropped {len(dropped)} orphan table(s)."
        }
    except Exception as e:
        logger.exception("cleanup_orphan_tables error")
        raise HTTPException(status_code=500, detail=str(e))


# 4. Query Database APIs
@app.post("/api/query")
async def process_user_query(req: QueryRequest):
    question = req.question
    sheet_id = req.sheet_id
    t_total = time.perf_counter()

    try:
        # Layer 1: Question cache scoped by sheet_id
        cache_key = f"{sheet_id or ''}:{question}"
        cached = query_cache.get_by_question(cache_key)
        if cached:
            total_ms = (time.perf_counter() - t_total) * 1000
            logger.info(json.dumps({"stage": "process_user_query", "cache_hit": "question", "total_ms": round(total_ms, 1)}))
            return {
                "sql": cached["sql"],
                "explanation": "(Cached result — no LLM call needed)",
                "status": "SUCCESS",
                "columns": cached["columns"],
                "rows": cached["result"],
                "duration_ms": round(total_ms, 1),
                "cache_hit": True
            }

        # Layer 2: LLM generation scoped by sheet_id
        response = await generate_sql_pipeline(question, sheet_id)
        sql = response.sql
        explanation = response.explanation

        if not sql:
            return {
                "sql": "",
                "explanation": explanation,
                "status": "SUCCESS",
                "columns": [],
                "rows": [],
                "duration_ms": round((time.perf_counter() - t_total) * 1000, 1),
                "cache_hit": False
            }

        is_write = not sql.strip().upper().startswith(("SELECT", "PRAGMA", "WITH"))

        if not is_write:
            # Layer 3: SQL-level cache (only read queries)
            cached_res = query_cache.get(sql)
            if cached_res:
                query_cache.set_by_question(cache_key, sql, cached_res)
                total_ms = (time.perf_counter() - t_total) * 1000
                logger.info(json.dumps({"stage": "process_user_query", "cache_hit": "sql", "total_ms": round(total_ms, 1)}))
                return {
                    "sql": sql,
                    "explanation": explanation,
                    "status": "SUCCESS",
                    "columns": cached_res["columns"],
                    "rows": cached_res["result"],
                    "duration_ms": round(total_ms, 1),
                    "cache_hit": True
                }

        # Layer 4: Execute against database immediately
        t_db = time.perf_counter()
        res = await db_gateway.execute_query(sql)
        db_ms = (time.perf_counter() - t_db) * 1000

        total_ms = (time.perf_counter() - t_total) * 1000
        logger.info(json.dumps({
            "stage": "process_user_query",
            "db_ms": round(db_ms, 1),
            "total_ms": round(total_ms, 1),
            "rows_returned": len(res.get("result", []))
        }))

        if res.get("success"):
            if is_write:
                await invalidate_all_caches()
            else:
                query_cache.set(sql, res)
                query_cache.set_by_question(cache_key, sql, res)

            return {
                "sql": sql,
                "explanation": explanation,
                "status": "SUCCESS",
                "columns": res.get("columns", []),
                "rows": res.get("result", []),
                "duration_ms": round(total_ms, 1),
                "cache_hit": False
            }
        else:
            return {
                "sql": sql,
                "explanation": explanation,
                "status": "ERROR",
                "error": res.get("error"),
                "columns": [],
                "rows": [],
                "duration_ms": round(total_ms, 1),
                "cache_hit": False
            }

    except Exception as e:
        logger.exception("Query pipeline error")
        raise HTTPException(status_code=500, detail=str(e))


# 5. Database Explorer APIs
@app.get("/api/explorer/tables")
async def get_explorer_tables():
    await ensure_schema_cache_loaded()
    raw = schema_cache.get_raw_schema()
    # Filter out internal tables (case-insensitive)
    tables = [t for t in raw.keys() if t.lower() not in {x.lower() for x in INTERNAL_TABLES}]
    return sorted(tables)


@app.get("/api/explorer/tables/{table_name}")
async def explorer_table_contents(table_name: str):
    if table_name in INTERNAL_TABLES:
        raise HTTPException(status_code=400, detail="Cannot browse internal metadata tables.")
    
    # Check if table contains is_deleted column dynamically
    pragma_res = await db_gateway.execute_query(f'PRAGMA table_info("{table_name}")')
    has_deleted_col = False
    if pragma_res.get("success"):
        cols = pragma_res.get("result", [])
        has_deleted_col = any(c.get("name", "").lower() == "is_deleted" for c in cols)

    if has_deleted_col:
        sql = f'SELECT * FROM "{table_name}" WHERE is_deleted = 0 OR is_deleted IS NULL LIMIT 500'
    else:
        sql = f'SELECT * FROM "{table_name}" LIMIT 500'

    res = await db_gateway.execute_query(sql)
    if res.get("success"):
        return {
            "columns": res.get("columns", []),
            "rows": res.get("result", [])
        }
    raise HTTPException(status_code=500, detail=res.get("error"))


# 6. Audit Logs API
@app.get("/api/logs")
async def get_sync_logs_endpoint(sheet_id: Optional[int] = None):
    try:
        # Always JOIN with connected_sheets to get spreadsheet_name
        if sheet_id:
            sql = """
                SELECT l.id, l.sheet_id, c.spreadsheet_name, l.sync_started, l.sync_finished,
                       l.rows_added, l.rows_updated, l.rows_deleted, l.status, l.error_message
                FROM sync_logs l
                LEFT JOIN connected_sheets c ON c.id = l.sheet_id
                WHERE l.sheet_id = ? ORDER BY l.id DESC LIMIT 50
            """
            res = await db_gateway.execute_query(sql, [sheet_id])
        else:
            sql = """
                SELECT l.id, l.sheet_id, c.spreadsheet_name, l.sync_started, l.sync_finished,
                       l.rows_added, l.rows_updated, l.rows_deleted, l.status, l.error_message
                FROM sync_logs l
                LEFT JOIN connected_sheets c ON c.id = l.sheet_id
                ORDER BY l.id DESC LIMIT 100
            """
            res = await db_gateway.execute_query(sql)

        if not res.get("success"):
            raise HTTPException(status_code=500, detail=res.get("error"))
        return res.get("result", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 7. Schema Cache Refresh API
@app.post("/api/schema/refresh")
async def refresh_schema_cache():
    """Triggers a manual schema cache refresh - call after connecting or syncing sheets."""
    try:
        await schema_cache.refresh()
        await invalidate_all_caches()
        return {"status": "SUCCESS", "message": "Schema cache refreshed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve React static assets in production if they are built
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/{catchall:path}")
    async def serve_frontend(catchall: str):
        # Fallback to index.html for SPA routing (exclude api calls)
        if catchall.startswith("api"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "API is running. Frontend static assets index.html is missing."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)