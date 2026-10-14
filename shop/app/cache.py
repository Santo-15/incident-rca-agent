# NEW FILE: shop/app/cache.py. One Redis client for the whole app (like db.py for Postgres)

import os  # read settings from environment variables
import redis  # official Redis client library (redis-py)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")  # Compose sets redis://redis:6379/0; fallback = laptop via the 127.0.0.1 door; /0 = database number 0
CART_TTL_SECONDS = int(os.getenv("CART_TTL_SECONDS", "86400"))  # carts expire after 24 h of no activity; env vars are text, so int()

redis_client = redis.Redis.from_url(  # creates a client with its own connection pool; doesn't connect until the first command
    REDIS_URL,  # where Redis is
    decode_responses=True,  # give back Python text ("3") instead of raw bytes (b"3")
    socket_connect_timeout=2,  # give up connecting after 2 s, so redis_down gives a fast 500 instead of a hang
    socket_timeout=2,  # give up waiting for a reply after 2 s
)


def get_redis():  # dependency for endpoints, same idea as get_db; tests swap it for a test client
    return redis_client  # the same shared client every time (it manages its own pool)