from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path, PurePosixPath
import shutil
import subprocess
from unittest.mock import patch
from uuid import uuid4

from mirror_repos.config import AppConfig, RepositoryConfig
from mirror_repos.sync import SyncResult
from mirror_repos.sync import sync_repositories


@contextmanager
def workspace_tmp_dir(prefix: str):
    root = Path.cwd() / ".test-artifacts" / f"{prefix}-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_sync_repositories_clones_missing_mirrors() -> None:
    with workspace_tmp_dir("sync-clone") as tmp_path:
        calls: list[list[str]] = []

        def fake_run(
            command: list[str],
            check: bool,
            capture_output: bool,
            text: bool,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="cloned", stderr="")

        repository = RepositoryConfig(
            url="https://github.com/org/example.git",
            relative_path=PurePosixPath("org/example.git"),
            local_path=tmp_path / "mirrors" / "org" / "example.git",
            options={},
        )
        config = AppConfig(
            update_period=timedelta(hours=24),
            max_parallel=4,
            destination_dir=tmp_path / "mirrors",
            repositories=[repository],
        )

        with patch("mirror_repos.sync.subprocess.run", new=fake_run):
            results = sync_repositories(config)

        assert calls == [
            [
                "git",
                "clone",
                "--mirror",
                "https://github.com/org/example.git",
                str(tmp_path / "mirrors" / "org" / "example.git"),
            ]
        ]
        assert results[0].success is True
        assert results[0].action == "clone"


def test_sync_repositories_updates_existing_mirrors() -> None:
    with workspace_tmp_dir("sync-update") as tmp_path:
        calls: list[list[str]] = []
        existing_repo = tmp_path / "mirrors" / "org" / "example.git"
        existing_repo.mkdir(parents=True)

        def fake_run(
            command: list[str],
            check: bool,
            capture_output: bool,
            text: bool,
        ) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="updated", stderr="")

        repository = RepositoryConfig(
            url="https://github.com/org/example.git",
            relative_path=PurePosixPath("org/example.git"),
            local_path=existing_repo,
            options={},
        )
        config = AppConfig(
            update_period=timedelta(hours=24),
            max_parallel=4,
            destination_dir=tmp_path / "mirrors",
            repositories=[repository],
        )

        with patch("mirror_repos.sync.subprocess.run", new=fake_run):
            results = sync_repositories(config)

        assert calls == [
            [
                "git",
                "-C",
                str(existing_repo),
                "remote",
                "update",
                "--prune",
            ]
        ]
        assert results[0].success is True
        assert results[0].action == "update"


def test_sync_repositories_uses_configured_parallelism() -> None:
    repository_a = RepositoryConfig(
        url="https://github.com/org/example-a.git",
        relative_path=PurePosixPath("org/example-a.git"),
        local_path=Path("mirrors/org/example-a.git"),
        options={},
    )
    repository_b = RepositoryConfig(
        url="https://github.com/org/example-b.git",
        relative_path=PurePosixPath("org/example-b.git"),
        local_path=Path("mirrors/org/example-b.git"),
        options={},
    )
    config = AppConfig(
        update_period=timedelta(hours=24),
        max_parallel=4,
        destination_dir=Path("mirrors"),
        repositories=[repository_a, repository_b],
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
                    url=repo.url,
                    local_path=repo.local_path,
                    action="clone",
                    success=True,
                    detail="ok",
                )
                for repo in repos
            ]

    with patch("mirror_repos.sync.ThreadPoolExecutor", new=FakeExecutor):
        results = sync_repositories(config)

    assert captured["max_workers"] == 4
    assert captured["repos"] == [repository_a, repository_b]
    assert [result.url for result in results] == [repository_a.url, repository_b.url]
