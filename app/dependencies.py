import time
from typing import List, Optional

import structlog
from fastapi import Request, Response, HTTPException, Header
from starlette.middleware.base import BaseHTTPMiddleware
from pyrate_limiter import BucketAsyncWrapper, Duration, InMemoryBucket, Limiter, Rate, RedisBucket
from redis.asyncio import Redis

from .config import settings
from .metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_LATENCY_SECONDS
from .state import state

logger = structlog.get_logger(__name__)

RATE_LIMIT_BUCKET_KEY = "describe-api-rate-limit"


def _rates() -> List[Rate]:
    return [Rate(settings.RATE_LIMIT_TIMES, settings.RATE_LIMIT_SECONDS * Duration.SECOND)]


def build_in_memory_rate_limiter() -> Limiter:
    """Per-instance limiter. Used when REDIS_ENABLED=False, and as the
    fallback if the Redis-backed limiter fails to come up at startup."""
    bucket = BucketAsyncWrapper(InMemoryBucket(_rates()))
    return Limiter(bucket)


async def build_redis_rate_limiter(redis_client: Redis) -> Limiter:
    """Cross-instance limiter, sharing state across every app replica via Redis."""
    bucket = await RedisBucket.init(_rates(), redis_client, RATE_LIMIT_BUCKET_KEY)
    return Limiter(bucket)


async def rate_limiter_dependency(request: Request, response: Response):
    """The single rate-limiting dependency every router should depend on."""
    if state.rate_limiter is None:
        logger.error("rate_limiter_not_initialized")
        raise HTTPException(status_code=503, detail="Service Unavailable: Rate limiter not initialized.")

    key = f"{request.client.host}:{request.url.path}"
    success = await state.rate_limiter.try_acquire_async(key, blocking=False)
    if not success:
        logger.warning("rate_limit_exceeded", client_ip=request.client.host, path=request.url.path)
        raise HTTPException(status_code=429, detail="Too Many Requests")


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
