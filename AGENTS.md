# Repository Guidelines

## Project Structure & Module Organization

This repository is a Python project centered around the `url_vault` package.

Current layout:

- `url_vault/`: runtime package
- `main.py`: thin wrapper around the installed CLI
- `mitm_local_cache.py`: mitmproxy addon for cache hits and miss logging
- `prefetch.d/`: tracked prefetch lists
- `requests/`: local request-log directory
- `tests/`: pytest suite
- `docs/specification.md`: behavior and config specification
- `mitmproxy.md`: Linux-first proxy setup

Keep new runtime code small and composable. Prefer adding focused modules under `url_vault/` instead of growing `main.py`.

## Build, Test, and Development Commands

Use Python 3.14+ (see `.python-version`).

- `uv sync`: install project and dev dependencies into the managed environment
- `python -m venv .venv && source .venv/bin/activate`: create and activate a local virtual environment
- `python -m pip install -e .`: install the project in editable mode
- `url-vault --once`: run one sync cycle
- `python main.py --once`: run the same behavior through the wrapper script
- `python -m pytest`: run the test suite

If you use `uv`, equivalent workflows are preferred.

## Coding Style & Naming Conventions

Follow standard Python conventions:

- 4-space indentation, UTF-8, and one import per line
- `snake_case` for functions, variables, and modules
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants

Use type hints for new or modified public functions. Prefer small modules over large multi-purpose files. Keep side effects explicit.

## Testing Guidelines

Use `pytest` for all new tests.

- Put tests under `tests/`
- Name files `test_*.py` and test functions `test_*`
- Cover happy paths, error paths, config parsing, and path derivation behavior
- For bug fixes, add a regression test that fails before the fix and passes after it

## Commit & Pull Request Guidelines

Use clear, imperative commit messages.

Recommended format:

- `feat: add request log ingestion`
- `fix: preserve query-specific cache paths`
- `test: cover proxy miss deduplication`

PRs should include:

- concise summary of behavior changes
- linked issue if applicable
- test evidence with command and result
- notes on config or migration impact

## Config.yaml Update Guidelines

- When I ask for URLs to be added to `config.yaml`, always ignore these projects:
  - `neovim/nvim-lspconfig`
  - `williamboman/mason.nvim`

## Security & Configuration Tips

Do not commit secrets, tokens, or machine-specific `.env` values. Keep runtime config, repository lists, and local request logs in ignored local files unless the file is intentionally tracked as an example or prefetch list.
