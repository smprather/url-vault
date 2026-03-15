from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import subprocess
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from url_vault.config import AppConfig, MirrorItemConfig


@dataclass(frozen=True)
class SyncResult:
    kind: str
    url: str
    local_path: Path
    action: str
    success: bool
    detail: str


def sync_repositories(config: AppConfig) -> list[SyncResult]:
    with ThreadPoolExecutor(max_workers=config.max_parallel) as executor:
        return list(executor.map(sync_item, config.items))


def sync_item(item: MirrorItemConfig) -> SyncResult:
    if item.kind == "git":
        return sync_git_item(item)
    if item.kind == "url":
        return sync_url_item(item)
    return SyncResult(
        kind=item.kind,
        url=item.url,
        local_path=item.local_path,
        action="skip",
        success=False,
        detail=f"Unsupported mirror kind: {item.kind}",
    )


def sync_git_item(item: MirrorItemConfig) -> SyncResult:
    item.local_path.parent.mkdir(parents=True, exist_ok=True)

    if item.local_path.exists():
        command = [
            "git",
            "-C",
            str(item.local_path),
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
            item.url,
            str(item.local_path),
        ]
        action = "clone"

    completed = _run_subprocess(command)
    if completed.returncode != 0:
        return SyncResult(
            kind=item.kind,
            url=item.url,
            local_path=item.local_path,
            action=action,
            success=False,
            detail=_completed_process_output(completed),
        )

    metadata_update = _run_subprocess(
        ["git", "--git-dir", str(item.local_path), "update-server-info"]
    )
    if metadata_update.returncode != 0:
        return SyncResult(
            kind=item.kind,
            url=item.url,
            local_path=item.local_path,
            action=action,
            success=False,
            detail=f"{_completed_process_output(completed)} | update-server-info failed: {_completed_process_output(metadata_update)}",
        )

    return SyncResult(
        kind=item.kind,
        url=item.url,
        local_path=item.local_path,
        action=action,
        success=True,
        detail="ok",
    )


def sync_url_item(item: MirrorItemConfig) -> SyncResult:
    item.local_path.parent.mkdir(parents=True, exist_ok=True)
    action = "refresh" if item.local_path.exists() else "download"

    try:
        request = Request(item.url, method="GET")
        with urlopen(request) as response:
            body = response.read()
    except HTTPError as exc:
        return SyncResult(
            kind=item.kind,
            url=item.url,
            local_path=item.local_path,
            action=action,
            success=False,
            detail=f"HTTP {exc.code}: {exc.reason}",
        )
    except URLError as exc:
        return SyncResult(
            kind=item.kind,
            url=item.url,
            local_path=item.local_path,
            action=action,
            success=False,
            detail=str(exc.reason),
        )

    with NamedTemporaryFile(delete=False, dir=item.local_path.parent) as handle:
        handle.write(body)
        temporary_path = Path(handle.name)

    temporary_path.replace(item.local_path)
    return SyncResult(
        kind=item.kind,
        url=item.url,
        local_path=item.local_path,
        action=action,
        success=True,
        detail="ok",
    )


def _run_subprocess(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=str(exc))


def _completed_process_output(completed: subprocess.CompletedProcess[str]) -> str:
    output = (completed.stdout or completed.stderr).strip()
    if not output:
        return "ok"
    return output
