import json
import base64
import pytest
import asyncio
import numpy as np
from PIL import Image
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.state import state
from app.config import settings
from app.background import kafka_consumer


@pytest.fixture(scope="session")
def client():
    """
    Session-wide TestClient fixture that triggers the FastAPI lifespan.
    The TestClient automatically handles the app's lifespan events (startup/shutdown).
    """

    if not Path(".env").exists():
        with open(".env", "w") as f:
            f.write("METRICS_API_KEY=test_key\n")

    with TestClient(app) as c:
        if not all([state.encoder_session, state.decoder_session, state.tokenizer]):
            raise RuntimeError("AI models failed to load during test startup.")
        yield c


@pytest.fixture(scope="session")
def test_image_path() -> Path:
    """Provides the path to the test image, creating it if it doesn't exist."""
    assets_dir = Path("tests/assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    image_path = assets_dir / "flower.png"

    # Create a 10x10 pink image if it doesn't exist
    if not image_path.exists():
        img_array = np.full((10, 10, 3), [255, 192, 203], dtype=np.uint8)
        img = Image.fromarray(img_array, 'RGB')
        img.save(image_path)

    return image_path


def test_read_root(client):
    """Test the root endpoint to ensure the service is running."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Service is running. See documentation at /docs"}


def test_describe_file_success(client, test_image_path):
    """
    Integration test for the /api/v1/describe/file endpoint.
    This test requires the models to be available. It will be skipped if they are not.
    """
    if not Path(settings.ENCODER_MODEL_PATH).exists() or not Path(settings.DECODER_MODEL_PATH).exists():
        pytest.skip("Skipping integration test: ONNX models not found.")

    with open(test_image_path, "rb") as f:
        files = {"image": (test_image_path.name, f, "image/png")}
        response = client.post("/api/v1/describe/file", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "description" in data
    assert isinstance(data["description"], str)
    assert len(data["description"]) > 0


def test_describe_file_no_file(client):
    """Test hitting the file endpoint without providing a file."""
    response = client.post("/api/v1/describe/file")
    assert response.status_code == 422


def test_describe_file_wrong_file_type(client):
    """Test providing a non-image file to the file endpoint."""
    files = {"image": ("test.txt", b"this is not an image", "text/plain")}
    response = client.post("/api/v1/describe/file", files=files)
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_describe_dataurl_success(client, test_image_path):
    """Test providing a valid image as a data URL to the dataurl endpoint."""
    with open(test_image_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")
    data_url = f"data:image/png;base64,{b64_data}"

    if not Path(settings.ENCODER_MODEL_PATH).exists() or not Path(settings.DECODER_MODEL_PATH).exists():
        pytest.skip("Skipping data URL test: ONNX models not found.")

    response = client.post("/api/v1/describe/dataurl", json={"data_url": data_url})
    assert response.status_code == 200
    data = response.json()
    assert "description" in data
    assert isinstance(data["description"], str)
    assert len(data["description"]) > 0


def test_describe_dataurl_no_data(client):
    """Test hitting the dataurl endpoint without providing a data_url."""
    response = client.post("/api/v1/describe/dataurl", json={})
    assert response.status_code == 422


def test_consume_kafka_requests_with_mocked_kafka(client, test_image_path):
    """Tests the Kafka consumer logic with mocked Kafka clients and services."""
    async def _run():
        with open(test_image_path, "rb") as f:
            image_bytes = f.read()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        fake_request_id = "req-123"
        fake_description = "A beautiful flower"

        fake_msg = type("Msg", (), {
            "value": json.dumps({
                "request_id": fake_request_id,
                "image_base64": image_b64
            }).encode("utf-8"),
            "topic": settings.KAFKA_REQUEST_TOPIC
        })()

        mock_consumer = AsyncMock()

        async def fake_iter():
            yield fake_msg
        mock_consumer.__aiter__.side_effect = fake_iter

        mock_producer = AsyncMock()
        state.kafka_producer = mock_producer

        with patch("app.background.kafka_consumer.AIOKafkaConsumer", return_value=mock_consumer), \
             patch("app.services.captioning.generate_description", return_value=fake_description):

            mock_consumer.stop.side_effect = lambda: None

            await kafka_consumer.consume_kafka_requests(state)

        mock_producer.send_and_wait.assert_awaited_once()
        args, _ = mock_producer.send_and_wait.call_args

        assert args[0] == settings.KAFKA_RESPONSE_TOPIC
        sent_payload = json.loads(args[1].decode("utf-8"))
        assert sent_payload["request_id"] == fake_request_id
        assert sent_payload["description"] == fake_description

    asyncio.run(_run())
