# End-to-End Git Clone Smoke Test

This repo includes a WSL-backed smoke harness that proves a mirrored Git repository can be:

1. mirrored with `url-vault --once`
2. served back through `mitmdump` and `mitm_local_cache.py`
3. cloned through the local proxy with Git dumb HTTP

The checked-in single-repo config is [e2e/url-vault-self.yaml](../e2e/url-vault-self.yaml). It mirrors this repository's canonical GitHub URL into `e2e/artifacts/cache`.

## Prerequisites

- Windows host with Git Bash installed in the standard location
- WSL with a working Linux distro
- WSL commands available: `bash` and `git`
- Either `uv` in WSL or a WSL Python environment with `mitmdump` installed
- Project dependencies installed in WSL, preferably with `uv sync`
- mitmproxy CA generated once in WSL

Generate the mitmproxy CA once in WSL:

```bash
mitmdump --listen-host 127.0.0.1 --listen-port 8080
```

Then stop it after `~/.mitmproxy/mitmproxy-ca-cert.pem` exists.

## Run The Smoke Test

From Git Bash in the repository root:

```bash
./scripts/run-e2e-clone-smoke.sh
```

The wrapper shells into WSL and runs the real harness there.

The WSL harness will:

1. run `url-vault --config e2e/url-vault-self.yaml --once`
2. start `mitmdump` with `mitm_local_cache.py`
3. export proxy and CA environment variables
4. force Git dumb HTTP with `GIT_SMART_HTTP=0`
5. clone `https://github.com/smprather/url-vault.git` through the proxy
6. allow only known dumb-HTTP probe misses and fail on any other miss

## Artifacts

The harness writes ignored files under `e2e/artifacts/`:

- `cache/`: test-only mirror cache
- `clone/`: cloned worktree fetched through the proxy
- `mitmdump.log`: proxy output for debugging
- `offline-misses.yaml`: created only on cache miss
- `uv-env/`: WSL-only environment used by the harness so it does not reuse the repo's main `.venv`

## Notes

- The harness is a manual smoke test, not part of `pytest`.
- If `uv` is installed in WSL, the harness uses it for both `url-vault` and `mitmdump`.
- If `uv` is not installed in WSL, the harness falls back to `python3 -m url_vault.cli` and expects `mitmdump` to already be on `PATH`.
- Git dumb HTTP may probe `objects/info/alternates`, `objects/info/http-alternates`, and a loose object path before falling back to pack files. The harness treats only those misses as acceptable.
- If the clone fails, inspect `e2e/artifacts/mitmdump.log` first.
