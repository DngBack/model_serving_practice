"""
Inference logic for table structure prediction.
"""

import copy
import time

import cv2
import numpy as np
from PIL import Image

from .metrics import INFERENCE_LATENCY, TABLES_PER_REQUEST
from .schemas import Bbox, PredictResponse, TableCell, TableResult


def _build_iocr_page(
    image: np.ndarray,
    image_width: int,
    image_height: int,
    table_bboxes: list[list[int]],
    iocr_json: dict | None = None,
) -> dict:
    """
    Build iocr_page dict for TFPredictor.
    If iocr_json provided, use its pages[0] and augment with image/table_bboxes.
    Otherwise create minimal page with empty tokens.
    """
    if iocr_json and "pages" in iocr_json and len(iocr_json["pages"]) > 0:
        page = copy.deepcopy(iocr_json["pages"][0])
    else:
        page = {
            "blocks": [],
            "cells": [],
            "height": image_height,
            "width": image_width,
            "dimensions": {
                "bbox": [0, 0, image_width, image_height],
                "height": image_height,
                "origin": "TopLeft",
                "width": image_width,
            },
            "fonts": [],
            "links": [],
            "rotation": 0.0,
            "rectangles": [],
            "textPositions": [],
            "text_lines": [],
            "tokens": [],
            "localized_image_locations": [],
            "scanned_elements": [],
            "paths": [],
            "pageNumber": 1,
            "page_image": {},
            "lang": ["en"],
        }

    # TFPredictor expects BGR (cv2 format)
    if len(image.shape) == 3 and image.shape[2] == 3:
        page["image"] = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    else:
        page["image"] = image
    page["table_bboxes"] = copy.deepcopy(table_bboxes)
    return page


def _extract_text_from_cell(cell: dict) -> str:
    """Extract matched text from text_cell_bboxes if present."""
    bboxes = cell.get("text_cell_bboxes", [])
    if not bboxes:
        return ""
    tokens = [b.get("token", "") for b in bboxes if isinstance(b, dict)]
    return " ".join(tokens).strip()


def predict(
    image: Image.Image,
    table_bboxes: list[list[int]],
    request_id: str,
    iocr_json: dict | None = None,
) -> PredictResponse:
    """Run table structure prediction on image with given table regions."""
    from .model_loader import get_predictor

    predictor = get_predictor()

    img_np = np.array(image.convert("RGB"))
    h, w = img_np.shape[:2]
    iocr_page = _build_iocr_page(img_np, w, h, table_bboxes, iocr_json)

    t0 = time.perf_counter()
    # Pass copy - TFPredictor mutates table_bboxes in place
    multi_tf_output = predictor.multi_table_predict(
        iocr_page,
        copy.deepcopy(table_bboxes),
        do_matching=True,
        correct_overlapping_cells=False,
        sort_row_col_indexes=True,
    )
    latency_sec = time.perf_counter() - t0
    latency_ms = latency_sec * 1000

    INFERENCE_LATENCY.observe(latency_sec)
    TABLES_PER_REQUEST.observe(len(multi_tf_output))

    tables: list[TableResult] = []
    for t, tf_output in enumerate(multi_tf_output):
        tf_responses = tf_output["tf_responses"]
        predict_details = tf_output["predict_details"]
        cells = []
        for r in tf_responses:
            bbox = r.get("bbox", {})
            if isinstance(bbox, dict):
                b = Bbox(l=bbox["l"], t=bbox["t"], r=bbox["r"], b=bbox["b"])
            else:
                b = Bbox(l=0, t=0, r=0, b=0)
            cells.append(
                TableCell(
                    bbox=b,
                    start_row_offset_idx=r.get("start_row_offset_idx", 0),
                    end_row_offset_idx=r.get("end_row_offset_idx", 0),
                    start_col_offset_idx=r.get("start_col_offset_idx", 0),
                    end_col_offset_idx=r.get("end_col_offset_idx", 0),
                    row_span=r.get("row_span", 1),
                    col_span=r.get("col_span", 1),
                    column_header=r.get("column_header", False),
                    row_header=r.get("row_header", False),
                    row_section=r.get("row_section", False),
                    text=_extract_text_from_cell(r),
                )
            )
        tables.append(
            TableResult(
                table_index=t,
                num_rows=predict_details.get("num_rows", 0),
                num_cols=predict_details.get("num_cols", 0),
                cells=cells,
            )
        )

    return PredictResponse(
        request_id=request_id,
        latency_ms=round(latency_ms, 2),
        tables=tables,
    )
