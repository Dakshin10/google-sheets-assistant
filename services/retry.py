import asyncio
import random
from monitoring.logger import logger


def async_retry(retries=3, backoff_base=2.0, max_delay=16.0, exceptions=(Exception,)):
    """
    Decorator for retrying asynchronous operations with exponential backoff and jitter.
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            delay = backoff_base
            for attempt in range(1, retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == retries:
                        logger.error(f"Function {func.__name__} failed on final attempt {attempt}: {str(e)}")
                        raise e
                    
                    # Apply randomized jitter: delay = delay * 0.5 + random_between_0_and_delay_half
                    jitter = delay * 0.5
                    current_delay = min(max_delay, delay + random.uniform(-jitter, jitter))
                    
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{retries}): {str(e)}. "
                        f"Retrying in {current_delay:.2f}s..."
                    )
                    
                    await asyncio.sleep(current_delay)
                    delay *= 2.0
            return await func(*args, **kwargs)
        return wrapper
    return decorator
