"""Logging helpers."""

from __future__ import annotations

import logging
import logging.config

from src.utils.config import load_yaml_config


def configure_logging() -> logging.Logger:
    try:
        logging.config.dictConfig(load_yaml_config("logging"))
    except Exception:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
    return logging.getLogger("gip")
