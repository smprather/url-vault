from __future__ import annotations

import mimetypes
from pathlib import Path

from mitmproxy import ctx
from mitmproxy import http

from url_vault.pathing import cache_lookup_paths
from url_vault.request_log import record_url_miss


class LocalCacheAddon:
    def load(self, loader) -> None:
        loader.add_option(
            name="cache_root",
            typespec=str,
            default="",
            help="Root cache directory created by url-vault.",
        )
        loader.add_option(
            name="miss_log_path",
            typespec=str,
            default="",
            help="YAML file where cache misses are recorded.",
        )
        loader.add_option(
            name="offline_only",
            typespec=bool,
            default=True,
            help="Return 404 on cache miss instead of forwarding upstream.",
        )

    def request(self, flow: http.HTTPFlow) -> None:
        if flow.request.method not in {"GET", "HEAD"}:
            return

        cache_root_value = ctx.options.cache_root
        if not cache_root_value:
            return

        cache_root = Path(cache_root_value).expanduser()
        matched_path = self._find_cached_path(cache_root, flow.request.pretty_url)
        if matched_path is not None:
            self._serve_file(flow, matched_path)
            return

        self._record_miss(flow.request.pretty_url, flow.request.method)

        if ctx.options.offline_only:
            flow.response = http.Response.make(
                404,
                b"cache miss\n",
                {"Content-Type": "text/plain; charset=utf-8"},
            )

    def _find_cached_path(self, cache_root: Path, url: str) -> Path | None:
        try:
            candidates = cache_lookup_paths(url)
        except ValueError as exc:
            ctx.log.warn(f"Skipping unsupported URL {url!r}: {exc}")
            return None

        for candidate in candidates:
            target = cache_root / Path(candidate)
            if target.is_file():
                return target
        return None

    def _serve_file(self, flow: http.HTTPFlow, target: Path) -> None:
        content_type, _ = mimetypes.guess_type(str(target))
        headers = {
            "Content-Type": content_type or "application/octet-stream",
            "X-Url-Vault-Cache": "hit",
        }
        body = b"" if flow.request.method == "HEAD" else target.read_bytes()
        flow.response = http.Response.make(200, body, headers)

    def _record_miss(self, url: str, request_method: str) -> None:
        miss_log_value = ctx.options.miss_log_path
        if not miss_log_value:
            return

        miss_log_path = Path(miss_log_value).expanduser()
        try:
            entry = record_url_miss(
                miss_log_path,
                url,
                request_method=request_method,
            )
        except ValueError as exc:
            ctx.log.warn(f"Failed to record cache miss for {url!r}: {exc}")
            return

        ctx.log.info(
            f"Recorded cache miss for {url} (count={entry.get('count', '?')})"
        )


addons = [LocalCacheAddon()]
