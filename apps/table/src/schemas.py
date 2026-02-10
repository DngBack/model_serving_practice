"""
Request/response models for Table inference API.
"""

from pydantic import BaseModel, Field


class Bbox(BaseModel):
    """Bounding box (l, t, r, b)."""

    l: float
    t: float
    r: float
    b: float


class TableCell(BaseModel):
    """Single table cell from TFPredictor."""

    bbox: Bbox
    start_row_offset_idx: int
    end_row_offset_idx: int
    start_col_offset_idx: int
    end_col_offset_idx: int
    row_span: int
    col_span: int
    column_header: bool = False
    row_header: bool = False
    row_section: bool = False
    text: str = Field(default="", description="Matched text from IOCR (if provided)")


class TableResult(BaseModel):
    """Result for one table."""

    table_index: int
    num_rows: int
    num_cols: int
    cells: list[TableCell] = Field(default_factory=list)


class PredictResponse(BaseModel):
    """Response for POST /predict."""

    request_id: str
    latency_ms: float
    tables: list[TableResult] = Field(default_factory=list)
