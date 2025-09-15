# Repository Guidelines

## Project Structure & Module Organization
- `src/` — core package and CLI. Entry points: `python -m src /path` or installed `digin /path`. Key modules: `analyzer.py`, `traverser.py`, `ai_client.py`, `cache.py`, `aggregator.py`, `config.py`, `__main__.py`.
- `tests/` — pytest suite (`test_*.py` or `*_test.py`; classes `Test*`; functions `test_*`).
- `config/` — defaults (`default.json`) and AI prompt (`prompt.txt`). User overrides via project‑root `.digin.json`.
- `docs/` — product/architecture notes (e.g., `PRD.md`).
- `scripts/` — helper scripts (optional).
- Root: `pyproject.toml`, `README.md`, `LICENSE`.

## Build, Test, and Development Commands
- Setup deps: `uv sync` (use `--dev` for dev extras). Dev install: `uv pip install -e .`.
- Run locally: `python -m src /path/to/analyze` or `digin /path` (after install). Example: `digin /path --provider gemini --verbose`.
- Tests: `uv run pytest` (coverage + HTML/XML reports). Specific file: `uv run pytest tests/test_analyzer.py`.
- Quality: `uv run black src tests` • `uv run isort src tests` • `uv run flake8 src tests` • `uv run mypy src`.
- Pre-commit: `uv run pre-commit install` then `uv run pre-commit run --all-files`.

## Coding Style & Naming Conventions
- Formatting: Black (line length 88) and isort (`profile=black`). 4‑space indentation.
- Linting: flake8; fix all warnings before PR.
- Typing: mypy strict; add type hints, no untyped defs in `src/`.
- Naming: modules/files `snake_case`; classes `PascalCase`; functions/vars `snake_case`; constants `UPPER_CASE`.

## Testing Guidelines
- Framework: pytest + pytest‑cov; keep tests deterministic and isolated (`tmp_path`, `pytest-mock`).
- Markers: `unit`, `integration`, `slow` (configured). Use when appropriate.
- Discovery: follow naming rules above. Prefer small, focused tests.
- Coverage: include tests for new/changed code; maintain or improve overall coverage.

## Commit & Pull Request Guidelines
- Commits: Conventional Commits (e.g., `feat: add hidden-file exclusion`). Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`.
- PRs: clearly describe intent and scope, link issues (e.g., `Closes #123`), include CLI/output screenshots when UX changes, and run all quality and test commands before requesting review.

## Security & Configuration Tips
- Do not commit API keys or provider tokens. Configure Claude/Gemini locally via environment/OS keychain.
- Prefer project‑root `.digin.json` for local overrides; respect `ignore_dirs`, `ignore_files`, and `ignore_hidden` (true by default).

