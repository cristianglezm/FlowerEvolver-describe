from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENCODER_MODEL_PATH: str = "models/onnx/encoder_model_quantized.onnx"
    DECODER_MODEL_PATH: str = "models/onnx/decoder_model_merged_quantized.onnx"
    # comma-separated providers
    ONNX_PROVIDERS: str = "CPUExecutionProvider"

    # comma-separated origins
    ORIGINS: str = "*"

    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_REQUEST_TOPIC: str = "descRequests"
    KAFKA_RESPONSE_TOPIC: str = "descResponses"

    REDIS_ENABLED: bool = False
    REDIS_URL: str = "redis://localhost:6379"
    RATE_LIMIT_TIMES: int = 5
    RATE_LIMIT_SECONDS: int = 10
    METRICS_API_KEY: str = "sk_change_key"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


# Create a single, importable instance for the entire application
settings = Settings()
