# FlowerEvolver-describe Microservice

[![CI](https://github.com/cristianglezm/FlowerEvolver-describe/actions/workflows/ci.yml/badge.svg)](https://github.com/cristianglezm/FlowerEvolver-describe/actions/workflows/ci.yml)[![CD - Build & Push Docker Image](https://github.com/cristianglezm/FlowerEvolver-describe/actions/workflows/docker.yml/badge.svg?branch=master)](https://github.com/cristianglezm/FlowerEvolver-describe/actions/workflows/docker.yml)

A FastAPI microservice that generates textual descriptions for images of flowers using pre-trained ONNX models. It can serve requests via a REST API and, optionally, process them asynchronously through Kafka.

## Description

This service provides a robust, scalable solution for ML-powered image captioning. It is designed for production-like local development and testing with comprehensive monitoring, including structured logging, Prometheus metrics, pre-configured Grafana dashboards, and detailed health checks.

The architecture promotes an **asynchronous-first workflow**. For computationally expensive tasks like generating a new flower description, requests should be sent to a Kafka topic. The service processes these requests in the background, ensuring a responsive user experience in the primary application. Synchronous REST API endpoints are also available for direct, on-demand use cases.

> **Warning: For Educational & Development Use**
> This repository provides a complete, orchestrated stack for local development and learning. It is **not** intended for direct production deployment without significant modifications. See the "Production Considerations" section for more details.

## Model & Dataset

The image captioning model is a `ViT-GPT2` architecture optimized for ONNX Runtime. The models are hosted on the [cristianglezm/ViT-GPT2-FlowerCaptioner-ONNX](https://huggingface.co/cristianglezm/ViT-GPT2-FlowerCaptioner-ONNX) Hugging Face repository.

The training [dataset](https://huggingface.co/datasets/cristianglezm/FlowerEvolver-Dataset) was custom-built using images generated from [FlowerEvolver](https://github.com/cristianglezm/FlowerEvolver-frontend) desktop app. It consists of 500 images, each with a description generated from a basic template and curated. This specialized dataset allows the model to produce descriptions tailored to the unique visual characteristics of the generated flowers.

## Features

-   **Modular Architecture**: Structured into distinct modules for configuration, API endpoints, services, and background tasks.
-   **Full Observability Stack**:
    -   **Structured Logging**: `structlog` for machine-readable JSON logs.
    -   **Prometheus Metrics**: Exposes detailed metrics at `/metrics`, configured for a multi-process Gunicorn environment. Includes exporters for Kafka and Redis.
    -   **Grafana Dashboards**: Pre-configured with a Prometheus datasource and dashboards for visualizing application and system health.
    -   **Health Checks**: Provides `/healthz` (liveness), `/readyz` (readiness), and `/health` (deep dependency check) endpoints.
-   **Containerized & Orchestrated**:
    -   A multi-stage `Dockerfile` creates a lightweight, secure production image running on Python 3.10.
    -   A `docker-compose.yml` file orchestrates the entire stack: the app, Redis, Kafka, Prometheus, and Grafana.
-   **Robust API & Performance**:
    -   **Asynchronous & Synchronous Processing**: Supports both Kafka and direct REST API workflows.
    -   **Rate Limiting**: Configurable, dual-mode rate limiting (Redis-backed or in-memory fallback).
    -   **Gunicorn Server**: Runs with Gunicorn and Uvicorn workers for concurrent request handling.
-   **Automated CI/CD**:
    -   GitHub Actions for automated testing with `pytest` and code quality checks with `flake8`.
    -   Workflow for automatically publishing Docker images to a registry.
    -   `Dependabot` configured for `pip` and `github-actions` to keep dependencies up-to-date.

## Project Structure
```
.
├── app/
│   ├── api/             # API Routers (describe, monitoring)
│   ├── background/      # Kafka consumer logic
│   ├── services/        # Core ML/business logic
│   ├── config.py        # Pydantic settings management
│   ├── dependencies.py  # Reusable dependencies (API key, rate limiter)
│   ├── lifespan.py      # Startup/shutdown event logic
│   ├── metrics.py       # Prometheus metric definitions
│   ├── state.py         # Shared application state
│   └── main.py          # Main application assembler
├── docker/              # Docker-specific configurations
│   ├── grafana/
│   ├── prometheus/
│   ├── gunicorn_config.py
│   └── wait_for_it.sh
├── tests/               # Test assets
├── .env                 # Local environment configuration
├── Dockerfile           # Multi-stage container build definition
├── docker-compose.yml   # Full stack orchestration
├── kafka_tester.py      # Script to test Kafka round-trip
├── test_main.py         # Script to test e2e
└── requirements.txt
```

## Getting Started

### Prerequisites
- Python 3.10+
- Docker
- Docker Compose

### Running fastapi / uvicorn

This is the way to run the service without the kafka background worker.

```bash
# Make sure to install dependencies first
pip install -r requirements.txt
# Download models
python download_models.py

# Run with FastAPI's development server
fastapi run
# or use Uvicorn directly for more control
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Running the Full Stack with Docker Compose

This is the easiest way to run the service and all its monitoring and messaging dependencies.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/cristianglezm/FlowerEvolver-describe.git
    cd FlowerEvolver-describe
    ```

2.  **Configure your environment:**
    An example `.env` file is provided. For the Docker Compose setup to work fully, you should enable Kafka and Redis.
    ```bash
    # .env
    ENCODER_MODEL_PATH="models/onnx/encoder_model_quantized.onnx"
    DECODER_MODEL_PATH="models/onnx/decoder_model_merged_quantized.onnx"
    ONNX_PROVIDERS="CPUExecutionProvider"
    
    ORIGINS="*"
    
    # Enable Kafka and Redis for the full stack
    KAFKA_ENABLED="true"
    KAFKA_BOOTSTRAP_SERVERS="kafka:9092"
    KAFKA_REQUEST_TOPIC="descRequests"
    KAFKA_RESPONSE_TOPIC="descResponses"
    
    REDIS_ENABLED="true"
    REDIS_URL="redis://redis:6379"
    
    RATE_LIMIT_TIMES=5
    RATE_LIMIT_SECONDS=10
    
    METRICS_API_KEY="sk_change_key"
    ```

3.  **Build and run the services:**
    This command will build the application image and start all services defined in `docker-compose.yml`.
    ```bash
    docker-compose up --build
    ```

4.  **Access the Services:**
    Once all containers are running, the various services will be available at:
    -   **Application API**: `http://localhost:8000`
    -   **Swagger UI Docs**: `http://localhost:8000/docs`
    -   **Prometheus UI**: `http://localhost:9090`
    -   **Grafana UI**: `http://localhost:3000` (Login: `admin` / `admin`)

5.  **Shutting Down:**
    To stop all running containers, press `Ctrl+C` in the terminal where compose is running, and then run:
    ```bash
    docker-compose down
    ```

### Manual Docker Build and Run

If you only want to build and run the application container without its dependencies, you can use these commands:

1.  **Build the image:**
    ```bash
    docker build -t fe-describe .
    ```

2.  **Run the container:**
    *(Note: Without Kafka/Redis, features relying on them will not work unless disabled in `.env`)*
    ```bash
    docker run -d -p 8000:8000 --name flower-app --env-file .env fe-describe
    ```

## Testing

### Integration Tests
The project includes an integration test suite. Run it from the project root:
```bash
pytest
```

### Kafka Round-Trip Test
A dedicated script, `kafka_tester.py`, is provided to test the full asynchronous pipeline.

1.  Ensure the full stack is running via `docker-compose up`.
2.  In a separate terminal, run the script:
    ```bash
    python kafka_tester.py
    ```
    This will send a message to the `descRequests` topic and wait for the processed response on the `descResponses` topic.

## Production Considerations

This setup is designed for a rich local development experience and is **NOT** ready for production as-is. Key areas to address before deploying to a live environment include:

-   **Secret Management**: All secrets (like `METRICS_API_KEY`) are currently in plaintext in the `.env` file and `prometheus.yml`. In production, these should be managed by a secure vault (like HashiCorp Vault, AWS Secrets Manager, etc.) and injected into the environment at runtime.
-   **Persistent Storage**: The Docker Compose setup uses Docker volumes for data persistence, which is fine for local use. A production Kafka and Prometheus setup requires robust, durable, and replicated storage solutions.
-   **Networking**: All service ports are exposed to `localhost`. In production, only the main application port and Grafana port should be exposed to the public internet, typically behind a load balancer or reverse proxy.
-   **High Availability**: This setup runs single instances of Kafka, Redis, and Prometheus. A production environment would require a replicated, highly available cluster for each of these critical components.
