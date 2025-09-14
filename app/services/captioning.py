import io
import time
import numpy as np
import onnxruntime as ort
import tiktoken
from PIL import Image
from fastapi import HTTPException
from ..metrics import MODEL_INFERENCES_TOTAL, MODEL_INFERENCE_LATENCY_SECONDS


def generate_description(
    image_bytes: bytes,
    encoder_session: ort.InferenceSession,
    decoder_session: ort.InferenceSession,
    tokenizer: tiktoken.Encoding
) -> str:
    """Processes an image and generates a description."""
    start_time = time.time()
    try:
        processed_image = _preprocess_image(image_bytes)

        encoder_inputs = {encoder_session.get_inputs()[0].name: processed_image}
        encoder_outputs = encoder_session.run(None, encoder_inputs)
        encoder_hidden_states = encoder_outputs[0]

        input_ids = np.array([[tokenizer.eot_token]], dtype=np.int64)

        num_layers, num_heads, head_dim = 12, 12, 64
        past_shape = [1, num_heads, 0, head_dim]
        dummy_past = [np.zeros(past_shape, dtype=np.float32) for _ in range(num_layers * 2)]

        decoder_input_names = [inp.name for inp in decoder_session.get_inputs()]
        past_key_input_names = [name for name in decoder_input_names if 'past_key_values' in name]
        past_key_values = dict(zip(past_key_input_names, dummy_past))
        output_names = ['logits'] + [out.name for out in decoder_session.get_outputs() if 'present' in out.name]

        generated_ids = []
        max_length = 256

        for _ in range(max_length):
            decoder_inputs = {
                "input_ids": input_ids,
                "encoder_hidden_states": encoder_hidden_states,
                "use_cache_branch": np.array([True], dtype=np.bool_),
                **past_key_values
            }
            decoder_outputs = decoder_session.run(output_names, decoder_inputs)
            logits, present_states = decoder_outputs[0], decoder_outputs[1:]
            past_key_values = dict(zip(past_key_input_names, present_states))
            next_token_id = np.argmax(logits[:, -1, :], axis=-1)

            if next_token_id[0] == tokenizer.eot_token:
                break

            generated_ids.append(next_token_id[0].item())
            input_ids = np.array([[next_token_id[0]]], dtype=np.int64)

        result = _postprocess_outputs(generated_ids, tokenizer)
        MODEL_INFERENCES_TOTAL.labels(status="success").inc()
        return result

    except Exception as e:
        MODEL_INFERENCES_TOTAL.labels(status="failure").inc()
        raise e
    finally:
        latency = time.time() - start_time
        MODEL_INFERENCE_LATENCY_SECONDS.observe(latency)


def _preprocess_image(image_bytes: bytes) -> np.ndarray:
    """Preprocesses the input image."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        img = img.resize((224, 224), resample=Image.Resampling.BILINEAR)
        img_array = np.array(img).astype(np.float32) / 255.0

        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        img_array = (img_array - mean) / std

        img_array = np.transpose(img_array, (2, 0, 1))
        return np.expand_dims(img_array, axis=0).astype(np.float32)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or corrupted image file.")


def _postprocess_outputs(output_ids: list, tokenizer: tiktoken.Encoding) -> str:
    """Postprocesses the model output to a human-readable format."""
    return tokenizer.decode(output_ids).strip()
