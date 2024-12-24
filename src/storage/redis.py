from redis.asyncio import Redis, ConnectionPool

from config.settings import settings


pool = ConnectionPool(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
redis_storage = Redis(connection_pool=pool)
