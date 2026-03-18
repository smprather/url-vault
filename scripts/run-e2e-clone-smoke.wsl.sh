#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <repo-root>" >&2
  exit 1
fi

REPO_ROOT=$1
shift

CONFIG_PATH="$REPO_ROOT/e2e/url-vault-self.yaml"
ARTIFACT_ROOT="$REPO_ROOT/e2e/artifacts"
CACHE_ROOT="$ARTIFACT_ROOT/cache"
MISS_LOG="$ARTIFACT_ROOT/offline-misses.yaml"
CLONE_ROOT="$ARTIFACT_ROOT/clone"
MITM_LOG="$ARTIFACT_ROOT/mitmdump.log"
UV_ENV_ROOT="$ARTIFACT_ROOT/uv-env"
TARGET_URL="https://github.com/smprather/url-vault.git"
PROXY_HOST="127.0.0.1"
PROXY_PORT="${URL_VAULT_E2E_PROXY_PORT:-8080}"
MITM_CA="${MITM_CA:-$HOME/.mitmproxy/mitmproxy-ca-cert.pem}"
MITM_PID=""
UV_BIN=""

fail() {
  echo "error: $*" >&2
  exit 1
}

need_command() {
  local command_name=$1

  if ! command -v "$command_name" >/dev/null 2>&1; then
    fail "missing required command: $command_name"
  fi
}

find_uv() {
  if command -v uv >/dev/null 2>&1; then
    UV_BIN=$(command -v uv)
    return
  fi

  if [[ -x "$HOME/.local/bin/uv" ]]; then
    UV_BIN="$HOME/.local/bin/uv"
    return
  fi

  UV_BIN=""
}

cleanup() {
  if [[ -n "$MITM_PID" ]] && kill -0 "$MITM_PID" >/dev/null 2>&1; then
    kill "$MITM_PID" >/dev/null 2>&1 || true
    wait "$MITM_PID" 2>/dev/null || true
  fi
}

run_url_vault() {
  if [[ -n "$UV_BIN" ]]; then
    (
      cd "$REPO_ROOT"
      "$UV_BIN" run url-vault --config "$CONFIG_PATH" --once
    )
    return
  fi

  need_command python3
  (
    cd "$REPO_ROOT"
    python3 -m url_vault.cli --config "$CONFIG_PATH" --once
  )
}

run_mitmdump() {
  if [[ -n "$UV_BIN" ]]; then
    (
      cd "$REPO_ROOT"
      exec "$UV_BIN" run mitmdump \
        --mode regular \
        --listen-host "$PROXY_HOST" \
        --listen-port "$PROXY_PORT" \
        -s "$REPO_ROOT/mitm_local_cache.py" \
        --set "cache_root=$CACHE_ROOT" \
        --set "miss_log_path=$MISS_LOG" \
        --set offline_only=true
    )
    return
  fi

  need_command mitmdump
  (
    cd "$REPO_ROOT"
    exec mitmdump \
      --mode regular \
      --listen-host "$PROXY_HOST" \
      --listen-port "$PROXY_PORT" \
      -s "$REPO_ROOT/mitm_local_cache.py" \
      --set "cache_root=$CACHE_ROOT" \
      --set "miss_log_path=$MISS_LOG" \
      --set offline_only=true
  )
}

wait_for_proxy() {
  local attempt

  for attempt in $(seq 1 150); do
    if [[ -n "$MITM_PID" ]] && ! kill -0 "$MITM_PID" >/dev/null 2>&1; then
      fail "mitmdump exited early. See $MITM_LOG"
    fi

    if bash -lc "exec 3<>/dev/tcp/$PROXY_HOST/$PROXY_PORT" >/dev/null 2>&1; then
      return
    fi
    sleep 0.2
  done

  fail "timed out waiting for mitmdump on $PROXY_HOST:$PROXY_PORT"
}

is_expected_git_miss() {
  local url=$1

  if [[ "$url" == "$TARGET_URL/objects/info/http-alternates" ]]; then
    return 0
  fi

  if [[ "$url" == "$TARGET_URL/objects/info/alternates" ]]; then
    return 0
  fi

  if [[ "$url" =~ ^${TARGET_URL//\//\\/}/objects/[0-9a-f]{2}/[0-9a-f]{38}$ ]]; then
    return 0
  fi

  return 1
}

validate_miss_log() {
  local miss_url

  if [[ ! -e "$MISS_LOG" || ! -s "$MISS_LOG" ]]; then
    return
  fi

  while IFS= read -r miss_url; do
    if ! is_expected_git_miss "$miss_url"; then
      fail "unexpected proxy miss was recorded: $miss_url"
    fi
  done < <(sed -n 's/^- url: //p' "$MISS_LOG")
}

need_command bash
need_command git
find_uv

if [[ ! -d "$REPO_ROOT" ]]; then
  fail "repo root does not exist: $REPO_ROOT"
fi

if [[ ! -f "$CONFIG_PATH" ]]; then
  fail "e2e config was not found: $CONFIG_PATH"
fi

if [[ ! -f "$MITM_CA" ]]; then
  fail "mitmproxy CA was not found at $MITM_CA. Run mitmdump once in WSL to generate it."
fi

trap cleanup EXIT

mkdir -p "$ARTIFACT_ROOT"
rm -rf "$CACHE_ROOT" "$CLONE_ROOT"
rm -f "$MISS_LOG" "$MITM_LOG"

if [[ -n "$UV_BIN" ]]; then
  export UV_PROJECT_ENVIRONMENT="$UV_ENV_ROOT"
  export UV_LINK_MODE=copy
fi

echo "==> Building mirror cache with url-vault"
run_url_vault

echo "==> Starting mitmdump on $PROXY_HOST:$PROXY_PORT"
run_mitmdump >"$MITM_LOG" 2>&1 &
MITM_PID=$!

wait_for_proxy

export HTTP_PROXY="http://$PROXY_HOST:$PROXY_PORT"
export HTTPS_PROXY="$HTTP_PROXY"
export ALL_PROXY="$HTTP_PROXY"
export NO_PROXY="localhost,127.0.0.1,::1"
export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTP_PROXY"
export all_proxy="$HTTP_PROXY"
export no_proxy="$NO_PROXY"
export SSL_CERT_FILE="$MITM_CA"
export CURL_CA_BUNDLE="$MITM_CA"
export REQUESTS_CA_BUNDLE="$MITM_CA"
export GIT_SSL_CAINFO="$MITM_CA"
export GIT_SMART_HTTP=0

echo "==> Cloning $TARGET_URL through mitmproxy"
git clone "$TARGET_URL" "$CLONE_ROOT"

if [[ ! -d "$CLONE_ROOT/.git" ]]; then
  fail "git clone did not produce a working tree at $CLONE_ROOT"
fi

if [[ ! -f "$CLONE_ROOT/README.md" ]]; then
  fail "cloned repository is missing README.md"
fi

validate_miss_log

echo "==> End-to-end smoke test passed"
echo "    cache root: $CACHE_ROOT"
echo "    clone root: $CLONE_ROOT"
echo "    mitmdump log: $MITM_LOG"
if [[ -e "$MISS_LOG" && -s "$MISS_LOG" ]]; then
  echo "    miss log: $MISS_LOG (expected dumb-http probe misses only)"
fi
