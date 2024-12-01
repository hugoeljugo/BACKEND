import os
from functools import wraps
from redis import Redis, ConnectionError
from fastapi import HTTPException
import json
import logging

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

try:
    redis_client = Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        db=REDIS_DB,
        decode_responses=True
    )
except ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    raise

def cache_response(expire_time=300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
                cached_result = redis_client.get(cache_key)
                
                if cached_result:
                    return json.loads(cached_result)
                    
                result = await func(*args, **kwargs)
                redis_client.setex(
                    cache_key,
                    expire_time,
                    json.dumps(result)
                )
                return result
            except Exception as e:
                logger.error(f"Cache error in {func.__name__}: {str(e)}")
                return await func(*args, **kwargs)
        return wrapper
    return decorator