#
# Demo for TableFormer predictor using local weights from weights/tableformer/
#
# Usage (run from docling-ibm-models/):
#   python -m demo.demo_tf_predictor -i tests/test_data/samples -v viz/
#
import argparse
import json
import logging
import os
import sys
from pathlib import Path

import cv2
from PIL import Image, ImageDraw

from docling_ibm_models.tableformer.data_management.tf_predictor import TFPredictor

# Project root = parent of demo/
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="TableFormer predictor demo (local weights)")
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to config JSON (default: weights/tableformer/tm_config.json)",
    )
    parser.add_argument(
        "-i",
        "--input_dir",
        default="tests/test_data/samples",
        help="Directory with PNG images and IOCR JSON files",
    )
    parser.add_argument(
        "-v",
        "--viz_dir",
        default="viz/",
        help="Directory to save visualizations",
    )
    parser.add_argument(
        "-d",
        "--device",
        default="cpu",
        help="Device: cpu or cuda",
    )
    parser.add_argument(
        "-n",
        "--num_threads",
        type=int,
        default=4,
        help="Number of threads for CPU",
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger("TFPredictor")

    # Config path
    config_path = args.config or str(PROJECT_ROOT / "weights" / "tableformer" / "tm_config.json")
    if not os.path.isfile(config_path):
        logger.error("Config not found: %s", config_path)
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    # Resolve save_dir to absolute path
    weights_dir = PROJECT_ROOT / "weights" / "tableformer"
    config["model"]["save_dir"] = str(weights_dir)

    if not (weights_dir / "tableformer_accurate.safetensors").exists():
        logger.error("Weights not found: %s", weights_dir / "tableformer_accurate.safetensors")
        sys.exit(1)

    # Test data: same structure as test_tf_predictor
    docling_api_data = {
        "table_jsons": [
            str(PROJECT_ROOT / "tests/test_data/samples/ADS.2007.page_123.png_iocr.parse_format.json"),
            str(PROJECT_ROOT / "tests/test_data/samples/PHM.2013.page_30.png_iocr.parse_format.json"),
            str(PROJECT_ROOT / "tests/test_data/samples/empty_iocr.png.json"),
        ],
        "png_images": [
            str(PROJECT_ROOT / "tests/test_data/samples/ADS.2007.page_123.png"),
            str(PROJECT_ROOT / "tests/test_data/samples/PHM.2013.page_30.png"),
            str(PROJECT_ROOT / "tests/test_data/samples/empty_iocr.png"),
        ],
        "table_bboxes": [
            [[178, 748, 1061, 976], [177, 1163, 1062, 1329]],
            [[100, 186, 1135, 525]],
            [[178, 748, 1061, 976], [177, 1163, 1062, 1329]],
        ],
    }

    # Check test files exist
    for fn in docling_api_data["table_jsons"] + docling_api_data["png_images"]:
        if not os.path.isfile(fn):
            logger.warning("Test file not found: %s", fn)

    logger.info("Loading TFPredictor from %s", config["model"]["save_dir"])
    predictor = TFPredictor(config, device=args.device, num_threads=args.num_threads)

    viz_dir = Path(args.viz_dir)
    viz_dir.mkdir(parents=True, exist_ok=True)

    iocr_pages = []
    for table_json_fn, png_image_fn, table_bboxes_b in zip(
        docling_api_data["table_jsons"],
        docling_api_data["png_images"],
        docling_api_data["table_bboxes"],
    ):
        if not os.path.isfile(table_json_fn) or not os.path.isfile(png_image_fn):
            continue
        with open(table_json_fn) as fp:
            iocr_page_raw = json.load(fp)
            iocr_page = iocr_page_raw["pages"][0]
        iocr_page["image"] = cv2.imread(png_image_fn)
        iocr_page["png_image_fn"] = png_image_fn
        iocr_page["table_bboxes"] = table_bboxes_b
        iocr_pages.append(iocr_page)

    for iocr_page in iocr_pages:
        table_bboxes = iocr_page["table_bboxes"]
        logger.info("Predicting: %s", os.path.basename(iocr_page["png_image_fn"]))

        multi_tf_output = predictor.multi_table_predict(
            iocr_page,
            table_bboxes,
            do_matching=True,
            correct_overlapping_cells=False,
            sort_row_col_indexes=True,
        )

        for t, tf_output in enumerate(multi_tf_output):
            tf_responses = tf_output["tf_responses"]
            predict_details = tf_output["predict_details"]
            logger.info("  Table %d: %d cells", t, len(tf_responses))

            # Visualization
            img = Image.open(iocr_page["png_image_fn"])
            img1 = ImageDraw.Draw(img)

            xt0, yt0 = table_bboxes[t][0], table_bboxes[t][1]
            xt1, yt1 = table_bboxes[t][2], table_bboxes[t][3]
            img1.rectangle(((xt0, yt0), (xt1, yt1)), outline="pink", width=5)

            for response in tf_responses:
                x0 = response["bbox"]["l"] - 2
                y0 = response["bbox"]["t"] - 2
                x1 = response["bbox"]["r"] + 2
                y1 = response["bbox"]["b"] + 2
                if response.get("column_header"):
                    img1.rectangle(((x0, y0), (x1, y1)), outline="blue", width=2)
                elif response.get("row_header"):
                    img1.rectangle(((x0, y0), (x1, y1)), outline="magenta", width=2)
                else:
                    img1.rectangle(((x0, y0), (x1, y1)), outline="black", width=1)

            png_bfn = os.path.basename(iocr_page["png_image_fn"])
            viz_fn = viz_dir / f"tf_{png_bfn.replace('.png', '')}_{t}.png"
            img.save(viz_fn)
            logger.info("  Saved: %s", viz_fn)

    logger.info("Done. Visualizations in %s", viz_dir)


if __name__ == "__main__":
    main()
