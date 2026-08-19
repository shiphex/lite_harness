import logging

import pytest

from observability.logger import LOGGER_NAME, configure_logging


@pytest.fixture
def clean_lite_harness_logger():
    logger = logging.getLogger(LOGGER_NAME)
    old_handlers = list(logger.handlers)
    old_level = logger.level
    old_propagate = logger.propagate
    for handler in old_handlers:
        logger.removeHandler(handler)
    try:
        yield logger
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        for handler in old_handlers:
            logger.addHandler(handler)
        logger.setLevel(old_level)
        logger.propagate = old_propagate


def test_configure_logging_is_idempotent_and_updates_level(
    clean_lite_harness_logger,
):
    logger = clean_lite_harness_logger

    configure_logging(logging.INFO)
    assert len(logger.handlers) == 1
    assert logger.level == logging.INFO
    assert logger.handlers[0].level == logging.INFO
    assert logger.handlers[0].formatter is not None
    assert "%(levelname)s" in logger.handlers[0].formatter._fmt

    configure_logging(logging.DEBUG)
    assert len(logger.handlers) == 1
    assert logger.level == logging.DEBUG
    assert logger.handlers[0].level == logging.DEBUG
    assert logger.handlers[0].formatter is not None
    assert "%(message)s" in logger.handlers[0].formatter._fmt
