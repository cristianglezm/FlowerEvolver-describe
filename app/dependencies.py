import time
from typing import List, Optional

import structlog
from fastapi import Request, Response, HTTPException, Header
from starlette.middleware.base import BaseHTTPMiddleware
from pyrate_limiter import BucketAsyncWrapper, Duration, InMemoryBucket, Limiter, Rate, RedisBucket
from redis.asyncio import Redis
from fastapi_limiter.depends import RateLimiter

from .config import settings
from .metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_LATENCY_SECONDS
from .state import state

logger = structlog.get_logger(__name__)

RATE_LIMIT_BUCKET_KEY = "describe-api-rate-limit"


def _rates() -> List[Rate]:
    return [Rate(settings.RATE_LIMIT_TIMES, settings.RATE_LIMIT_SECONDS * Duration.SECOND)]


def build_in_memory_rate_limiter() -> RateLimiter:
    """
    Per-instance limiter. Used when REDIS_ENABLED=False, and also as the
    fallback if the Redis-backed limiter fails to come up at startup.

    InMemoryBucket is sync-only, so it's wrapped in BucketAsyncWrapper -- the
    fastapi-limiter RateLimiter dependency always calls try_acquire_async.
    """
    bucket = BucketAsyncWrapper(InMemoryBucket(_rates()))
    return RateLimiter(limiter=Limiter(bucket))


async def build_redis_rate_limiter(redis_client: Redis) -> RateLimiter:
    """
    Cross-instance limiter, sharing state across every app replica via Redis.
    RedisBucket.init() is a classmethod that must be awaited when given an
    async redis client (redis.asyncio.Redis) -- this is what actually wires
    the limiter up to Redis, which the old code never did.
    """
    bucket = await RedisBucket.init(_rates(), redis_client, RATE_LIMIT_BUCKET_KEY)
    return RateLimiter(limiter=Limiter(bucket))


async def rate_limiter_dependency(request: Request, response: Response):
    """
    The single rate-limiting dependency every router should depend on.

    state.rate_limiter is built exactly once, during app startup (see
    app/lifespan.py), via build_redis_rate_limiter() or
    build_in_memory_rate_limiter() above. This function just delegates to
    whichever one startup built -- there is exactly one place in the app that
    constructs a rate limiter, and exactly one dependency that uses it.
    """
    if state.rate_limiter is None:
        logger.error("rate_limiter_not_initialized")
        raise HTTPException(status_code=503, detail="Service Unavailable: Rate limiter not initialized.")
    return await state.rate_limiter(request, response)


async def verify_metrics_api_key(authorization: Optional[str] = Header(None)):
    """
    Dependency to verify the API key from the standard 'Authorization' header.
    Expects the format: 'Authorization: Bearer <your_api_key>'
    """
    if not settings.METRICS_API_KEY:
        logger.warning("metrics_api_key_not_configured", detail="Metrics endpoint is unprotected.")
        return

    if not authorization:
        logger.warning("metrics_access_denied", reason="Missing Authorization header")
        raise HTTPException(status_code=401, detail="Unauthorized: Missing Authorization header")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid authorization scheme")

        if token == settings.METRICS_API_KEY:
            return
    except ValueError:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid Authorization header format")

    logger.warning("metrics_access_denied", reason="Invalid API key")
    raise HTTPException(status_code=401, detail="Unauthorized: Invalid API key")


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        method = request.method
        endpoint = request.url.path
        response = await call_next(request)
        if request.scope.get("route"):
            endpoint = request.scope["route"].path

        status_code = response.status_code
        latency = time.time() - start_time

        HTTP_REQUEST_LATENCY_SECONDS.labels(endpoint=endpoint, method=method).observe(latency)
        HTTP_REQUESTS_TOTAL.labels(endpoint=endpoint, method=method, status_code=status_code).inc()
        logger.info("request_metrics_tracked", endpoint=endpoint, latency_sec=latency)
        return response
