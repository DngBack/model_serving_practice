"""
Request/response models for Layout inference API.
"""

from pydantic import BaseModel, Field


class Box(BaseModel):
    """Bounding box for a layout region."""

    x1: float = Field(..., description="Left coordinate")
    y1: float = Field(..., description="Top coordinate")
    x2: float = Field(..., description="Right coordinate")
    y2: float = Field(..., description="Bottom coordinate")
    text: str = Field(..., description="Region label (e.g. Table, Text, Picture)")
    conf: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class PredictResponse(BaseModel):
    """Response for POST /predict."""

    request_id: str = Field(..., description="Unique request identifier")
    text: str = Field(
        default="",
        description="Aggregated text representation (comma-separated region labels)",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Average confidence across all regions",
    )
    latency_ms: float = Field(..., description="Inference latency in milliseconds")
    boxes: list[Box] = Field(default_factory=list, description="Detected layout regions")
