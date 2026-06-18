from validation.schema_cache import schema_cache as validation_schema_cache
from retrieval.schema_index import schema_indexer
from db.database import db_gateway

db_client = db_gateway

# Tables that belong to the integration platform — never exposed to the LLM or query UI
INTERNAL_TABLES = frozenset({
    "connected_sheets", "sheet_snapshots", "sync_logs",
    "pending_schema_changes", "_cf_kv", "sqlite_sequence",
})


class RuntimeSchemaCache:
    """Enterprise schema cache maintaining validation caches and index structures."""
    def __init__(self):
        self._raw_schema = {}
        self._table_ddls = {}
        self._is_loaded = False

    async def refresh(self):
        """Fetches from D1 and repopulates the caches and indexes."""
        # 1. Fetch tables, excluding internal ones
        res = await db_client.execute_query(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT IN ('_cf_KV', 'sqlite_sequence')"
        )
        if not res.get("success"):
            return

        tables_info = res.get("result", [])
        # Filter out integration metadata tables from schema exposed to the LLM
        user_tables_info = [row for row in tables_info if row["name"].lower() not in INTERNAL_TABLES]
        tables = [row["name"] for row in user_tables_info]
        self._table_ddls = {row["name"]: row["sql"] for row in user_tables_info}

        pragma_results = {}
        for table in tables:
            pragma_res = await db_client.execute_query(f"PRAGMA table_info({table})")
            if pragma_res.get("success"):
                pragma_results[table] = pragma_res.get("result", [])

        # 2. Populate validation schema cache (user tables only)
        validation_schema_cache.load_from_db_result(tables, pragma_results)

        # 3. Populate RAG schema index
        schema_dict = validation_schema_cache.get_schema()
        self._raw_schema = schema_dict
        schema_indexer.index_schemas(schema_dict)
        self._is_loaded = True

    def get_raw_schema(self) -> dict:
        return self._raw_schema

    def get_ddls(self) -> dict:
        return self._table_ddls

    def invalidate(self):
        self._raw_schema = {}
        self._table_ddls = {}
        self._is_loaded = False
        validation_schema_cache.invalidate()


schema_cache = RuntimeSchemaCache()

