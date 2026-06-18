from validation.schema_cache import schema_cache
from validation.ast_analyzer import analyze_sql_ast
from monitoring.logger import logger


async def ensure_schema_cache_loaded(force: bool = False):
    """
    Ensures schema is loaded into the validation cache.
    Delegates to cache.schema_cache.refresh() to guarantee a single
    code path for schema population — eliminating the duplicate D1 call
    that caused the 110-second latency on every request.
    """
    if schema_cache.is_loaded and not force:
        return

    # Import here to avoid circular imports at module load time
    from cache.schema_cache import schema_cache as runtime_cache
    logger.info("Schema not loaded — delegating refresh to RuntimeSchemaCache...")
    try:
        await runtime_cache.refresh()
    except Exception as e:
        logger.error(f"Schema cache load failed: {str(e)}")


async def validate_query_statically(sql: str) -> tuple[bool, str]:
    """Validates the input SQLite query against D1 active schemas using AST analysis."""
    await ensure_schema_cache_loaded()
    schema = schema_cache.get_schema()
    return analyze_sql_ast(sql, schema)
