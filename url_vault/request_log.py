from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import yaml


def record_url_miss(
    log_path: Path,
    url: str,
    *,
    request_method: str,
    seen_at: datetime | None = None,
) -> dict[str, object]:
    timestamp = _format_timestamp(seen_at or datetime.now(timezone.utc))
    document = _load_request_document(log_path)
    requests = document.setdefault("requests", [])
    if not isinstance(requests, list):
        raise ValueError(f"'requests' must be a list in {log_path}")

    existing_entry: dict[str, object] | None = None
    for entry in requests:
        if not isinstance(entry, dict):
            continue
        if entry.get("url") == url:
            existing_entry = entry
            break

    if existing_entry is None:
        existing_entry = {
            "url": url,
            "count": 0,
            "first_seen": timestamp,
        }
        requests.append(existing_entry)

    current_count = existing_entry.get("count", 0)
    if isinstance(current_count, bool) or not isinstance(current_count, int):
        current_count = 0

    existing_entry["count"] = current_count + 1
    existing_entry["last_seen"] = timestamp
    existing_entry["last_method"] = request_method

    _write_request_document(log_path, document)
    return existing_entry


def _load_request_document(log_path: Path) -> dict[str, object]:
    if not log_path.exists():
        return {"kind": "url", "requests": []}

    with log_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)

    if loaded is None:
        return {"kind": "url", "requests": []}
    if not isinstance(loaded, dict):
        raise ValueError(f"Top-level request log must be a mapping in {log_path}")

    loaded.setdefault("kind", "url")
    return loaded


def _write_request_document(log_path: Path, document: dict[str, object]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        delete=False,
        dir=log_path.parent,
        encoding="utf-8",
    ) as handle:
        yaml.safe_dump(document, handle, sort_keys=False)
        temporary_path = Path(handle.name)

    temporary_path.replace(log_path)


def _format_timestamp(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")
