import json
import os
import time
from pathlib import Path
from config import DATA_DIR

QUEUE_FILE = DATA_DIR / "approval_queue.json"


class ApprovalQueue:
    """Manages the lifecycle queue of query requests needing admin human approvals."""
    def __init__(self):
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
        if not os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, "w") as f:
                json.dump([], f)

    def _load(self) -> list:
        self._ensure_file()
        try:
            with open(QUEUE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, data: list):
        with open(QUEUE_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def add_request(self, user: str, sql: str) -> str:
        """Add a pending SQL request to the queue and return request_id."""
        queue = self._load()
        request_id = f"REQ_{int(time.time() * 1000)}"
        queue.append({
            "request_id": request_id,
            "user": user,
            "generated_sql": sql,
            "status": "PENDING",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "approved_by": None,
            "approved_at": None
        })
        self._save(queue)
        return request_id

    def get_pending(self) -> list:
        """Fetch all PENDING approval entries."""
        return [r for r in self._load() if r["status"] == "PENDING"]

    def update_status(self, request_id: str, status: str, admin: str = "ADMIN") -> dict:
        """Update request status (APPROVED, REJECTED, EXECUTED, FAILED)."""
        queue = self._load()
        for r in queue:
            if r["request_id"] == request_id:
                r["status"] = status
                r["approved_by"] = admin
                r["approved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self._save(queue)
                return r
        return None


approval_queue = ApprovalQueue()
