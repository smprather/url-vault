from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path, PurePosixPath
import shutil
import subprocess
from unittest.mock import patch
from urllib.error import URLError
from uuid import uuid4

from url_vault.config import AppConfig
from url_vault.config import MirrorItemConfig
from url_vault.sync import SyncResult
from url_vault.sync import sync_repositories


@contextmanager
def workspace_tmp_dir(prefix: str):
    root = Path.cwd() / ".test-artifacts" / f"{prefix}-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def make_item(kind: str, url: str, local_path: Path) -> MirrorItemConfig:
    return MirrorItemConfig(
        kind=kind,
        url=url,
        relative_path=PurePosixPath("placeholder"),
        local_path=local_path,
        options={},
    )


def test_sync_repositories_clones_missing_git_mirrors() -> None:
    with workspace_tmp_dir("sync-clone") as tmp_path:
        calls: list[list[str]] = []
        local_path = tmp_path / "mirrors" / "https" / "github.com" / "org" / "example.git"

        def fake_run(
            command: list[str],
            check: bool,
            capture_output: bool,
            text: bool,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

        item = make_item("git", "https://github.com/org/example.git", local_path)
        config = AppConfig(
            update_period=timedelta(hours=24),
            max_parallel=4,
            destination_dir=tmp_path / "mirrors",
            items=[item],
        )

        with patch("url_vault.sync.subprocess.run", new=fake_run):
            results = sync_repositories(config)

        assert calls == [
            [
                "git",
                "clone",
                "--mirror",
                "https://github.com/org/example.git",
                str(local_path),
            ],
            [
                "git",
                "--git-dir",
                str(local_path),
                "update-server-info",
            ],
        ]
        assert results[0].success is True
        assert results[0].action == "clone"


def test_sync_repositories_updates_existing_git_mirrors() -> None:
    with workspace_tmp_dir("sync-update") as tmp_path:
        calls: list[list[str]] = []
        local_path = tmp_path / "mirrors" / "https" / "github.com" / "org" / "example.git"
        local_path.mkdir(parents=True)

        def fake_run(
            command: list[str],
            check: bool,
            capture_output: bool,
            text: bool,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

        item = make_item("git", "https://github.com/org/example.git", local_path)
        config = AppConfig(
            update_period=timedelta(hours=24),
            max_parallel=4,
            destination_dir=tmp_path / "mirrors",
            items=[item],
        )

        with patch("url_vault.sync.subprocess.run", new=fake_run):
            results = sync_repositories(config)

        assert calls == [
            [
                "git",
                "-C",
                str(local_path),
                "remote",
                "update",
                "--prune",
            ],
            [
                "git",
                "--git-dir",
                str(local_path),
                "update-server-info",
            ],
        ]
        assert results[0].success is True
        assert results[0].action == "update"


def test_sync_repositories_downloads_plain_urls() -> None:
    with workspace_tmp_dir("sync-url") as tmp_path:
        local_path = (
            tmp_path
            / "mirrors"
            / "https"
            / "example.com"
            / "archive.tar.gz"
            / "__query__"
            / "sha%3Dabc123"
        )

        class FakeResponse:
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self) -> bytes:
                return b"payload"

        item = make_item(
            "url",
            "https://example.com/archive.tar.gz?sha=abc123",
            local_path,
        )
        config = AppConfig(
            update_period=timedelta(hours=24),
            max_parallel=4,
            destination_dir=tmp_path / "mirrors",
            items=[item],
        )

        with patch("url_vault.sync.urlopen", return_value=FakeResponse()) as urlopen_mock:
            results = sync_repositories(config)

        assert urlopen_mock.call_args.args[0].full_url == item.url
        assert local_path.read_bytes() == b"payload"
        assert results[0].success is True
        assert results[0].action == "download"


def test_sync_repositories_reports_url_download_errors() -> None:
    with workspace_tmp_dir("sync-url-error") as tmp_path:
        item = make_item(
            "url",
            "https://example.com/archive.tar.gz",
            tmp_path / "mirrors" / "https" / "example.com" / "archive.tar.gz",
        )
        config = AppConfig(
            update_period=timedelta(hours=24),
            max_parallel=4,
            destination_dir=tmp_path / "mirrors",
            items=[item],
        )

        with patch("url_vault.sync.urlopen", side_effect=URLError("offline")):
            results = sync_repositories(config)

        assert results[0].success is False
        assert results[0].detail == "offline"


def test_sync_repositories_uses_configured_parallelism() -> None:
    item_a = MirrorItemConfig(
        kind="git",
        url="https://github.com/org/example-a.git",
        relative_path=PurePosixPath("https/github.com/org/example-a.git"),
        local_path=Path("mirrors/https/github.com/org/example-a.git"),
        options={},
    )
    item_b = MirrorItemConfig(
        kind="url",
        url="https://example.com/archive.tar.gz",
        relative_path=PurePosixPath("https/example.com/archive.tar.gz"),
        local_path=Path("mirrors/https/example.com/archive.tar.gz"),
        options={},
    )
    config = AppConfig(
        update_period=timedelta(hours=24),
        max_parallel=4,
        destination_dir=Path("mirrors"),
        items=[item_a, item_b],
    )
    captured: dict[str, object] = {}

    class FakeExecutor:
        def __init__(self, max_workers: int):
            captured["max_workers"] = max_workers

        def __enter__(self) -> FakeExecutor:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def map(self, func, repositories):
            repos = list(repositories)
            captured["repos"] = repos
            return [
                SyncResult(
                    kind=repo.kind,
                    url=repo.url,
                    local_path=repo.local_path,
                    action="sync",
                    success=True,
                    detail="ok",
                )
                for repo in repos
            ]

    with patch("url_vault.sync.ThreadPoolExecutor", new=FakeExecutor):
        results = sync_repositories(config)

    assert captured["max_workers"] == 4
    assert captured["repos"] == [item_a, item_b]
    assert [result.url for result in results] == [item_a.url, item_b.url]
