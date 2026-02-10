"""
FastAPI Layout inference service.

Endpoints:
- GET  /healthz  - Health check
- POST /predict  - Layout prediction (multipart/form-data: file=@image)
- GET  /metrics  - Prometheus metrics
"""

import io
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from PIL import Image
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .inference import predict
from .metrics import REQUESTS_TOTAL
from .model_loader import get_predictor, is_ready
from .schemas import PredictResponse

MAX_IMAGE_SIZE_MB = 50
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger("layout")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Layout service")
    yield
    logger.info("Shutting down Layout service")


app = FastAPI(
    title="Layout Inference Service",
    description="Document layout detection using docling-ibm-models LayoutPredictor",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz():
    try:
        get_predictor()
        return {"status": "ok", "ready": is_ready()}
    except Exception as e:
        logger.exception("Health check failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/predict", response_model=PredictResponse)
async def predict_endpoint(request: Request, file: UploadFile = File(...)):
    """Run layout prediction on an uploaded image."""
    request_id = str(uuid.uuid4())
    tenant_id = request.headers.get("X-Tenant-ID", "")
    start_time = time.perf_counter()

    try:
        content_type = file.content_type or ""
        if not any(ct in content_type for ct in ["image/png", "image/jpeg", "image/jpg", "image/webp"]):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content type. Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}",
            )

        content = b""
        while chunk := await file.read(8192):
            content += chunk
            if len(content) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Image too large. Max size: {MAX_IMAGE_SIZE_MB}MB",
                )

        if not content:
            raise HTTPException(status_code=400, detail="Empty file")

        image = Image.open(io.BytesIO(content)).convert("RGB")
        result = predict(image, request_id)

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "request_id=%s tenant_id=%s status_code=200 latency_ms=%.2f payload_size=%d",
            request_id,
            tenant_id,
            latency_ms,
            len(content),
        )
        REQUESTS_TOTAL.labels(status="success").inc()
        return result

    except HTTPException:
        REQUESTS_TOTAL.labels(status="error").inc()
        raise
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.exception(
            "request_id=%s tenant_id=%s status_code=500 latency_ms=%.2f error=%s",
            request_id,
            tenant_id,
            latency_ms,
            str(e),
        )
        REQUESTS_TOTAL.labels(status="error").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
