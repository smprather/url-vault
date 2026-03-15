from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
from uuid import uuid4

import pytest

from url_vault.config import ConfigError
from url_vault.config import derive_relative_repo_path
from url_vault.config import derive_relative_url_path
from url_vault.config import load_config
from url_vault.pathing import cache_lookup_paths


@contextmanager
def workspace_tmp_dir(prefix: str):
    root = Path.cwd() / ".test-artifacts" / f"{prefix}-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_load_config_combines_prefetch_and_request_files() -> None:
    with workspace_tmp_dir("config-files") as tmp_path:
        config_path = tmp_path / "config.yaml"
        prefetch_path = tmp_path / "prefetch.d" / "plugins.yaml"
        request_path = tmp_path / "requests" / "offline-misses.yaml"

        prefetch_path.parent.mkdir(parents=True)
        request_path.parent.mkdir(parents=True)

        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "max_parallel: 4",
                    "destination_dir: mirrors",
                    "prefetch_files:",
                    "  - prefetch.d/plugins.yaml",
                    "request_files:",
                    "  - requests/offline-misses.yaml",
                ]
            ),
            encoding="utf-8",
        )
        prefetch_path.write_text(
            "\n".join(
                [
                    "kind: git",
                    "entries:",
                    "  - url: https://github.com/org/example.git",
                    "    enabled: true",
                ]
            ),
            encoding="utf-8",
        )
        request_path.write_text(
            "\n".join(
                [
                    "kind: url",
                    "requests:",
                    "  - url: https://example.com/releases/tool.tar.gz?sha=abc123",
                    "    source: offline-proxy",
                ]
            ),
            encoding="utf-8",
        )

        config = load_config(config_path)

        assert config.update_period.total_seconds() == 24 * 60 * 60
        assert config.max_parallel == 4
        assert config.destination_dir == (tmp_path / "mirrors").resolve()
        assert [item.kind for item in config.items] == ["git", "url"]
        assert (
            config.items[0].relative_path.as_posix()
            == "https/github.com/org/example.git"
        )
        assert config.items[0].options == {"enabled": True}
        assert (
            config.items[1].relative_path.as_posix()
            == "https/example.com/releases/tool.tar.gz/__query__/sha%3Dabc123"
        )
        assert config.items[1].options == {"source": "offline-proxy"}


def test_load_config_skips_missing_request_files() -> None:
    with workspace_tmp_dir("config-missing-request") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "destination_dir: mirrors",
                    "prefetch:",
                    "  - kind: url",
                    "    url: https://example.com/bootstrap.txt",
                    "request_files:",
                    "  - requests/offline-misses.yaml",
                ]
            ),
            encoding="utf-8",
        )

        config = load_config(config_path)

        assert len(config.items) == 1
        assert config.items[0].url == "https://example.com/bootstrap.txt"


def test_load_config_uses_git_default_for_legacy_repositories_key() -> None:
    with workspace_tmp_dir("config-legacy-repos") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "destination_dir: mirrors",
                    "repositories:",
                    "  - url: git@github.com:org/example.git",
                ]
            ),
            encoding="utf-8",
        )

        config = load_config(config_path)

        assert len(config.items) == 1
        assert config.items[0].kind == "git"
        assert (
            config.items[0].relative_path.as_posix()
            == "ssh/github.com/org/example.git"
        )


def test_derive_relative_repo_path_handles_ssh_github_url() -> None:
    assert (
        derive_relative_repo_path("git@github.com:org/example.git").as_posix()
        == "ssh/github.com/org/example.git"
    )


def test_derive_relative_url_path_includes_query_component() -> None:
    assert (
        derive_relative_url_path(
            "https://example.com/archive.tar.gz?sha=deadbeef"
        ).as_posix()
        == "https/example.com/archive.tar.gz/__query__/sha%3Ddeadbeef"
    )


def test_cache_lookup_paths_try_exact_query_before_plain_path() -> None:
    candidates = cache_lookup_paths("https://example.com/archive.tar.gz?sha=deadbeef")

    assert [str(candidate) for candidate in candidates] == [
        "https/example.com/archive.tar.gz/__query__/sha%3Ddeadbeef",
        "https/example.com/archive.tar.gz",
    ]


def test_load_config_rejects_non_mapping_prefetch_entries() -> None:
    with workspace_tmp_dir("config-non-mapping") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "destination_dir: mirrors",
                    "prefetch:",
                    "  - https://example.com/bootstrap.txt",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="prefetch\\[0\\]"):
            load_config(config_path)


def test_load_config_rejects_invalid_update_period() -> None:
    with workspace_tmp_dir("config-bad-period") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: sometimes",
                    "destination_dir: mirrors",
                    "prefetch:",
                    "  - kind: git",
                    "    url: https://github.com/org/example.git",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="update_period"):
            load_config(config_path)


def test_load_config_rejects_invalid_max_parallel() -> None:
    with workspace_tmp_dir("config-bad-max-parallel") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "max_parallel: 0",
                    "destination_dir: mirrors",
                    "prefetch:",
                    "  - kind: git",
                    "    url: https://github.com/org/example.git",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="max_parallel"):
            load_config(config_path)


def test_load_config_rejects_git_urls_with_query_strings() -> None:
    with workspace_tmp_dir("config-query-string") as tmp_path:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "update_period: 24h",
                    "destination_dir: mirrors",
                    "prefetch:",
                    "  - kind: git",
                    "    url: https://github.com/org/example.git?ref=main",
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="query string or fragment"):
            load_config(config_path)
