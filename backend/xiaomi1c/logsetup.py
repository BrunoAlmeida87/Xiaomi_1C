"""Logs detalhados com redação automática de segredos."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_PATTERNS = [
    re.compile(r"\b[0-9a-fA-F]{32}\b"),  # tokens miIO
    re.compile(r"(serviceToken|ssecurity|passToken|token)(['\"]?\s*[:=]\s*['\"]?)([^'\",;\s}]+)", re.I),
]


def redact(text: str) -> str:
    text = _PATTERNS[0].sub("«token-oculto»", text)
    return _PATTERNS[1].sub(lambda m: f"{m.group(1)}{m.group(2)}«oculto»", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        record.msg, record.args = redact(msg), None
        return True


def setup_logging(log_dir: Path, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    flt = RedactingFilter()
    fh = RotatingFileHandler(log_dir / "xiaomi1c.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    sh = logging.StreamHandler()
    for h in (fh, sh):
        h.setFormatter(fmt)
        h.addFilter(flt)
        root.addHandler(h)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
