from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import yaml


class ConfigError(ValueError):
    """Raised when the configuration file is invalid."""


@dataclass(frozen=True)
class RepositoryConfig:
    url: str
    relative_path: PurePosixPath
    local_path: Path
    options: dict[str, object]


@dataclass(frozen=True)
class AppConfig:
    update_period: timedelta
    max_parallel: int
    destination_dir: Path
    repositories: list[RepositoryConfig]


def load_config(config_path: Path) -> AppConfig:
    raw_config = _read_yaml(config_path)
    config_dir = config_path.parent.resolve()

    update_period_value = raw_config.get("update_period")
    if not isinstance(update_period_value, str) or not update_period_value.strip():
        raise ConfigError("'update_period' must be a non-empty string")
    update_period = parse_update_period(update_period_value)

    max_parallel_value = raw_config.get("max_parallel", 4)
    max_parallel = parse_max_parallel(max_parallel_value)

    destination_value = raw_config.get("destination_dir")
    if not isinstance(destination_value, str) or not destination_value.strip():
        raise ConfigError("'destination_dir' must be a non-empty string")
    destination_dir = _resolve_path(destination_value, config_dir)

    repositories_value = raw_config.get("repositories")
    if not isinstance(repositories_value, list):
        raise ConfigError("'repositories' must be a list of repository mappings")

    repositories: list[RepositoryConfig] = []
    for index, repository_value in enumerate(repositories_value, start=1):
        repositories.append(
            _parse_repository(
                repository_value=repository_value,
                destination_dir=destination_dir,
                index=index,
            )
        )

    return AppConfig(
        update_period=update_period,
        max_parallel=max_parallel,
        destination_dir=destination_dir,
        repositories=repositories,
    )


def parse_update_period(value: str) -> timedelta:
    match = re.fullmatch(r"\s*(\d+)\s*([smhd])\s*", value)
    if match is None:
        raise ConfigError(
            "'update_period' must use an integer plus unit suffix: s, m, h, or d"
        )

    amount = int(match.group(1))
    unit = match.group(2)
    if amount <= 0:
        raise ConfigError("'update_period' must be greater than zero")

    unit_to_seconds = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 24 * 60 * 60,
    }
    return timedelta(seconds=amount * unit_to_seconds[unit])


def parse_max_parallel(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError("'max_parallel' must be an integer greater than zero")
    if value <= 0:
        raise ConfigError("'max_parallel' must be greater than zero")
    return value


def _read_yaml(config_path: Path) -> dict[str, object]:
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML in {config_path}: {exc}") from exc

    if loaded is None:
        raise ConfigError(f"Config file is empty: {config_path}")
    if not isinstance(loaded, dict):
        raise ConfigError("Top-level config value must be a mapping")
    return loaded


def _resolve_path(path_value: str, config_dir: Path) -> Path:
    expanded = os.path.expandvars(path_value)
    expanded = os.path.expanduser(expanded)
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = config_dir / candidate
    return candidate.resolve()


def _parse_repository(
    repository_value: object,
    destination_dir: Path,
    index: int,
) -> RepositoryConfig:
    if not isinstance(repository_value, dict):
        raise ConfigError(
            f"'repositories[{index - 1}]' must be a mapping with at least a 'url' key"
        )

    url = repository_value.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ConfigError(f"'repositories[{index - 1}].url' must be a non-empty string")

    relative_path = derive_relative_repo_path(url)
    options = {
        key: value for key, value in repository_value.items() if key != "url"
    }

    return RepositoryConfig(
        url=url,
        relative_path=relative_path,
        local_path=destination_dir / Path(relative_path),
        options=options,
    )


def derive_relative_repo_path(url: str) -> PurePosixPath:
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https", "ssh"}:
        if parsed.hostname != "github.com":
            raise ConfigError(f"Unsupported repository host in URL: {url}")
        path = parsed.path
    elif url.startswith("git@github.com:"):
        path = url.removeprefix("git@github.com:")
    else:
        raise ConfigError(f"Unsupported repository URL format: {url}")

    normalized = path.lstrip("/:")
    if not normalized:
        raise ConfigError(f"Repository URL is missing a GitHub path: {url}")

    relative_path = PurePosixPath(normalized)
    if str(relative_path) in {".", ""} or ".." in relative_path.parts:
        raise ConfigError(f"Repository URL produced an invalid local path: {url}")

    return relative_path
