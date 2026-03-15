from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit


def derive_relative_path(kind: str, url: str) -> PurePosixPath:
    if kind == "git":
        return derive_relative_git_path(url)
    if kind == "url":
        return derive_relative_url_path(url)
    raise ValueError(f"Unsupported mirror kind: {kind}")


def derive_relative_git_path(url: str) -> PurePosixPath:
    scp_like = re.fullmatch(r"(?P<user>[^@]+)@(?P<host>[^:]+):(?P<path>.+)", url)
    if scp_like is not None:
        relative_path = PurePosixPath(
            "ssh",
            scp_like.group("host"),
            scp_like.group("path").lstrip("/:"),
        )
        return _validate_relative_path(relative_path, url, require_repo_path=True)

    split = urlsplit(url)
    if not split.scheme or not split.hostname:
        raise ValueError("git URL must include a scheme/host or be scp-style")
    if split.query or split.fragment:
        raise ValueError("git URL must not include a query string or fragment")

    relative_path = PurePosixPath(
        split.scheme,
        split.hostname,
        unquote(split.path.lstrip("/:")),
    )
    return _validate_relative_path(relative_path, url, require_repo_path=True)


def derive_relative_url_path(url: str) -> PurePosixPath:
    split = urlsplit(url)
    if not split.scheme or not split.hostname:
        raise ValueError("URL must include a scheme and host")
    if split.fragment:
        raise ValueError("URL must not include a fragment")

    path_value = unquote(split.path.lstrip("/")) or "__root__"
    relative_path = PurePosixPath(split.scheme, split.hostname, path_value)
    relative_path = _validate_relative_path(relative_path, url, require_repo_path=False)

    if split.query:
        return relative_path / "__query__" / quote(split.query, safe="")
    return relative_path


def cache_lookup_paths(url: str) -> list[PurePosixPath]:
    split = urlsplit(url)
    candidates = [derive_relative_url_path(url)]
    if split.query:
        without_query = urlunsplit((split.scheme, split.netloc, split.path, "", ""))
        candidates.append(derive_relative_url_path(without_query))
    return candidates


def _validate_relative_path(
    relative_path: PurePosixPath,
    url: str,
    *,
    require_repo_path: bool,
) -> PurePosixPath:
    minimum_parts = 3 if require_repo_path else 2
    if len(relative_path.parts) < minimum_parts:
        raise ValueError(f"URL is missing a path component: {url}")
    if str(relative_path) in {".", ""} or ".." in relative_path.parts:
        raise ValueError(f"URL produced an invalid local path: {url}")
    return relative_path
