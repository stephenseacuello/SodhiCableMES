"""Simple in-memory cache with TTL for expensive computations."""
from __future__ import annotations
import time
import functools
from flask import request


_cache: dict[str, tuple[float, object]] = {}


def cached(ttl: int = 30):
    """Decorator that caches a route's response for `ttl` seconds.

    Cache key is derived from the route path + query string.
    Use for GET endpoints only.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            key = f"{request.path}?{request.query_string.decode()}"
            now = time.time()
            if key in _cache:
                expires, value = _cache[key]
                if now < expires:
                    return value
            result = f(*args, **kwargs)
            _cache[key] = (now + ttl, result)
            return result
        return wrapper
    return decorator


def clear_cache() -> None:
    """Clear all cached entries."""
    _cache.clear()
