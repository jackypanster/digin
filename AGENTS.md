# Repository Guidelines

## Project Structure
- `src/` — core package + CLI (`python -m src` or `digin`). Key modules: `analyzer.py`, `traverser.py`, `ai_client.py`, `cache.py`, `aggregator.py`, `config.py`, `__main__.py`.
- `tests/` — pytest suite (`test_*.py` / `*_test.py`; classes `Test*`; functions `test_*`).
- `config/` — defaults (`default.json`), AI prompt (`prompt.txt`); user overrides `.digin.json`.
- `docs/`, `scripts/`; root: `pyproject.toml`, `README.md`, `LICENSE`.

## Build, Test, Dev
- Setup: `uv sync` (add `--dev` for dev extras). Editable install: `uv pip install -e .`.
- Run: `python -m src /path` or `digin /path --provider gemini --verbose`.
- Test: `uv run pytest` or `uv run pytest tests/test_analyzer.py`.
- Quality: `uv run black src tests` • `uv run isort src tests` • `uv run flake8 src tests` • `uv run mypy src`.
- Pre-commit: `uv run pre-commit install` then `uv run pre-commit run --all-files`.

## Coding Style
- Black (88 cols), isort `profile=black`, 4-space indent.
- flake8 clean before PR.
- mypy strict; full type hints; no untyped defs in `src/`.
- Naming: modules/files snake_case; classes PascalCase; functions/vars snake_case; constants UPPER_CASE.

## Testing
- pytest + pytest-cov; deterministic, isolated (`tmp_path`, `pytest-mock`).
- Use markers: `unit`, `integration`, `slow`.
- Maintain or improve coverage; add tests for changed code.

## Commits & PRs
- Conventional Commits (e.g., `feat: add hidden-file exclusion`).
- PRs: clear intent/scope, linked issues (`Closes #123`), screenshots for UX changes. Run formatting, lint, types, tests first.

## Code Review Rules
- Fail Fast: raise or propagate errors; no blind retries or swallow-and-continue.
- Readability First: small, single-purpose functions (<60 lines); files have single responsibility; names reflect domain intent.
- Clear Boundaries: validate inputs; prefer immutable data; define explicit timeouts and retry/backoff where needed.
- Logging & Monitoring: structured `logging` on critical paths; never log secrets or PII; avoid `print`.
- Python-specific: prefer `pathlib`, typing (`TypedDict`, `Protocol`, `dataclass(frozen=True)`), context managers, and `logging`. Avoid side effects at import; make time/IO injectable for tests.

## Review Output Contract
- Human-readable (PR comment): sections “Summary / High / Medium / Quick Wins / Tests / Patch Ideas”.
- Machine-readable (CI): prefer CodeClimate JSON for findings; otherwise emit minimal JSON with fields: `check_name`, `description`, `categories`, `severity`, `location{path,lines}`, `fingerprint`. Write to `reports/code-review.json` or stdout.

## Security & Config
- Never commit API keys; configure providers via env/OS keychain.
- Use `.digin.json` for local overrides; respect `ignore_dirs`, `ignore_files`, `ignore_hidden=true`.
