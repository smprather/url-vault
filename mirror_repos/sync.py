from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mirror_repos.config import AppConfig, RepositoryConfig


@dataclass(frozen=True)
class SyncResult:
    url: str
    local_path: Path
    action: str
    success: bool
    detail: str


def sync_repositories(config: AppConfig) -> list[SyncResult]:
    with ThreadPoolExecutor(max_workers=config.max_parallel) as executor:
        return list(executor.map(sync_repository, config.repositories))


def sync_repository(repository: RepositoryConfig) -> SyncResult:
    repository.local_path.parent.mkdir(parents=True, exist_ok=True)

    if repository.local_path.exists():
        command = [
            "git",
            "-C",
            str(repository.local_path),
            "remote",
            "update",
            "--prune",
        ]
        action = "update"
    else:
        command = [
            "git",
            "clone",
            "--mirror",
            repository.url,
            str(repository.local_path),
        ]
        action = "clone"

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return SyncResult(
            url=repository.url,
            local_path=repository.local_path,
            action=action,
            success=False,
            detail=str(exc),
        )

    output = (completed.stdout or completed.stderr).strip()
    if not output:
        output = "ok"

    return SyncResult(
        url=repository.url,
        local_path=repository.local_path,
        action=action,
        success=completed.returncode == 0,
        detail=output,
    )
