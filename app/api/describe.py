import asyncio
import base64
import re
import structlog
from fastapi import APIRouter, Body, File, UploadFile, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi_limiter.depends import RateLimiter

from ..config import settings
from ..services import captioning
from ..dependencies import in_memory_rate_limiter
from ..state import state

logger = structlog.get_logger(__name__)

limiter_dependency = RateLimiter(
    times=settings.RATE_LIMIT_TIMES,
    seconds=settings.RATE_LIMIT_SECONDS
) if settings.REDIS_ENABLED else in_memory_rate_limiter

router = APIRouter(
    prefix="/api/v1/describe",
    tags=["Describe"],
    dependencies=[Depends(limiter_dependency)]
)

DATA_URL_PATTERN = re.compile(r"^data:(image/[a-z0-9.+-]+);base64,(.+)$", re.IGNORECASE)


def _check_models_loaded():
    if not all([state.encoder_session, state.decoder_session, state.tokenizer]):
        logger.error("api_request_failed_models_not_loaded")
        raise HTTPException(status_code=503, detail="Service Unavailable: Models are not loaded.")


@router.post(
    "/dataurl",
    summary="Describe image from JSON data URL",
    operation_id="describe_from_dataurl",
)
async def describe_dataurl(request: Request, data_url: str = Body(..., embed=True)):
    _check_models_loaded()
    if not data_url:
        raise HTTPException(status_code=422, detail="Data URL contains no image data.")

    match = DATA_URL_PATTERN.match(data_url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid data URL format.")

    try:
        image_bytes = base64.b64decode(match.group(2))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Base64 encoding.")

    try:
        result_text = await asyncio.to_thread(
            captioning.generate_description,
            image_bytes,
            state.encoder_session,
            state.decoder_session,
            state.tokenizer
        )
        logger.info("description_generated", endpoint="/dataurl", client_ip=request.client.host)
        return JSONResponse(content={"description": result_text})
    except Exception as e:
        logger.error("api_error", endpoint="/dataurl", error=str(e), exc_info=True)
        # Re-raise generic HTTP exceptions or handle them
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post(
    "/file",
    summary="Describe image from uploaded file",
    operation_id="describe_from_file",
)
async def describe_file(request: Request, image: UploadFile = File(...)):
    _check_models_loaded()
    if not image or not image.filename:
        raise HTTPException(status_code=422, detail="Image file is empty.")
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type.")

    raw_content = await image.read()

    try:
        result_text = await asyncio.to_thread(
            captioning.generate_description,
            raw_content,
            state.encoder_session,
            state.decoder_session,
            state.tokenizer
        )
        logger.info("description_generated", endpoint="/file", client_ip=request.client.host)
        return JSONResponse(content={"description": result_text})
    except Exception as e:
        logger.error("api_error", endpoint="/file", error=str(e), exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Internal Server Error")
