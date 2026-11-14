"""Logging that never writes resume content. A redaction filter masks emails/phones as a safety net;
the code itself also never logs document text."""
from __future__ import annotations

import logging
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        msg = _EMAIL.sub("[email]", msg)
        msg = _PHONE.sub("[phone]", msg)
        record.msg, record.args = msg, ()
        return True


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("resume")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        handler.addFilter(RedactFilter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


log = setup_logging()
