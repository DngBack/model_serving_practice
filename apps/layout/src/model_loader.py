"""
Load and manage LayoutPredictor from docling-ibm-models.
"""

import logging
import os
from pathlib import Path

from huggingface_hub import snapshot_download

logger = logging.getLogger(__name__)

_predictor = None


def _resolve_layout_artifact_path() -> str:
    artifact_path = os.environ.get("LAYOUT_ARTIFACT_PATH", "").strip()
    if artifact_path and Path(artifact_path).exists():
        logger.info("Using layout model from LAYOUT_ARTIFACT_PATH: %s", artifact_path)
        return artifact_path

    hf_repo = os.environ.get(
        "LAYOUT_HF_REPO",
        "ds4sd/docling-layout-heron",
    )
    logger.info("Downloading layout model from HuggingFace: %s", hf_repo)
    return snapshot_download(repo_id=hf_repo)


def get_predictor():
    """Get or create LayoutPredictor singleton."""
    global _predictor

    if _predictor is None:
        from docling_ibm_models.layoutmodel.layout_predictor import LayoutPredictor

        device = os.environ.get("LAYOUT_DEVICE", "cpu").lower()
        num_threads = int(os.environ.get("LAYOUT_NUM_THREADS", "4"))
        threshold = float(os.environ.get("LAYOUT_THRESHOLD", "0.3"))
        artifact_path = _resolve_layout_artifact_path()

        logger.info(
            "Loading LayoutPredictor with device=%s, num_threads=%s, threshold=%s",
            device,
            num_threads,
            threshold,
        )
        _predictor = LayoutPredictor(
            artifact_path=artifact_path,
            device=device,
            num_threads=num_threads,
            base_threshold=threshold,
        )
        logger.info("LayoutPredictor loaded: %s", _predictor.info())

    return _predictor


def is_ready() -> bool:
    return _predictor is not None
