import asyncio
import json
import base64
import structlog
from aiokafka import AIOKafkaConsumer

from ..config import settings
from ..services import captioning
from ..state import AppState

import time
from ..metrics import KAFKA_MESSAGES_PROCESSED_TOTAL, KAFKA_MESSAGE_PROCESSING_TIME_SECONDS

logger = structlog.get_logger(__name__)


def decode_base64_image(data_uri: str) -> bytes:
    # If it starts with a data URI scheme, remove it
    if data_uri.startswith("data:image"):
        data_uri = data_uri.split(",", 1)[1]
    data_uri = data_uri.strip().replace("\n", "").replace("\r", "")
    missing_padding = len(data_uri) % 4
    if missing_padding:
        data_uri += "=" * (4 - missing_padding)
    return base64.b64decode(data_uri)


async def consume_kafka_requests(state: AppState):
    """Consumes image description requests from a Kafka topic."""
    consumer = AIOKafkaConsumer(
        settings.KAFKA_REQUEST_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id="flower_desc_group",
        auto_offset_reset="earliest"
    )
    await consumer.start()
    logger.info("kafka_consumer_listening", topic=settings.KAFKA_REQUEST_TOPIC)
    try:
        async for msg in consumer:
            start_time = time.time()
            topic = msg.topic
            try:
                data = json.loads(msg.value.decode("utf-8"))
                request_id = data.get("request_id")
                image_base64 = data.get("image_base64")

                if not request_id or not image_base64:
                    logger.warning("invalid_kafka_message_skipped", message_data=data)
                    continue

                logger.info("processing_kafka_request", request_id=request_id)
                image_bytes = decode_base64_image(image_base64)

                description = await asyncio.to_thread(
                    captioning.generate_description,
                    image_bytes,
                    state.encoder_session,
                    state.decoder_session,
                    state.tokenizer
                )

                response_payload = {
                    "request_id": request_id,
                    "description": description,
                }
                await state.kafka_producer.send_and_wait(
                    settings.KAFKA_RESPONSE_TOPIC,
                    json.dumps(response_payload).encode("utf-8")
                )
                logger.info("produced_kafka_response", request_id=request_id)
                KAFKA_MESSAGES_PROCESSED_TOTAL.labels(topic=topic, status="success").inc()

            except Exception as e:
                logger.error("kafka_message_processing_error", error=str(e), exc_info=True)
                KAFKA_MESSAGES_PROCESSED_TOTAL.labels(topic=topic, status="failure").inc()
            finally:
                latency = time.time() - start_time
                KAFKA_MESSAGE_PROCESSING_TIME_SECONDS.labels(topic=topic).observe(latency)
    finally:
        await consumer.stop()
        logger.info("kafka_consumer_shutdown")
