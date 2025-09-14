import asyncio
import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..state import state
from ..config import settings

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Monitoring"])


class ComponentStatus(BaseModel):
    status: str = Field(..., json_schema_extra="ok")
    details: str = Field(..., json_schema_extra="Component is operational")


class HealthCheckResponse(BaseModel):
    status: str = Field(..., json_schema_extra="ok")
    components: dict[str, ComponentStatus]


@router.get("/healthz", summary="Perform a Liveness Check")
async def get_liveness():
    return {"status": "ok"}


@router.get("/readyz", summary="Perform a Readiness Check")
async def get_readiness():
    if not all([state.encoder_session, state.decoder_session, state.tokenizer]):
        logger.warning("readiness_check_failed", reason="Models not loaded")
        raise HTTPException(status_code=503, detail="Service not ready: Models are not loaded.")

    return {"status": "ready"}


@router.get("/health", summary="Perform a Deep Health Check", response_model=HealthCheckResponse)
async def get_health():
    """
    Performs a detailed health check of the application and its dependencies.
    Checks the status of ML models, Kafka, and Redis.
    """
    components: dict[str, ComponentStatus] = {}
    is_healthy = True

    if all([state.encoder_session, state.decoder_session, state.tokenizer]):
        components["models"] = ComponentStatus(status="ok", details="Models are loaded and available.")
    else:
        components["models"] = ComponentStatus(status="error", details="Models are not loaded.")
        is_healthy = False

    if settings.KAFKA_ENABLED:
        if state.kafka_producer:
            try:
                await asyncio.wait_for(state.kafka_producer.partitions_for(settings.KAFKA_REQUEST_TOPIC), timeout=2.0)
                components["kafka"] = ComponentStatus(status="ok", details="Kafka producer is connected.")
            except Exception as e:
                logger.error("health_check_kafka_failed", error=str(e))
                components["kafka"] = ComponentStatus(status="error", details=f"Kafka connection failed: {e}")
                is_healthy = False
        else:
            components["kafka"] = ComponentStatus(status="error", details="Kafka producer not initialized.")
            is_healthy = False
    else:
        components["kafka"] = ComponentStatus(status="not_configured", details="Kafka is disabled.")

    if settings.REDIS_ENABLED:
        if state.redis_client:
            try:
                if await state.redis_client.ping():
                    components["redis"] = ComponentStatus(status="ok", details="Redis is connected.")
                else:
                    raise ConnectionError("PING command returned False")
            except Exception as e:
                logger.error("health_check_redis_failed", error=str(e))
                components["redis"] = ComponentStatus(status="error", details=f"Redis connection failed: {e}")
                is_healthy = False
        else:
            components["redis"] = ComponentStatus(status="error", details="Redis client not initialized.")
            is_healthy = False
    else:
        components["redis"] = ComponentStatus(status="not_configured", details="Redis is disabled.")

    overall_status = "ok" if is_healthy else "error"
    status_code = 200 if is_healthy else 503

    response_model = HealthCheckResponse(status=overall_status, components=components)

    return JSONResponse(
        content=response_model.model_dump(),
        status_code=status_code
    )
