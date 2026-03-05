import requests
import base64
from pathlib import Path
import numpy as np
from PIL import Image
import sys

# Prevent pytest from collecting this file
__test__ = False

SERVICE_URL = "http://localhost:8000"


def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def test_root():
    r = requests.get(f"{SERVICE_URL}/")
    if r.status_code != 200:
        fail("Root endpoint returned non-200")
    if "Service is running" not in r.json().get("message", ""):
        fail("Unexpected root response")


def test_describe_file():
    img_path = Path("tests/assets/flower.png")
    img_path.parent.mkdir(parents=True, exist_ok=True)

    if not img_path.exists():
        arr = np.full((10, 10, 3), [255, 192, 203], dtype=np.uint8)
        Image.fromarray(arr).save(img_path)

    with open(img_path, "rb") as f:
        files = {"image": (img_path.name, f, "image/png")}
        r = requests.post(f"{SERVICE_URL}/api/v1/describe/file", files=files)

    if r.status_code != 200:
        fail("describe/file returned non-200")

    if "description" not in r.json():
        fail("Missing description in response")


def test_describe_dataurl():
    img_path = Path("tests/assets/flower.png")
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    data_url = f"data:image/png;base64,{b64}"

    r = requests.post(
        f"{SERVICE_URL}/api/v1/describe/dataurl",
        json={"data_url": data_url},
    )

    if r.status_code != 200:
        fail("describe/dataurl returned non-200")

    if "description" not in r.json():
        fail("Missing description in dataurl response")


if __name__ == "__main__":
    print("[INFO] Running E2E tests...")
    test_root()
    test_describe_file()
    test_describe_dataurl()
    print("[OK] All E2E tests passed")
