"""
FastAPI Table inference service.

Endpoints:
- GET  /healthz  - Health check
- POST /predict  - Table structure prediction (image + table_bboxes)
- GET  /metrics  - Prometheus metrics
"""

import io
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from PIL import Image
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .inference import predict
from .metrics import REQUESTS_TOTAL
from .model_loader import get_predictor, is_ready
from .schemas import PredictResponse

MAX_IMAGE_SIZE_MB = 50
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger("table")


@asynccontextmanager
async def lifespan(app):
    logger.info("Starting Table service")
    yield
    logger.info("Shutting down Table service")


app = FastAPI(
    title="Table Inference Service",
    description="Table structure recognition using docling-ibm-models TFPredictor (TableFormer)",
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
async def predict_endpoint(
    request: Request,
    file: UploadFile = File(...),
    table_bboxes: str = Form(
        ...,
        description='JSON array of table bboxes, e.g. [[178,748,1061,976],[177,1163,1062,1329]]',
    ),
    iocr_json: str | None = Form(
        default=None,
        description="Optional: IOCR JSON from docling (pages[0] structure) for text matching",
    ),
):
    """
    Run table structure prediction.

    - file: Image containing table(s)
    - table_bboxes: JSON array of [x1,y1,x2,y2] per table (from layout API)
    - iocr_json: Optional IOCR JSON for text matching (from docling pipeline)
    """
    request_id = str(uuid.uuid4())
    tenant_id = request.headers.get("X-Tenant-ID", "")
    start_time = time.perf_counter()

    try:
        # Parse table_bboxes
        try:
            bboxes = json.loads(table_bboxes)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid table_bboxes JSON: {e}")

        if not isinstance(bboxes, list) or len(bboxes) == 0:
            raise HTTPException(
                status_code=400,
                detail="table_bboxes must be a non-empty array of [x1,y1,x2,y2]",
            )

        for i, bbox in enumerate(bboxes):
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise HTTPException(
                    status_code=400,
                    detail=f"table_bboxes[{i}] must be [x1,y1,x2,y2]",
                )
            # Ensure integers
            bboxes[i] = [int(x) for x in bbox]

        # Parse optional iocr_json
        iocr = None
        if iocr_json:
            try:
                iocr = json.loads(iocr_json)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid iocr_json: {e}")

        # Read image
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
        result = predict(image, bboxes, request_id, iocr)

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "request_id=%s tenant_id=%s status_code=200 latency_ms=%.2f payload_size=%d tables=%d",
            request_id,
            tenant_id,
            latency_ms,
            len(content),
            len(result.tables),
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

    uvicorn.run("src.main:app", host="0.0.0.0", port=8001, reload=True)
