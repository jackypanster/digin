# Repository Guidelines

## Project Structure & Module Organization
- Core package lives in `src/`; start with `analyzer.py`, `traverser.py`, `ai_client.py`, `cache.py`, `aggregator.py`, `config.py`, and `__main__.py` to trace CLI behavior.
- Tests sit under `tests/` and mirror module names via `Test*` classes and `test_*` functions for quick isolation.
- Configuration assets (`config/default.json`, `config/prompt.txt`) define traversal defaults and prompt wording; `docs/` and `scripts/` house reference material and automation helpers.

## Build, Test & Development Commands
- `uv sync --dev` installs runtime plus dev extras pinned in `pyproject.toml`.
- `uv pip install -e .` enables editable imports for local iteration.
- `python -m src /path` or `digin /path --provider gemini --verbose` runs the analyzer against a target tree.
- `uv run pytest` executes the suite; scope with module paths (e.g., `uv run pytest tests/test_analyzer.py`).
- Quality gates: `uv run black src tests`, `uv run isort src tests`, `uv run flake8 src tests`, `uv run mypy src`.

## Coding Style & Naming Conventions
- Black formatting (88 columns), 4-space indentation, and isort with the Black profile are mandatory.
- Prefer `pathlib`, typed dataclasses, and explicit protocols; avoid side effects at import time.
- Use snake_case for modules/functions, PascalCase for classes, UPPER_CASE for constants.

## Testing Guidelines
- Pytest is the standard; leverage fixtures like `tmp_path` and `pytest-mock` to isolate IO.
- Tag slower scenarios with `@pytest.mark.slow` or project markers; keep unit tests fast.
- Maintain or raise coverage before merging; add regression tests alongside bug fixes.
- Place tests in `tests/test_<module>.py` and mirror class/function names for clarity.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (e.g., `feat: add hidden-file exclusion`, `fix: handle cache miss`).
- PRs must summarize scope, link issues (`Closes #123`), and include CLI output or screenshots for user-visible work.
- Document any skipped checks and ensure formatting, lint, type, and test commands run clean locally.

## Security & Configuration Tips
- Never commit provider credentials; rely on environment variables or secret managers.
- Respect `ignore_dirs`, `ignore_files`, and `ignore_hidden=true` defaults when extending traversal logic.
- Use structured logging for diagnostics; avoid `print` in production pathways.

## Agent Workflow Notes
- Review `config/default.json` and `config/prompt.txt` before altering analyzer behavior.
- Keep functions focused (<60 lines), validate inputs early, and prefer immutable data flows.
- Inject time and IO dependencies to keep executions and tests deterministic.
