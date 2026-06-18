import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from contextlib import contextmanager

from config import DATA_DIR, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_DATABASE_ID
from services.d1_http_client import D1HttpClient

# Local SQLite file for metadata and local-mode sheet data
LOCAL_DB_FILE = DATA_DIR / "database.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{LOCAL_DB_FILE}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class DatabaseGateway:
    """
    Unified database client that routes queries either to remote Cloudflare D1
    or to the local SQLite database, depending on configuration.
    """
    def __init__(self):
        self.d1_client = D1HttpClient()
        
    def _use_local_sqlite(self) -> bool:
        """Determines if the system should fall back to local SQLite execution."""
        return (
            not CLOUDFLARE_API_TOKEN
            or CLOUDFLARE_API_TOKEN == "dummy_api_token"
            or not CLOUDFLARE_ACCOUNT_ID
            or CLOUDFLARE_ACCOUNT_ID == "dummy_account_id"
            or not CLOUDFLARE_DATABASE_ID
            or CLOUDFLARE_DATABASE_ID == "dummy_database_id"
        )

    async def execute_query(self, sql: str, params: list = None) -> dict:
        """Executes a single SQL query either in remote D1 or local SQLite."""
        if not self._use_local_sqlite():
            return await self.d1_client.execute_query(sql, params)
            
        # Execute locally
        params = params or []
        try:
            # Connect to SQLite file directly
            conn = sqlite3.connect(LOCAL_DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(sql, params)
            
            # Commit changes for write queries
            is_write = not sql.strip().upper().startswith(("SELECT", "PRAGMA", "WITH"))
            if is_write:
                conn.commit()
                
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description] if cursor.description else []
            
            result_list = [dict(row) for row in rows]
            conn.close()
            
            return {
                "success": True,
                "result": result_list,
                "columns": columns,
                "meta": {"duration": 0.0}
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "result": []
            }

    async def execute_batch(self, queries: list) -> list:
        """Executes a batch of SQL queries sequentially."""
        if not self._use_local_sqlite():
            return await self.d1_client.execute_batch(queries)
            
        # Execute locally in a single transaction block
        outcomes = []
        try:
            conn = sqlite3.connect(LOCAL_DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            for q in queries:
                try:
                    if isinstance(q, tuple):
                        sql, params = q
                    else:
                        sql, params = q, []
                        
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    columns = [col[0] for col in cursor.description] if cursor.description else []
                    result_list = [dict(row) for row in rows]
                    
                    outcomes.append({
                        "success": True,
                        "result": result_list,
                        "columns": columns
                    })
                except Exception as ex:
                    outcomes.append({
                        "success": False,
                        "error": str(ex)
                    })
            
            conn.commit()
            conn.close()
        except Exception as e:
            # Connection level failure
            outcomes = [{"success": False, "error": str(e)} for _ in queries]
            
        return outcomes

# Initialize tables
def init_db():
    Base.metadata.create_all(bind=engine)

# Singleton gateway instance
db_gateway = DatabaseGateway()
