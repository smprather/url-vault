from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
from uuid import uuid4

import pytest

from mirror_repos.config import ConfigError, derive_relative_repo_path, load_config


@contextmanager
def workspace_tmp_dir(prefix: str):
    root = Path.cwd() / ".test-artifacts" / f"{prefix}-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_load_config_derives_local_path_from_https_url() -> None:
    with workspace_tmp_dir("config-load") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "max_parallel: 4",
                    "destination_dir: mirrors",
                    "repositories:",
                    "  - url: https://github.com/org/example.git",
                    "    enabled: true",
                ]
            ),
            encoding="utf-8",
        )

        config = load_config(config_path)

        assert config.update_period.total_seconds() == 24 * 60 * 60
        assert config.max_parallel == 4
        assert config.destination_dir == (tmp_path / "mirrors").resolve()
        assert len(config.repositories) == 1
        repository = config.repositories[0]
        assert str(repository.relative_path) == "org/example.git"
        assert repository.local_path == (tmp_path / "mirrors" / "org" / "example.git").resolve()
        assert repository.options == {"enabled": True}


def test_derive_relative_repo_path_handles_ssh_github_url() -> None:
    assert str(derive_relative_repo_path("git@github.com:org/example.git")) == "org/example.git"


def test_load_config_rejects_non_mapping_repository_entries() -> None:
    with workspace_tmp_dir("config-non-mapping") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "destination_dir: mirrors",
                    "repositories:",
                    "  - https://github.com/org/example.git",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="repositories\\[0\\]"):
            load_config(config_path)


def test_load_config_requires_repository_url() -> None:
    with workspace_tmp_dir("config-missing-url") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "destination_dir: mirrors",
                    "repositories:",
                    "  - branch: main",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="repositories\\[0\\]\\.url"):
            load_config(config_path)


def test_load_config_rejects_non_github_urls() -> None:
    with workspace_tmp_dir("config-non-github") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "destination_dir: mirrors",
                    "repositories:",
                    "  - url: https://gitlab.com/org/example.git",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="Unsupported repository host"):
            load_config(config_path)


def test_load_config_rejects_invalid_update_period() -> None:
    with workspace_tmp_dir("config-bad-period") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: sometimes",
                    "destination_dir: mirrors",
                    "repositories:",
                    "  - url: https://github.com/org/example.git",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="update_period"):
            load_config(config_path)


def test_load_config_defaults_max_parallel_to_four() -> None:
    with workspace_tmp_dir("config-default-max-parallel") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "destination_dir: mirrors",
                    "repositories:",
                    "  - url: https://github.com/org/example.git",
                ]
            ),
            encoding="utf-8",
        )

        config = load_config(config_path)

        assert config.max_parallel == 4


def test_load_config_rejects_invalid_max_parallel() -> None:
    with workspace_tmp_dir("config-bad-max-parallel") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "max_parallel: 0",
                    "destination_dir: mirrors",
                    "repositories:",
                    "  - url: https://github.com/org/example.git",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="max_parallel"):
            load_config(config_path)
