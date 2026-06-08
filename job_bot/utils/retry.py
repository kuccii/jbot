import asyncio
import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 4.0,
    exceptions: tuple = (Exception,),
):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_attempts:
                        logger.warning(
                            "retry_attempt",
                            func=func.__name__,
                            attempt=attempt,
                            delay=current_delay,
                            error=str(e),
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            raise last_error
        return wrapper
    return decorator
