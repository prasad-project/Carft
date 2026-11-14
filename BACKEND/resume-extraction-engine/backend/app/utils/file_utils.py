from __future__ import annotations

import os
import re
from pathlib import Path


def safe_display_name(name) -> str:
    name = os.path.basename(name or "resume")
    name = re.sub(r"[^\w.\- ]", "_", name)[:120]
    return name or "resume"


def ensure_private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def secure_delete(path) -> None:
    if path and Path(path).exists():
        try:
            Path(path).unlink()
        except OSError:
            pass
