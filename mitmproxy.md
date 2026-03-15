# mitmproxy Setup For Linux

This document is Linux-first. Windows notes are left in a few places for reference, but the main target is a Linux environment running offline behind a local proxy.

The goal is:

1. Serve cached URLs from the local database created by `url-vault`.
2. Record cache misses into a YAML file.
3. Copy that YAML file back to a connected environment.
4. Re-run `url-vault` there so the missing URLs are fetched into the same cache layout.

## Requirements

- a cache tree populated by `url-vault`
- `mitmproxy` or `mitmdump`
- the `mitm_local_cache.py` addon from this repo
- a shell environment where clients can be pointed at an HTTP(S) proxy

You can run the addon either:

- from the repository root, so it can import `url_vault`
- or from any environment where `url-vault` is installed into Python

## Cache Layout

`url-vault` stores cache entries under:

`<destination_dir>/<scheme>/<host>/<path>`

Examples:

- `https://github.com/folke/lazy.nvim.git` ->
  `<destination_dir>/https/github.com/folke/lazy.nvim.git`
- `https://github.com/folke/lazy.nvim.git/info/refs?service=git-upload-pack` ->
  `<destination_dir>/https/github.com/folke/lazy.nvim.git/info/refs/__query__/service%3Dgit-upload-pack`
- `git@github.com:folke/lazy.nvim.git` ->
  `<destination_dir>/ssh/github.com/folke/lazy.nvim.git`

For ordinary URLs with a query string, the addon first checks the exact query-derived path and then falls back to the same path without the query component.

## 1. Install mitmproxy

```bash
python -m pip install mitmproxy
```

Or:

```bash
uv tool install mitmproxy
```

## 2. Generate The CA Once

Run mitmproxy one time:

```bash
mitmdump --listen-host 127.0.0.1 --listen-port 8080
```

This creates CA files under `~/.mitmproxy/`.

The file most CLI tools need is:

- `~/.mitmproxy/mitmproxy-ca-cert.pem`

## 3. Use The Repo Addon

This repo includes `mitm_local_cache.py`.

It does three things:

- looks up requested URLs in the local cache tree
- serves the file immediately on cache hit
- appends cache misses into a YAML file on cache miss

Current miss-log behavior:

- only `GET` and `HEAD` are recorded
- duplicate URLs are merged
- `count`, `first_seen`, `last_seen`, and `last_method` are tracked

The miss log schema is compatible with `request_files` in `config.yaml`.

## 4. Start The Proxy

Repository-root example:

```bash
export MIRROR_ROOT="$HOME/repo_mirrors"
export MISS_LOG="$PWD/requests/offline-misses.yaml"

mitmdump \
  --mode regular \
  --listen-host 127.0.0.1 \
  --listen-port 8080 \
  -s ./mitm_local_cache.py \
  --set cache_root="$MIRROR_ROOT" \
  --set miss_log_path="$MISS_LOG" \
  --set offline_only=true
```

Installed-package example:

```bash
export MIRROR_ROOT="$HOME/repo_mirrors"
export MISS_LOG="$HOME/url-vault/requests/offline-misses.yaml"

mitmdump \
  --mode regular \
  --listen-host 127.0.0.1 \
  --listen-port 8080 \
  -s /path/to/mitm_local_cache.py \
  --set cache_root="$MIRROR_ROOT" \
  --set miss_log_path="$MISS_LOG" \
  --set offline_only=true
```

Notes:

- `offline_only=true` makes cache misses fail fast with `404`.
- If you later want online fallback, set `offline_only=false`.
- Cache hits return `X-Url-Vault-Cache: hit`.

## 5. Point Linux CLI Tools At The Proxy

Use both upper and lower case variables for compatibility:

```bash
export HTTP_PROXY="http://127.0.0.1:8080"
export HTTPS_PROXY="http://127.0.0.1:8080"
export ALL_PROXY="http://127.0.0.1:8080"
export NO_PROXY="localhost,127.0.0.1,::1"

export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTPS_PROXY"
export all_proxy="$ALL_PROXY"
export no_proxy="$NO_PROXY"
```

This typically covers:

- `curl`
- `wget`
- Git
- Python `requests`
- tools layered on top of Git or libcurl

## 6. Trust The mitmproxy CA

Point common tools at the mitmproxy CA:

```bash
export MITM_CA="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"
export SSL_CERT_FILE="$MITM_CA"
export CURL_CA_BUNDLE="$MITM_CA"
export REQUESTS_CA_BUNDLE="$MITM_CA"
export GIT_SSL_CAINFO="$MITM_CA"
```

`wget` example:

```bash
wget --ca-certificate="$MITM_CA" -S -O - https://example.com/file.txt
```

## 7. Git Caveat

Git mirrors are stored as bare repositories. That is enough to hold the objects locally, but HTTP clients are still expecting a Git-over-HTTP view of those files.

`url-vault` already runs:

```bash
git --git-dir <mirror> update-server-info
```

after each Git sync. That helps dumb-HTTP clients by generating `info/refs` metadata inside the mirror.

This is still not the same thing as a full smart Git HTTP server. If you later need better compatibility, the next step is probably `git-http-backend` in front of the same cache tree.

## 8. Miss Queue Workflow

In the offline Linux environment:

1. Run the proxy with `miss_log_path` pointing at a writable YAML file.
2. Let users run Neovim, Git, `curl`, `wget`, or other tools through the proxy.
3. When the cache misses, the addon writes or updates entries in `requests/offline-misses.yaml`.

Example:

```yaml
kind: url
requests:
  - url: https://github.com/folke/lazy.nvim.git/info/refs?service=git-upload-pack
    count: 2
    first_seen: 2026-03-15T18:00:00Z
    last_seen: 2026-03-15T18:05:00Z
    last_method: GET
```

Then:

1. Copy that YAML file to the connected environment.
2. Keep it listed under `request_files` in `config.yaml`.
3. Run `url-vault --once`.
4. Copy the refreshed cache tree back to the offline environment.

The request file is deduplicated by URL and keeps hit counts plus timestamps.

## 9. Prefetch Known URL Sets

Manual miss capture is only part of the loop. Known high-value sets should be prefetched in advance.

This repo already uses that pattern:

- `prefetch.d/neovim-plugins.yaml` keeps the Neovim plugin prefetch list in the generic `kind + entries` format
- `config.yaml` points at that file through `prefetch_files`

That lets you warm the cache for likely requests before an offline user asks for them.

## 10. Smoke Tests

With the proxy running and env vars set:

```bash
curl -I https://github.com/folke/lazy.nvim.git/info/refs
```

```bash
wget --ca-certificate="$MITM_CA" -S -O - https://github.com/folke/lazy.nvim.git/info/refs
```

If the file exists in the cache, the response should come directly from mitmproxy.

If it does not exist, the addon should:

- record the miss in `requests/offline-misses.yaml`
- return `404` when `offline_only=true`

## Optional Windows Notes

If you ever want to test from Windows, the same proxy variables exist in PowerShell:

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:8080"
$env:HTTPS_PROXY = "http://127.0.0.1:8080"
$env:ALL_PROXY = "http://127.0.0.1:8080"
$env:NO_PROXY = "localhost,127.0.0.1,::1"

$env:http_proxy = $env:HTTP_PROXY
$env:https_proxy = $env:HTTPS_PROXY
$env:all_proxy = $env:ALL_PROXY
$env:no_proxy = $env:NO_PROXY
```
