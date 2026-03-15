from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import shutil
from uuid import uuid4

import pytest
import yaml

from url_vault.request_log import record_url_miss


@contextmanager
def workspace_tmp_dir(prefix: str):
    root = Path.cwd() / ".test-artifacts" / f"{prefix}-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_record_url_miss_creates_and_updates_yaml_log() -> None:
    with workspace_tmp_dir("request-log") as tmp_path:
        log_path = tmp_path / "requests" / "offline-misses.yaml"

        record_url_miss(
            log_path,
            "https://example.com/archive.tar.gz",
            request_method="GET",
            seen_at=datetime(2026, 3, 15, 18, 0, tzinfo=timezone.utc),
        )
        record_url_miss(
            log_path,
            "https://example.com/archive.tar.gz",
            request_method="HEAD",
            seen_at=datetime(2026, 3, 15, 19, 0, tzinfo=timezone.utc),
        )

        document = yaml.safe_load(log_path.read_text(encoding="utf-8"))

        assert document["kind"] == "url"
        assert document["requests"] == [
            {
                "url": "https://example.com/archive.tar.gz",
                "count": 2,
                "first_seen": "2026-03-15T18:00:00Z",
                "last_seen": "2026-03-15T19:00:00Z",
                "last_method": "HEAD",
            }
        ]


def test_record_url_miss_rejects_non_mapping_logs() -> None:
    with workspace_tmp_dir("request-log-invalid") as tmp_path:
        log_path = tmp_path / "requests" / "offline-misses.yaml"
        log_path.parent.mkdir(parents=True)
        log_path.write_text("- bad\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Top-level request log must be a mapping"):
            record_url_miss(
                log_path,
                "https://example.com/archive.tar.gz",
                request_method="GET",
            )
