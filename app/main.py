import logging
import structlog
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest

from .config import settings
from .lifespan import lifespan
from .api import describe, monitoring
from .dependencies import verify_metrics_api_key, PrometheusMetricsMiddleware

logging.basicConfig(level=logging.INFO, format="%(message)s")
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger(__name__)

app = FastAPI(
    title="FlowerEvolver-describe Microservice",
    description="An API that generates descriptions for flower images.",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(PrometheusMetricsMiddleware)

allowed_origins = [origin.strip() for origin in settings.ORIGINS.split(',')]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)
logger.info("cors_middleware_configured", allow_origins=allowed_origins,)

app.include_router(describe.router)
app.include_router(monitoring.router)


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Service is running. See documentation at /docs"}


@app.get(
    "/metrics",
    tags=["Monitoring"],
    dependencies=[Depends(verify_metrics_api_key)],
    response_class=PlainTextResponse
)
async def metrics():
    """Exposes Prometheus-compatible metrics."""
    logger.info("metrics_endpoint_accessed")
    return generate_latest()
