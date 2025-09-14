import os
from huggingface_hub import hf_hub_download


def download_model_files():
    """
    Downloads the required ONNX models from the Hugging Face Hub.
    """
    repo_id = "cristianglezm/ViT-GPT2-FlowerCaptioner-ONNX"
    model_files = [
        "onnx/encoder_model_quantized.onnx",
        "onnx/decoder_model_merged_quantized.onnx"
    ]
    local_dir = "models"

    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
        print(f"Created directory: {local_dir}")

    print(f"Downloading models from Hugging Face repository: {repo_id}")

    for filename in model_files:
        print(f"Downloading {filename}...")
        try:
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=local_dir
            )
            print(f"Successfully downloaded {filename} to {local_dir}/")
        except Exception as e:
            print(f"An error occurred while downloading {filename}: {e}")
            break
    else:
        print("\nAll models downloaded successfully.")


if __name__ == "__main__":
    download_model_files()
