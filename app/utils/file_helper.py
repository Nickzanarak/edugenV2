import os
import json
from typing import Any


def read_json(path: str, default: Any = None) -> Any:
    """Read a JSON file from local disk (used by tests and offline tooling)."""
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path: str, data: Any):
    """Write a JSON file atomically (used by tests and offline tooling)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
