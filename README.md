# url-vault

`url-vault` builds a local cache of mirrored Git repositories and ordinary URLs, then serves that cache back through a local proxy-friendly URL layout.

The current workflow is:

1. Prefetch known sources in a connected environment.
2. Run a local proxy in a disconnected environment.
3. Record cache misses into YAML.
4. Copy the miss YAML back to the connected environment.
5. Run `url-vault` again to fill the missing objects into the same cache tree.

## Current Capabilities

- Mirrors Git repositories with `git clone --mirror`
- Refreshes existing Git mirrors with `git remote update --prune`
- Runs `git update-server-info` after Git syncs for dumb-HTTP compatibility
- Downloads ordinary HTTP(S) URLs into the same cache tree
- Supports parallel sync with configurable `max_parallel`
- Supports always-prefetched lists through `prefetch` and `prefetch_files`
- Supports offline miss ingestion through `request_files`
- Includes a mitmproxy addon for cache hits and miss logging

## Cache Layout

The local cache path is derived from the original URL:

`<destination_dir>/<scheme>/<host>/<path>`

Examples:

- `https://github.com/org/example.git` -> `.../https/github.com/org/example.git`
- `git@github.com:org/example.git` -> `.../ssh/github.com/org/example.git`
- `https://example.com/archive.tar.gz?sha=abc123` -> `.../https/example.com/archive.tar.gz/__query__/sha%3Dabc123`

## Quick Start

Install the project into a local environment:

```bash
uv sync
```

Or with standard venv tooling:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Run one sync cycle:

```bash
url-vault --once
```

Or use the compatibility entry point:

```bash
python main.py --once
```

## Config Shape

Example runtime config:

```yaml
update_period: 24h
max_parallel: 4
destination_dir: /srv/url-vault/cache

prefetch_files:
  - prefetch.d/neovim-plugins.yaml

request_files:
  - requests/offline-misses.yaml
```

Current repo-local examples:

- `prefetch.d/neovim-plugins.yaml`: tracked Git prefetch list
- `requests/offline-misses.yaml`: optional offline miss queue, created or updated by the proxy workflow

## Project Layout

- `url_vault/`: runtime package
- `main.py`: Python entry point wrapper
- `mitm_local_cache.py`: mitmproxy addon for cache serving and miss logging
- `prefetch.d/`: tracked prefetch lists
- `requests/`: local miss queue directory
- `tests/`: pytest coverage
- `docs/specification.md`: project behavior and schema
- `mitmproxy.md`: Linux-first proxy setup

## Documentation

- Project specification: [docs/specification.md](docs/specification.md)
- Linux-focused proxy setup: [mitmproxy.md](mitmproxy.md)
- WSL-backed end-to-end smoke harness: [docs/e2e-smoke.md](docs/e2e-smoke.md)
