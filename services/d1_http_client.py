import httpx
import json
import asyncio
from config import CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_DATABASE_ID, D1_DATABASE_NAME
from services.retry import async_retry
from exceptions.d1_exceptions import D1ConnectionError, D1QueryExecutionError
from monitoring.logger import logger
from monitoring.metrics import metrics

# Create connection-pooled async client
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(15.0, connect=5.0),
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
)


class D1HttpClient:
    """Production-grade REST client to execute SQL queries on Cloudflare D1 database, with Wrangler fallback."""
    def __init__(self):
        self.account_id = CLOUDFLARE_ACCOUNT_ID
        self.api_token = CLOUDFLARE_API_TOKEN
        self.database_id = CLOUDFLARE_DATABASE_ID
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/d1/database/{self.database_id}"

        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        # Warn at construction time so the performance impact is visible immediately in logs
        if self._use_wrangler_fallback():
            logger.warning(
                "⚠️  CLOUDFLARE_API_TOKEN is not configured or is a placeholder. "
                "Falling back to Wrangler CLI subprocess execution. "
                "Expect 10–30× higher query latency (~3s per subprocess spawn). "
                "Set CLOUDFLARE_API_TOKEN in your .env to enable the REST API path (<350ms per query)."
            )

    def _use_wrangler_fallback(self) -> bool:
        """Determines if the client should fall back to Wrangler CLI based on missing API token credentials."""
        return (
            not self.api_token
            or self.api_token == "dummy_api_token"
            or not self.account_id
            or self.account_id == "dummy_account_id"
            or not self.database_id
            or self.database_id == "dummy_database_id"
        )

    def _validate_config(self):
        if not self.account_id or self.account_id == "dummy_account_id" or not self.api_token or not self.database_id:
            raise D1ConnectionError(
                "Cloudflare credentials are not configured. "
                "Please set CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, "
                "and CLOUDFLARE_DATABASE_ID in your .env file."
            )

    async def _execute_query_via_wrangler(self, sql: str, params: list = None) -> dict:
        """Asynchronously runs a query via Wrangler CLI subprocess wrapper."""
        sql_clean = " ".join(sql.split()).replace('"', '\\"')
        cmd = f'npx wrangler d1 execute {D1_DATABASE_NAME} --remote --command="{sql_clean}" --json'
        
        logger.info(f"D1 Subprocess Fallback Query Execution: {sql[:120]}")
        with metrics.track_duration("d1_wrangler_query_time"):
            try:
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    err_content = stderr.decode('utf-8', errors='ignore')
                    raise D1QueryExecutionError(
                        f"Wrangler CLI Error: {err_content}",
                        sql=sql
                    )
                    
                stdout_str = stdout.decode("utf-8", errors="ignore")
                # Parse JSON array returned by Wrangler
                try:
                    data = json.loads(stdout_str)
                except json.JSONDecodeError:
                    raise D1QueryExecutionError(f"Failed to parse Wrangler output as JSON: {stdout_str}", sql=sql)
                    
                if not data:
                    return {"success": True, "result": []}
                    
                outcome = data[0]
                rows = outcome.get("results", [])
                meta = outcome.get("meta", {})
                columns = list(rows[0].keys()) if rows else []
                
                return {
                    "success": True,
                    "result": rows,
                    "columns": columns,
                    "meta": meta
                }
            except Exception as e:
                if isinstance(e, D1QueryExecutionError):
                    raise e
                raise D1QueryExecutionError(f"Wrangler Execution failed: {str(e)}", sql=sql)

    @async_retry(retries=3, exceptions=(httpx.HTTPError,))
    async def execute_query(self, sql: str, params: list = None) -> dict:
        """Executes a single SQL query against the D1 REST API, falling back to Wrangler CLI if needed."""
        if self._use_wrangler_fallback():
            return await self._execute_query_via_wrangler(sql, params)
            
        self._validate_config()
        url = f"{self.base_url}/query"
        payload = {
            "sql": sql,
            "params": params or []
        }
        
        logger.info(f"D1 HTTP Query Execution: {sql[:120]}")
        with metrics.track_duration("d1_http_query_time"):
            try:
                response = await http_client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                try:
                    body = response.json()
                    errors = body.get("errors", [{"message": str(e)}])
                    err_msg = errors[0].get("message")
                    code = errors[0].get("code")
                except ValueError:
                    err_msg = str(e)
                    code = None
                raise D1QueryExecutionError(
                    f"D1 API Execution Error: {err_msg}",
                    sql=sql,
                    error_code=code
                )
            except httpx.RequestError as e:
                raise D1ConnectionError(f"HTTP request connection failure: {str(e)}")
            
            body = response.json()
            if not body.get("success"):
                errors = body.get("errors", [{"message": "Unknown API Error"}])
                raise D1QueryExecutionError(
                    f"D1 API Execution Error: {errors[0].get('message')}",
                    sql=sql,
                    error_code=errors[0].get("code")
                )
            
            results = body.get("result", [])
            if not results:
                return {"success": True, "result": []}
            
            outcome = results[0]
            rows = outcome.get("results", [])
            meta = outcome.get("meta", {})
            columns = list(rows[0].keys()) if rows else []
            
            return {
                "success": True,
                "result": rows,
                "columns": columns,
                "meta": meta
            }

    async def execute_batch(self, queries: list) -> list:
        """
        Executes a batch of queries sequentially.
        queries: list of tuples like (sql_string, params_list) or list of SQL query strings.
        """
        outcomes = []
        logger.info(f"Executing batch of {len(queries)} queries sequentially...")
        for idx, q in enumerate(queries):
            try:
                if isinstance(q, tuple):
                    res = await self.execute_query(q[0], q[1])
                else:
                    res = await self.execute_query(q)
                outcomes.append(res)
            except Exception as e:
                logger.error(f"Batch query index {idx} failed: {str(e)}")
                outcomes.append({"success": False, "error": str(e)})
        return outcomes

    async def initialize_tables(self):
        """Creates the synchronization metadata tables if they do not exist."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS connected_sheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spreadsheet_id TEXT UNIQUE,
                spreadsheet_name TEXT,
                owner_email TEXT,
                sync_enabled BOOLEAN DEFAULT 1,
                sync_frequency_minutes INTEGER DEFAULT 5,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_sync_at DATETIME,
                last_successful_sync DATETIME,
                sync_status TEXT DEFAULT 'PENDING'
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS sheet_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spreadsheet_id TEXT,
                worksheet_title TEXT,
                row_index INTEGER,
                row_hash TEXT,
                row_data TEXT,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(spreadsheet_id, worksheet_title, row_index)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS sync_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_id INTEGER,
                sync_started DATETIME,
                sync_finished DATETIME,
                rows_added INTEGER DEFAULT 0,
                rows_updated INTEGER DEFAULT 0,
                rows_deleted INTEGER DEFAULT 0,
                status TEXT,
                error_message TEXT,
                FOREIGN KEY(sheet_id) REFERENCES connected_sheets(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS pending_schema_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sheet_id INTEGER,
                worksheet_title TEXT,
                change_type TEXT,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'PENDING',
                FOREIGN KEY(sheet_id) REFERENCES connected_sheets(id) ON DELETE CASCADE
            );
            """
        ]
        logger.info("Initializing persistent integration metadata tables...")
        await self.execute_batch(queries)


