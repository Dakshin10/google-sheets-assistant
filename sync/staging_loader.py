import pandas as pd
from db.database import db_gateway
from schema.schema_builder import build_schema, build_create_sql, build_insert_sql
from exceptions.sync_exceptions import StagingLoadError
from monitoring.logger import logger
from monitoring.metrics import metrics

db_client = db_gateway


async def load_staging_and_swap(df: pd.DataFrame, table_name: str) -> None:
    """
    Creates a staging table, inserts data in batches, verifies row counts,
    and performs a transactional swap to production with rollback on failure.
    """
    staging_table = f"{table_name}_staging"
    schema = build_schema(df)
    create_staging_sql = build_create_sql(schema, staging_table)
    
    # 1. Clean staging environment
    logger.info(f"Cleaning existing staging table: {staging_table}")
    await db_client.execute_query(f'DROP TABLE IF EXISTS "{staging_table}"')

    # 2. Create staging table
    logger.info(f"Creating staging table: {staging_table}")
    create_res = await db_client.execute_query(create_staging_sql)
    if not create_res.get("success"):
        raise StagingLoadError(f"Staging table creation failed: {create_res.get('error')}")

    try:
        # 3. Load data in batches of 500
        BATCH_SIZE = 500
        rows_inserted = 0
        queries = []
        
        for i in range(0, len(df), BATCH_SIZE):
            chunk = df.iloc[i : i + BATCH_SIZE]
            insert_sql = build_insert_sql(chunk, staging_table)
            queries.append(insert_sql)
            rows_inserted += len(chunk)
            
        logger.info(f"Executing batch loading of {rows_inserted} rows into {staging_table}")
        batch_outcomes = await db_client.execute_batch(queries)
        for idx, outcome in enumerate(batch_outcomes):
            if not outcome.get("success"):
                raise StagingLoadError(f"Batch insert {idx} failed: {outcome.get('error')}")

        # 4. Verify staging table row count
        count_res = await db_client.execute_query(f'SELECT COUNT(*) as cnt FROM "{staging_table}"')
        if not count_res.get("success") or not count_res.get("result"):
            raise StagingLoadError("Failed to verify staging table row count.")
            
        staging_count = count_res["result"][0]["cnt"]
        if staging_count != len(df):
            raise StagingLoadError(
                f"Row count mismatch. Expected: {len(df)}, Got in Staging: {staging_count}"
            )

        # 5. Swap staging table with production table transactionally
        logger.info(f"Performing transactional swap: {staging_table} -> {table_name}")
        swap_queries = [
            f'DROP TABLE IF EXISTS "{table_name}"',
            f'ALTER TABLE "{staging_table}" RENAME TO "{table_name}"'
        ]
        
        # Cloudflare D1 query REST API executes arrays of queries sequentially in one transaction block
        swap_outcomes = await db_client.execute_batch(swap_queries)
        for outcome in swap_outcomes:
            if not outcome.get("success"):
                raise StagingLoadError(f"Table swap transactional DDL failed: {outcome.get('error')}")
                
        logger.info(f"Transactional swap successful for table {table_name}")

    except Exception as e:
        logger.error(f"Failed loading staging table. Initiating rollback for staging: {staging_table}")
        # Clean up staging table on failure
        await db_client.execute_query(f'DROP TABLE IF EXISTS "{staging_table}"')
        raise StagingLoadError(f"Data sync failed: {str(e)}")
