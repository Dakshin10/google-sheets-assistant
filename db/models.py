from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from db.database import Base

class ConnectedSheet(Base):
    __tablename__ = "connected_sheets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    spreadsheet_id = Column(String, unique=True, nullable=False)
    spreadsheet_name = Column(String, nullable=True)
    owner_email = Column(String, nullable=True)
    sync_enabled = Column(Boolean, default=True)
    sync_frequency_minutes = Column(Integer, default=5)
    created_at = Column(DateTime, default=func.now())
    last_sync_at = Column(DateTime, nullable=True)
    last_successful_sync = Column(DateTime, nullable=True)
    sync_status = Column(String, default="PENDING")

class SheetSnapshot(Base):
    __tablename__ = "sheet_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    spreadsheet_id = Column(String, nullable=False)
    worksheet_title = Column(String, nullable=False)
    row_index = Column(Integer, nullable=False)
    row_hash = Column(String, nullable=False)
    row_data = Column(Text, nullable=False)  # Store JSON string of the row
    synced_at = Column(DateTime, default=func.now())

class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sheet_id = Column(Integer, ForeignKey("connected_sheets.id", ondelete="CASCADE"), nullable=False)
    sync_started = Column(DateTime, nullable=False)
    sync_finished = Column(DateTime, nullable=False)
    rows_added = Column(Integer, default=0)
    rows_updated = Column(Integer, default=0)
    rows_deleted = Column(Integer, default=0)
    status = Column(String, nullable=False)
    error_message = Column(Text, nullable=True)

class PendingSchemaChange(Base):
    __tablename__ = "pending_schema_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sheet_id = Column(Integer, ForeignKey("connected_sheets.id", ondelete="CASCADE"), nullable=False)
    worksheet_title = Column(String, nullable=False)
    change_type = Column(String, nullable=False)  # 'RENAME' or 'TYPE_CHANGE'
    details = Column(Text, nullable=False)  # Store JSON details of rename or type change
    created_at = Column(DateTime, default=func.now())
    status = Column(String, default="PENDING")  # 'PENDING', 'APPROVED', 'REJECTED'

class QueryApprovalRequest(Base):
    __tablename__ = "query_approvals"

    request_id = Column(String, primary_key=True)
    user = Column(String, nullable=False)
    generated_sql = Column(Text, nullable=False)
    status = Column(String, default="PENDING")  # 'PENDING', 'APPROVED', 'REJECTED', 'EXECUTED', 'FAILED'
    created_at = Column(DateTime, default=func.now())
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=func.now())
    action = Column(String, nullable=False)  # 'APPROVE_SQL', 'REJECT_SQL', etc.
    request_id = Column(String, nullable=True)
    sql = Column(Text, nullable=True)
    actor = Column(String, nullable=False)
    outcome = Column(String, nullable=False)  # 'EXECUTED', 'REJECTED', 'FAILED'
    error = Column(Text, nullable=True)
