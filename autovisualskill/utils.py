import os
import re
from typing import Any


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str, *, default: str = "artifact", suffix: str = "") -> str:
    stem, ext = os.path.splitext(name.strip())
    if suffix and not ext:
        ext = suffix
    elif suffix and ext.lower() != suffix.lower():
        ext = suffix
    safe_stem = _SAFE_FILENAME_RE.sub("_", stem).strip("._-")
    if not safe_stem:
        safe_stem = default
    return f"{safe_stem[:80]}{ext}"


def append_records(state: dict[str, Any], key: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = state.get(key, [])
    if not isinstance(existing, list):
        existing = []
    return [*existing, *records]


def provenance_record(node: str, action: str, **details: Any) -> dict[str, Any]:
    return {"node": node, "action": action, "details": details}


def issue_record(node: str, message: str, **details: Any) -> dict[str, Any]:
    return {"node": node, "message": message, "details": details}
