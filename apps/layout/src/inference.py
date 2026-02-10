"""
Inference logic for layout prediction.
"""

import time

from PIL import Image

from .metrics import INFERENCE_LATENCY, REGIONS_PER_REQUEST
from .schemas import Box, PredictResponse


def predict(image: Image.Image, request_id: str) -> PredictResponse:
    """Run layout prediction on an image."""
    from .model_loader import get_predictor

    predictor = get_predictor()

    t0 = time.perf_counter()
    raw_predictions = list(predictor.predict(image))
    latency_sec = time.perf_counter() - t0
    latency_ms = latency_sec * 1000

    INFERENCE_LATENCY.observe(latency_sec)
    REGIONS_PER_REQUEST.observe(len(raw_predictions))

    boxes = []
    confidences = []
    for pred in raw_predictions:
        boxes.append(
            Box(
                x1=pred["l"],
                y1=pred["t"],
                x2=pred["r"],
                y2=pred["b"],
                text=pred["label"],
                conf=pred["confidence"],
            )
        )
        confidences.append(pred["confidence"])

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    text = ", ".join(pred["label"] for pred in raw_predictions)

    return PredictResponse(
        request_id=request_id,
        text=text,
        confidence=round(avg_confidence, 4),
        latency_ms=round(latency_ms, 2),
        boxes=boxes,
    )
