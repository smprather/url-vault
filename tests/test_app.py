from __future__ import annotations

from datetime import timedelta
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from url_vault.app import run
from url_vault.config import AppConfig
from url_vault.config import MirrorItemConfig
from url_vault.sync import SyncResult


def make_config() -> AppConfig:
    item = MirrorItemConfig(
        kind="git",
        url="https://github.com/org/example.git",
        relative_path=PurePosixPath("https/github.com/org/example.git"),
        local_path=Path("mirrors/https/github.com/org/example.git"),
        options={},
    )
    return AppConfig(
        update_period=timedelta(hours=24),
        max_parallel=4,
        destination_dir=Path("mirrors"),
        items=[item],
    )


def test_run_once_exits_after_single_cycle() -> None:
    config = make_config()
    results = [
        SyncResult(
            kind=config.items[0].kind,
            url=config.items[0].url,
            local_path=config.items[0].local_path,
            action="clone",
            success=True,
            detail="ok",
        )
    ]

    with patch("url_vault.app.load_config", return_value=config), patch(
        "url_vault.app.sync_repositories", return_value=results
    ) as sync_mock, patch("builtins.print") as print_mock:
        exit_code = run(once=True)

    assert exit_code == 0
    assert sync_mock.call_count == 1
    print_mock.assert_called_once()


def test_run_loop_sleeps_until_interrupted() -> None:
    config = make_config()
    results = [
        SyncResult(
            kind=config.items[0].kind,
            url=config.items[0].url,
            local_path=config.items[0].local_path,
            action="update",
            success=True,
            detail="ok",
        )
    ]

    with patch("url_vault.app.load_config", return_value=config), patch(
        "url_vault.app.sync_repositories", return_value=results
    ) as sync_mock, patch(
        "url_vault.app.time.sleep", side_effect=KeyboardInterrupt
    ) as sleep_mock, patch("builtins.print") as print_mock:
        exit_code = run(once=False)

    assert exit_code == 0
    assert sync_mock.call_count == 1
    sleep_mock.assert_called_once_with(24 * 60 * 60)
    assert print_mock.call_count == 3
