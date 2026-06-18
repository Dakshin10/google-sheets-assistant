import time
import hashlib


def _question_key(question: str) -> str:
    """Generates a stable SHA-256 cache key from a natural language question."""
    return hashlib.sha256(question.strip().lower().encode()).hexdigest()


class QueryCache:
    """
    In-memory cache for SQL query results with TTL invalidation.

    Two cache layers:
    - SQL cache: keyed by the exact SQL string (for identical generated queries)
    - Question cache: keyed by SHA-256 of the natural language question (skips LLM entirely)
    """
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._sql_cache: dict = {}
        self._question_cache: dict = {}

    # ── SQL-level cache ────────────────────────────────────────────────────────

    def get(self, sql: str):
        """Retrieve cached result by SQL string if not expired."""
        entry = self._sql_cache.get(sql.strip().lower())
        if entry:
            val, timestamp = entry
            if (time.time() - timestamp) <= self.ttl:
                return val
            self.delete(sql)
        return None

    def set(self, sql: str, result: dict):
        """Cache a query result by SQL string."""
        self._sql_cache[sql.strip().lower()] = (result, time.time())

    def delete(self, sql: str):
        self._sql_cache.pop(sql.strip().lower(), None)

    # ── Question-level cache (skips LLM generation) ───────────────────────────

    def get_by_question(self, question: str):
        """
        Retrieve cached (sql, result) by natural language question.
        Returns None if not found or expired.
        """
        key = _question_key(question)
        entry = self._question_cache.get(key)
        if entry:
            val, timestamp = entry
            if (time.time() - timestamp) <= self.ttl:
                return val  # returns {"sql": ..., "result": ..., "columns": ...}
            self._question_cache.pop(key, None)
        return None

    def set_by_question(self, question: str, sql: str, result: dict):
        """
        Cache both the generated SQL and its execution result keyed by question.
        This allows future identical questions to skip LLM generation entirely.
        """
        key = _question_key(question)
        self._question_cache[key] = (
            {"sql": sql, "result": result.get("result", []), "columns": result.get("columns", [])},
            time.time()
        )

    # ── Housekeeping ───────────────────────────────────────────────────────────

    def clear(self):
        """Clears both cache layers. Called after schema sync."""
        self._sql_cache.clear()
        self._question_cache.clear()


query_cache = QueryCache()
