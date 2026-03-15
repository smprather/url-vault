from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import yaml

from url_vault.pathing import derive_relative_path


class ConfigError(ValueError):
    """Raised when the configuration file is invalid."""


@dataclass(frozen=True)
class MirrorItemConfig:
    kind: str
    url: str
    relative_path: Path
    local_path: Path
    options: dict[str, object]


@dataclass(frozen=True)
class AppConfig:
    update_period: timedelta
    max_parallel: int
    destination_dir: Path
    items: list[MirrorItemConfig]

    @property
    def repositories(self) -> list[MirrorItemConfig]:
        return self.items


def load_config(config_path: Path) -> AppConfig:
    raw_config = _read_yaml_mapping(config_path)
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

    items: list[MirrorItemConfig] = []

    items.extend(
        _parse_entry_list(
            entries_value=raw_config.get("prefetch", []),
            destination_dir=destination_dir,
            context="prefetch",
            default_kind=None,
        )
    )
    items.extend(
        _parse_entry_list(
            entries_value=raw_config.get("repositories", []),
            destination_dir=destination_dir,
            context="repositories",
            default_kind="git",
        )
    )

    prefetch_files = _parse_file_list(raw_config.get("prefetch_files", []), "prefetch_files")
    for relative_file_path in prefetch_files:
        prefetch_path = _resolve_path(relative_file_path, config_dir)
        prefetch_config = _read_yaml_mapping(prefetch_path)
        items.extend(
            _parse_entry_list(
                entries_value=prefetch_config.get("entries", []),
                destination_dir=destination_dir,
                context=str(prefetch_path),
                default_kind=_parse_default_kind(prefetch_config.get("kind"), None, str(prefetch_path)),
            )
        )

    request_files = _parse_file_list(raw_config.get("request_files", []), "request_files")
    for relative_file_path in request_files:
        request_path = _resolve_path(relative_file_path, config_dir)
        request_config = _read_yaml_mapping(request_path, missing_ok=True)
        if request_config is None:
            continue
        items.extend(
            _parse_entry_list(
                entries_value=request_config.get("requests", []),
                destination_dir=destination_dir,
                context=str(request_path),
                default_kind=_parse_default_kind(request_config.get("kind"), "url", str(request_path)),
            )
        )

    return AppConfig(
        update_period=update_period,
        max_parallel=max_parallel,
        destination_dir=destination_dir,
        items=_dedupe_items(items),
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


def derive_relative_repo_path(url: str) -> Path:
    return Path(derive_relative_path("git", url))


def derive_relative_url_path(url: str) -> Path:
    return Path(derive_relative_path("url", url))


RepositoryConfig = MirrorItemConfig


def _read_yaml_mapping(config_path: Path, *, missing_ok: bool = False) -> dict[str, object] | None:
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        if missing_ok:
            return None
        raise ConfigError(f"Config file not found: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML in {config_path}: {exc}") from exc

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"Top-level config value must be a mapping in {config_path}")
    return loaded


def _resolve_path(path_value: str, config_dir: Path) -> Path:
    expanded = os.path.expandvars(path_value)
    expanded = os.path.expanduser(expanded)
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = config_dir / candidate
    return candidate.resolve()


def _parse_file_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ConfigError(f"'{field_name}' must be a list of file paths")

    file_paths: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"'{field_name}[{index}]' must be a non-empty string path")
        file_paths.append(item)
    return file_paths


def _parse_default_kind(value: object, fallback: str | None, context: str) -> str | None:
    if value is None:
        return fallback
    if not isinstance(value, str) or value not in {"git", "url"}:
        raise ConfigError(f"'{context}.kind' must be 'git' or 'url'")
    return value


def _parse_entry_list(
    entries_value: object,
    destination_dir: Path,
    context: str,
    default_kind: str | None,
) -> list[MirrorItemConfig]:
    if not isinstance(entries_value, list):
        raise ConfigError(f"'{context}' must be a list of entry mappings")

    items: list[MirrorItemConfig] = []
    for index, entry_value in enumerate(entries_value):
        items.append(
            _parse_entry(
                entry_value=entry_value,
                destination_dir=destination_dir,
                context=f"{context}[{index}]",
                default_kind=default_kind,
            )
        )
    return items


def _parse_entry(
    entry_value: object,
    destination_dir: Path,
    context: str,
    default_kind: str | None,
) -> MirrorItemConfig:
    if not isinstance(entry_value, dict):
        raise ConfigError(f"'{context}' must be a mapping with at least 'url'")

    kind_value = entry_value.get("kind", default_kind)
    if not isinstance(kind_value, str) or kind_value not in {"git", "url"}:
        raise ConfigError(f"'{context}.kind' must be 'git' or 'url'")

    url = entry_value.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ConfigError(f"'{context}.url' must be a non-empty string")

    try:
        relative_path = Path(derive_relative_path(kind_value, url))
    except ValueError as exc:
        raise ConfigError(f"'{context}.url' is invalid: {exc}") from exc

    options = {
        key: value
        for key, value in entry_value.items()
        if key not in {"kind", "url"}
    }

    return MirrorItemConfig(
        kind=kind_value,
        url=url,
        relative_path=relative_path,
        local_path=(destination_dir / relative_path).resolve(),
        options=options,
    )


def _dedupe_items(items: list[MirrorItemConfig]) -> list[MirrorItemConfig]:
    deduped: list[MirrorItemConfig] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.kind, item.url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
