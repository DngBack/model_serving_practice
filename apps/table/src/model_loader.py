"""
Load and manage TFPredictor (TableFormer) from docling-ibm-models.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_predictor = None


def _resolve_weights_dir() -> str:
    """
    Resolve TableFormer weights directory.
    Uses TABLE_WEIGHTS_DIR if set, otherwise downloads from HuggingFace.
    """
    weights_dir = os.environ.get("TABLE_WEIGHTS_DIR", "").strip()
    if weights_dir and Path(weights_dir).exists():
        config_path = Path(weights_dir) / "tm_config.json"
        if config_path.exists():
            logger.info("Using table weights from TABLE_WEIGHTS_DIR: %s", weights_dir)
            return weights_dir

    from huggingface_hub import snapshot_download

    logger.info("Downloading TableFormer weights from HuggingFace")
    repo_path = snapshot_download(
        repo_id="ds4sd/docling-models",
        allow_patterns=["model_artifacts/tableformer/accurate/*"],
    )
    weights_dir = os.path.join(repo_path, "model_artifacts", "tableformer", "accurate")
    return weights_dir


def _load_config(weights_dir: str) -> dict:
    """Load and patch config for TFPredictor."""
    config_path = Path(weights_dir) / "tm_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path) as f:
        config = json.load(f)

    config["model"]["save_dir"] = weights_dir
    return config


def get_predictor():
    """Get or create TFPredictor singleton."""
    global _predictor

    if _predictor is None:
        from docling_ibm_models.tableformer.data_management.tf_predictor import TFPredictor

        weights_dir = _resolve_weights_dir()
        config = _load_config(weights_dir)
        device = os.environ.get("TABLE_DEVICE", "cpu").lower()
        num_threads = int(os.environ.get("TABLE_NUM_THREADS", "4"))

        logger.info(
            "Loading TFPredictor with device=%s, num_threads=%s, weights_dir=%s",
            device,
            num_threads,
            weights_dir,
        )
        _predictor = TFPredictor(
            config,
            device=device,
            num_threads=num_threads,
        )
        logger.info("TFPredictor loaded")

    return _predictor


def is_ready() -> bool:
    return _predictor is not None
