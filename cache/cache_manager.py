from cache.schema_cache import schema_cache
from cache.query_cache import query_cache
from monitoring.logger import logger


async def invalidate_all_caches():
    """
    Clears all cache registries. Should be called after schema migrations
    and worksheet synchronization operations.
    """
    logger.info("Invalidating all schema and query caches...")
    schema_cache.invalidate()
    query_cache.clear()
    
    # Reload schema cache asynchronously
    await schema_cache.refresh()
    logger.info("Caches successfully refreshed.")
