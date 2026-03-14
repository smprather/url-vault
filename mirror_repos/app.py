from __future__ import annotations

from pathlib import Path
import time

from mirror_repos.config import ConfigError, load_config
from mirror_repos.sync import sync_repositories


def run(config_path: Path | None = None, *, once: bool = False) -> int:
    selected_config_path = config_path or Path("config.yaml")

    try:
        config = load_config(selected_config_path)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 1

    exit_code = 0
    while True:
        results = sync_repositories(config)
        for result in results:
            status = "OK" if result.success else "ERROR"
            print(
                f"[{status}] {result.action} {result.url} -> {result.local_path} :: {result.detail}"
            )

        iteration_exit_code = 0 if all(result.success for result in results) else 1
        exit_code = max(exit_code, iteration_exit_code)

        if once:
            return exit_code

        print(
            f"Waiting {format_update_period_seconds(config.update_period.total_seconds())} before the next update cycle."
        )
        try:
            time.sleep(config.update_period.total_seconds())
        except KeyboardInterrupt:
            print("Stopping update loop.")
            return exit_code


def format_update_period_seconds(total_seconds: float) -> str:
    seconds = int(total_seconds)
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"

