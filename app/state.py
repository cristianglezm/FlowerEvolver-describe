from typing import Optional
import asyncio
import onnxruntime as ort
import tiktoken
from aiokafka import AIOKafkaProducer
from redis.asyncio import Redis


class AppState:
    """A class to hold shared application state."""
    def __init__(self):
        self.encoder_session: Optional[ort.InferenceSession] = None
        self.decoder_session: Optional[ort.InferenceSession] = None
        self.tokenizer: Optional[tiktoken.Encoding] = None
        self.kafka_producer: Optional[AIOKafkaProducer] = None
        self.kafka_consumer_task: Optional[asyncio.Task] = None
        self.redis_client: Optional[Redis] = None


state = AppState()
