"""
Background scheduler that runs inside the FastAPI lifespan.
Uses APScheduler AsyncIOScheduler to register recurring interval jobs for active sheets.
"""
import asyncio
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError

from db.database import db_gateway
from services.sync_engine import sync_sheet_by_id
from monitoring.logger import logger
from services.websocket_manager import ws_manager

scheduler = AsyncIOScheduler()

# Active sync task handles — prevents concurrent syncs of the same sheet
_running_syncs: set = set()


async def _run_sync_task(sheet_id: int):
    """Wrapper that removes sheet_id from _running_syncs when done and broadcasts WebSocket events."""
    if sheet_id in _running_syncs:
        logger.warning(f"Sync for sheet {sheet_id} already in progress. Skipping scheduled run.")
        return
        
    _running_syncs.add(sheet_id)
    
    try:
        # Broadcast sync start
        await ws_manager.broadcast("sync_status", {
            "sheet_id": sheet_id,
            "status": "SYNCING",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        await sync_sheet_by_id(sheet_id)
        
        # Broadcast sync complete or updated status
        # Note: sync_sheet_by_id updates database status. We fetch the updated sheet status and broadcast it.
        status_res = await db_gateway.execute_query(
            "SELECT sync_status, last_sync_at, last_successful_sync FROM connected_sheets WHERE id = ?",
            [sheet_id]
        )
        if status_res.get("success") and status_res.get("result"):
            sheet_info = status_res["result"][0]
            await ws_manager.broadcast("sync_status_change", {
                "sheet_id": sheet_id,
                "status": sheet_info["sync_status"],
                "last_sync_at": sheet_info["last_sync_at"],
                "last_successful_sync": sheet_info["last_successful_sync"]
            })
            
    except Exception as e:
        logger.error(f"Unhandled error in scheduler sync task for sheet {sheet_id}: {e}")
    finally:
        _running_syncs.discard(sheet_id)


def add_sheet_job(sheet_id: int, freq_minutes: int):
    """Registers a recurring sync job for a sheet ID with a specific frequency."""
    job_id = f"sync_{sheet_id}"
    try:
        remove_sheet_job(sheet_id)
    except Exception:
        pass
        
    scheduler.add_job(
        _run_sync_task,
        "interval",
        minutes=freq_minutes,
        id=job_id,
        args=[sheet_id],
        replace_existing=True
    )
    logger.info(f"📅 Registered sync job '{job_id}' to run every {freq_minutes} minutes.")


def remove_sheet_job(sheet_id: int):
    """Removes a registered sync job for a sheet ID."""
    job_id = f"sync_{sheet_id}"
    try:
        scheduler.remove_job(job_id)
        logger.info(f"📅 Removed sync job '{job_id}' from scheduler.")
    except JobLookupError:
        logger.debug(f"Sync job '{job_id}' was not found in scheduler.")


def update_sheet_job(sheet_id: int, freq_minutes: int):
    """Reschedules an existing sync job with a new frequency."""
    add_sheet_job(sheet_id, freq_minutes)


def trigger_immediate_sync(sheet_id: int):
    """Triggers an out-of-band sync task instantly in the background."""
    logger.info(f"📅 Forcing immediate sync task for sheet {sheet_id} in background.")
    asyncio.create_task(_run_sync_task(sheet_id))


async def start_scheduler():
    """Initializes and starts the scheduler on FastAPI startup."""
    if scheduler.running:
        return
        
    logger.info("📅 Initializing APScheduler and loading active sync jobs...")
    
    try:
        res = await db_gateway.execute_query(
            """
            SELECT id, sync_frequency_minutes FROM connected_sheets
            WHERE sync_enabled = 1
              AND sync_status NOT IN ('SCHEMA_SUSPENDED')
            """
        )
        rows = res.get("result", []) if res.get("success") else []
        for row in rows:
            add_sheet_job(row["id"], row["sync_frequency_minutes"])
            
        scheduler.start()
        logger.info("📅 Background APScheduler started successfully.")
    except Exception as e:
        logger.error(f"📅 Failed to start APScheduler: {e}")


async def shutdown_scheduler():
    """Shuts down the scheduler on FastAPI shutdown."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("📅 APScheduler stopped.")
