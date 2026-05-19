# utils.py — shared helpers

import logging
import os
from datetime import datetime
from config import REPORT_DIR


def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s — %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    return logging.getLogger(__name__)


def ensure_report_dir():
    if not os.path.exists(REPORT_DIR):
        os.makedirs(REPORT_DIR)


def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_filename_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def severity_color(severity):
    colors = {
        "Critical": "#cc0000",
        "High":     "#e65c00",
        "Medium":   "#ccaa00",
        "Low":      "#2d862d"
    }
    return colors.get(severity, "#333333")