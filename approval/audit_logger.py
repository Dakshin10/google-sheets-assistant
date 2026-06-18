import os
import json
import time
from config import LOGS_DIR

AUDIT_LOG_FILE = LOGS_DIR / "audit_log.jsonl"


def log_audit_event(action: str, request_id: str, sql: str, actor: str, outcome: str, error: str = None):
    """
    Appends an audit log entry detailing manual database overrides or query approvals.
    """
    os.makedirs(os.path.dirname(AUDIT_LOG_FILE), exist_ok=True)
    
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,         # e.g., "APPROVE_SQL", "REJECT_SQL"
        "request_id": request_id,
        "sql": sql,
        "actor": actor,           # e.g., "ADMIN"
        "outcome": outcome,       # e.g., "EXECUTED", "REJECTED", "FAILED"
        "error": error
    }
    
    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"Failed writing audit log: {e}")
