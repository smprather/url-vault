# Project Specification

## 1. Purpose

`url-vault` maintains a local URL-shaped cache that can be populated in a connected environment and served in a disconnected environment.

The current implementation supports two source kinds:

- `git`: bare mirrors created with `git clone --mirror`
- `url`: ordinary HTTP(S) objects fetched and stored as files

## 2. Current Runtime Surface

Current user-facing entry points:

- `url-vault`: installed CLI from the package entry point
- `python main.py`: thin wrapper around the same CLI

Current runtime modules:

- `url_vault/config.py`: config loading and validation
- `url_vault/pathing.py`: URL-to-cache-path derivation and proxy lookup fallbacks
- `url_vault/sync.py`: Git and plain-URL sync engine
- `url_vault/request_log.py`: YAML miss-log merge/update behavior
- `url_vault/app.py`: update loop and stdout reporting
- `url_vault/cli.py`: `rich-click` command-line interface

Current proxy integration:

- `mitm_local_cache.py`: mitmproxy addon that serves hits and logs misses

## 3. Primary Workflow

The intended operating loop is:

1. A connected machine prefetches known sources into a local cache.
2. A disconnected machine runs `mitmproxy` in front of tools like `curl`, `wget`, Git, and Neovim plugin managers.
3. On cache miss, the proxy records the exact requested URL into a YAML request file.
4. That request file is copied back to the connected environment.
5. `url-vault` ingests the request file and downloads the missing objects into the same cache tree.

The manual copy step is intentional for the first version.

## 4. Goals

- Keep Git mirrors up to date on a schedule.
- Prefetch known URL lists before users ask for them.
- Record exact cache misses for later retrieval.
- Preserve URL structure on disk so a proxy can resolve requests without custom per-source metadata.
- Allow bounded parallel syncs.

## 5. Non-Goals

- No full automatic online/offline transport yet.
- No attempt to be a full smart Git HTTP server.
- No GUI.

## 6. Functional Requirements

1. The system must read a local YAML config file.
2. The system must support both inline entries and referenced YAML files.
3. The system must clone missing Git mirrors with `git clone --mirror`.
4. The system must update existing Git mirrors with `git remote update --prune`.
5. The system must regenerate `update-server-info` for mirrored Git repositories.
6. The system must download configured plain URLs into the local cache tree.
7. The system must support a `--once` CLI mode that runs a single cycle and exits.
8. The system must allow a configurable sync concurrency limit.
9. The proxy-facing cache lookup must use the same URL-to-path rules as the fetch side.
10. Cache misses must be recordable into a YAML file that can be fed back through `request_files`.

## 7. Configuration Model

Runtime config:

```yaml
update_period: 24h
max_parallel: 4
destination_dir: $HOME/repo_mirrors

prefetch:
  - kind: url
    url: https://example.com/bootstrap.txt

prefetch_files:
  - prefetch.d/neovim-plugins.yaml

request_files:
  - requests/offline-misses.yaml
```

Rules:

- `update_period` is required and supports `s`, `m`, `h`, and `d` suffixes.
- `max_parallel` defaults to `4`.
- `destination_dir` is required.
- `prefetch` is an inline list of entries.
- `repositories` is still accepted as a legacy alias for Git-prefetch entries.
- `prefetch_files` loads tracked or shared entry files.
- `request_files` loads offline miss queues; missing files are allowed.

Prefetch file example:

```yaml
kind: git
entries:
  - url: https://github.com/folke/lazy.nvim.git
  - url: https://github.com/nvim-lua/plenary.nvim.git
```

Request file example:

```yaml
kind: url
requests:
  - url: https://github.com/folke/lazy.nvim.git/info/refs?service=git-upload-pack
    count: 3
    first_seen: 2026-03-15T18:00:00Z
    last_seen: 2026-03-15T18:05:00Z
    last_method: GET
```

Entries remain mappings so more keys can be added later without changing the schema.

## 8. Cache Path Rules

Local cache paths are derived automatically from the URL and stored under:

`<destination_dir>/<scheme>/<host>/<path>`

Examples:

- `https://github.com/org/example.git` ->
  `<destination_dir>/https/github.com/org/example.git`
- `git@github.com:org/example.git` ->
  `<destination_dir>/ssh/github.com/org/example.git`
- `https://example.com/archive.tar.gz?sha=abc123` ->
  `<destination_dir>/https/example.com/archive.tar.gz/__query__/sha%3Dabc123`

For ordinary URLs with a query string, the exact query is preserved under `__query__/`.

For proxy lookup, the system first tries the exact URL-derived path and then falls back to the no-query path for ordinary URLs.

## 9. Sync Behavior

Git items:

- missing mirror: `git clone --mirror`
- existing mirror: `git -C <path> remote update --prune`
- success follow-up: `git --git-dir <path> update-server-info`

URL items:

- download with `urllib.request`
- write through a temp file and atomic replace
- return `download` for first fetch and `refresh` when overwriting an existing cached file

Parallelism:

- sync tasks run through a bounded `ThreadPoolExecutor`
- `max_parallel` controls the worker count

## 10. Request Logging

`url_vault/request_log.py` maintains a YAML request log compatible with `request_files`.

Current behavior:

- keyed by exact URL
- increments `count`
- preserves `first_seen`
- updates `last_seen`
- updates `last_method`
- creates the log file if it does not exist

## 11. Prefetch Strategy

Known high-value sources should live in tracked files under `prefetch.d/`.

Current example:

- `prefetch.d/neovim-plugins.yaml`: Git prefetch list for popular Neovim plugins

This lets the cache be prewarmed for expected demand without waiting for an offline miss to happen first.

## 12. Error Handling And Observability

- Partial failures must not stop other sync tasks.
- Per-item status must be printed with action, URL, local path, and result detail.
- Missing request files are allowed so the runtime config can point at future offline exports.
- Invalid config files or malformed request logs must fail with actionable errors.
- Proxy cache hits return `X-Url-Vault-Cache: hit`.

## 13. Testing Status

Current automated coverage includes:

- config parsing and validation
- path derivation and query handling
- Git sync execution
- plain URL download execution
- request-log merge behavior
- app loop and CLI wiring

## 14. Acceptance Criteria

- `url-vault --once` processes all configured items exactly once.
- Git items are mirrored into bare repositories and refreshed with `update-server-info`.
- URL items are downloaded into the same cache tree used by the proxy.
- Proxy misses can be recorded into YAML and later ingested through `request_files`.
- Core config, sync, CLI, and request-log behavior is covered by automated tests.
