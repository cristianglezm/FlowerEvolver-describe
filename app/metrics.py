from prometheus_client import Counter, Histogram

# Counter for tracking the total number of HTTP requests.
# The 'endpoint' label will distinguish between different routes like '/', '/api/v1/describe/file'.
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests made.",
    ["endpoint", "method", "status_code"]
)

HTTP_REQUEST_LATENCY_SECONDS = Histogram(
    "http_request_latency_seconds",
    "Latency of HTTP requests.",
    ["endpoint", "method"]
)

MODEL_INFERENCES_TOTAL = Counter(
    "model_inferences_total",
    "Total number of image captioning inferences performed.",
    ["status"]  # 'success' or 'failure'
)

MODEL_INFERENCE_LATENCY_SECONDS = Histogram(
    "model_inference_latency_seconds",
    "Latency of the ML model generating a description."
)

KAFKA_MESSAGES_PROCESSED_TOTAL = Counter(
    "kafka_messages_processed_total",
    "Total number of Kafka messages processed by the consumer.",
    ["topic", "status"]  # status: 'success', 'failure'
)

KAFKA_MESSAGE_PROCESSING_TIME_SECONDS = Histogram(
    "kafka_message_processing_time_seconds",
    "Time taken to process a single Kafka message (inference + publish).",
    ["topic"]
)
