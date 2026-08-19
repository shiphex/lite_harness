# observability/logger.py

from __future__ import annotations

import logging
import sys


LOGGER_NAME = "lite_harness"


def configure_logging(
    level: int = logging.INFO,
) -> None:
    """Configure lite_harness logging.

    应只在程序入口调用一次。
    """
    logger = logging.getLogger(LOGGER_NAME)

    # 防止重复初始化
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s "
            "[%(levelname)s] "
            "%(name)s: "
            "%(message)s"
        ),
        datefmt="%H:%M:%S",
    )

    if not logger.handlers:
        logger.addHandler(logging.StreamHandler(sys.stderr))

    for handler in logger.handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)

    # 不再交给 root logger 重复处理
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under lite_harness namespace."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
