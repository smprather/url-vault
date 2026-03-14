# Repository Guidelines

## Project Structure & Module Organization
This repository is currently a minimal Python project:
- `main.py`: entry point script.
- `pyproject.toml`: project metadata and dependencies (`pyyaml`).
- `README.md`: short project description.

Keep new runtime code small and composable. As the project grows, prefer moving logic from `main.py` into a package directory such as `src/mirror_repos/`, and place tests in `tests/`.

## Build, Test, and Development Commands
Use Python 3.14+ (see `.python-version`).

- `python -m venv .venv && source .venv/bin/activate`: create and activate a local virtual environment.
- `python -m pip install -e .`: install project dependencies in editable mode.
- `python main.py`: run the current entry point.
- `python -m pytest`: run tests (when `tests/` exists).

If you use `uv`, equivalent workflows are acceptable (for example, `uv sync`, `uv run python main.py`).

## Coding Style & Naming Conventions
Follow standard Python conventions:
- 4-space indentation, UTF-8, and one import per line.
- `snake_case` for functions/variables/modules, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Keep functions focused and side effects explicit.

Use type hints for new or modified public functions. Prefer small modules over large multi-purpose files.

## Testing Guidelines
Use `pytest` for all new tests.
- Put tests under `tests/`.
- Name files `test_*.py` and test functions `test_*`.
- Cover happy paths, error paths, and config parsing behavior.

For bug fixes, add a regression test that fails before the fix and passes after it.

## Commit & Pull Request Guidelines
Current history is minimal (`Initial commit`), so use clear, imperative commit messages moving forward.

Recommended format:
- `feat: add repository sync planner`
- `fix: handle missing remote URL`
- `test: add config validation cases`

PRs should include:
- concise summary of behavior changes,
- linked issue (if applicable),
- test evidence (command + result),
- notes on config or migration impact.

## Security & Configuration Tips
Do not commit secrets, tokens, or machine-specific `.env` values. Keep repository lists and credentials in local, ignored config files.
