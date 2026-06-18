from approval.approval_queue import approval_queue
from approval.audit_logger import log_audit_event
from db.database import db_gateway

db_client = db_gateway


async def request_query_approval(user: str, sql: str) -> str:
    """Create a new query approval request."""
    return approval_queue.add_request(user, sql)


async def approve_and_execute_request(request_id: str, admin: str = "ADMIN") -> dict:
    """Approve a query, execute it in D1 database, and write audit trail."""
    pending_list = approval_queue.get_pending()
    req = None
    for r in pending_list:
        if r["request_id"] == request_id:
            req = r
            break
            
    if not req:
        raise ValueError(f"Pending request with ID {request_id} not found.")

    sql = req["generated_sql"]
    # Update status in queue
    approval_queue.update_status(request_id, "APPROVED", admin)
    
    # Execute D1 query
    res = await db_client.execute_query(sql)
    if res.get("success"):
        approval_queue.update_status(request_id, "EXECUTED", admin)
        log_audit_event("APPROVE_SQL", request_id, sql, admin, "EXECUTED")
        return {
            "success": True,
            "result": res.get("result"),
            "columns": res.get("columns"),
            "message": "Query approved and executed successfully."
        }
    else:
        err = res.get("error")
        approval_queue.update_status(request_id, "FAILED", admin)
        log_audit_event("APPROVE_SQL", request_id, sql, admin, "FAILED", error=err)
        return {
            "success": False,
            "error": err,
            "message": "Query execution failed after approval."
        }


async def reject_request(request_id: str, admin: str = "ADMIN") -> dict:
    """Reject a query, preventing execution, and log event."""
    pending_list = approval_queue.get_pending()
    req = None
    for r in pending_list:
        if r["request_id"] == request_id:
            req = r
            break
            
    if not req:
        raise ValueError(f"Pending request with ID {request_id} not found.")

    sql = req["generated_sql"]
    updated_req = approval_queue.update_status(request_id, "REJECTED", admin)
    log_audit_event("REJECT_SQL", request_id, sql, admin, "REJECTED")
    return {
        "success": True,
        "message": "Query request rejected by administrator.",
        "request": updated_req
    }


def list_pending_requests() -> list:
    """Get all requests currently pending approval."""
    return approval_queue.get_pending()
