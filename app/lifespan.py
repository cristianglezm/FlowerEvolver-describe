import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import onnxruntime as ort
import tiktoken
import structlog
from fastapi import FastAPI
from aiokafka import AIOKafkaProducer
from redis.asyncio import Redis
from fastapi_limiter.depends import RateLimiter


from .config import settings
from .background.kafka_consumer import consume_kafka_requests
from .state import state

logger = structlog.get_logger(__name__)


async def _startup():
    """Handles application startup logic."""
    try:
        encoder_path = Path(settings.ENCODER_MODEL_PATH)
        decoder_path = Path(settings.DECODER_MODEL_PATH)

        if not encoder_path.exists() or not decoder_path.exists():
            logger.error("model_files_not_found", detail="Please run download_models.py.")
            return

        providers_to_try = [p.strip() for p in settings.ONNX_PROVIDERS.split(',')]

        logger.info("loading_onnx_models", providers=providers_to_try)
        state.encoder_session = ort.InferenceSession(str(encoder_path), providers=providers_to_try)
        state.decoder_session = ort.InferenceSession(str(decoder_path), providers=providers_to_try)
        logger.info("models_loaded_successfully")

        logger.info("loading_tokenizer")
        state.tokenizer = tiktoken.get_encoding("gpt2")
        logger.info("tokenizer_loaded_successfully")

    except Exception as e:
        logger.error("startup_model_loading_error", error=str(e), exc_info=True)

    if settings.KAFKA_ENABLED:
        logger.info("kafka_enabled_initializing")
        try:
            state.kafka_producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
            await state.kafka_producer.start()
            logger.info("kafka_producer_started")
            state.kafka_consumer_task = asyncio.create_task(consume_kafka_requests(state))
            logger.info("kafka_consumer_task_created", topic=settings.KAFKA_REQUEST_TOPIC)
        except Exception as e:
            logger.error("kafka_initialization_failed", error=str(e), exc_info=True)

    if settings.REDIS_ENABLED:
        logger.info("redis_enabled_initializing_rate_limiter")
        try:
            state.redis_client = Redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
            await RateLimiter.init(state.redis_client)
            logger.info("fastapi_limiter_initialized_successfully")
        except Exception as e:
            logger.error("fastapi_limiter_initialization_failed", error=str(e), exc_info=True)
            state.redis_client = None


async def _shutdown():
    """Handles application shutdown logic."""
    if state.kafka_producer:
        await state.kafka_producer.stop()
        logger.info("kafka_producer_stopped")
    if state.kafka_consumer_task and not state.kafka_consumer_task.done():
        state.kafka_consumer_task.cancel()
        logger.info("kafka_consumer_task_cancelled")
    if state.redis_client:
        await state.redis_client.close()
        logger.info("redis_client_closed")
    logger.info("application_shutdown_complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """The application's lifespan context manager."""
    await _startup()
    try:
        yield
    finally:
        await _shutdown()
