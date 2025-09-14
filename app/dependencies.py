import time
import structlog
from fastapi import Request, HTTPException, Header
from starlette.middleware.base import BaseHTTPMiddleware
from cachetools import TTLCache
from typing import Optional

from .config import settings
from .metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_LATENCY_SECONDS

logger = structlog.get_logger(__name__)

# In-memory cache for rate limiting when Redis is disabled
# 10,000 max clients, 5-second time-to-live window
ttl_cache = TTLCache(maxsize=10000, ttl=settings.RATE_LIMIT_SECONDS)


def in_memory_rate_limiter(request: Request):
    """A simple in-memory rate limiter for use when Redis is disabled."""
    if not settings.REDIS_ENABLED:
        ip = request.client.host
        count = ttl_cache.get(ip, 0) + 1
        ttl_cache[ip] = count
        if count > settings.RATE_LIMIT_TIMES:
            logger.warning("in_memory_rate_limit_exceeded", client_ip=ip, count=count)
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
