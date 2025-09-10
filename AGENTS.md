# Repository Guidelines

## Project Structure & Module Organization
- `src/` — core package and CLI (run with `python -m src` or installed `digin`). Key modules: `analyzer.py`, `traverser.py`, `ai_client.py`, `cache.py`, `aggregator.py`, `config.py`, `__main__.py`.
- `tests/` — pytest suite. Discovery: `test_*.py` or `*_test.py`; classes `Test*`; functions `test_*`.
- `config/` — defaults (`default.json`) and AI prompt (`prompt.txt`). User overrides via project‐root `.digin.json`.
- `docs/` — product/architecture notes (e.g., `PRD.md`).
- `scripts/` — helper scripts (optional).
- Root files: `pyproject.toml` (hatchling + tooling), `README.md`, `LICENSE`.

## Build, Test, and Development Commands
- Setup deps: `uv sync` (use `--dev` for dev extras). Dev install: `uv pip install -e .`.
- Run locally: `python -m src /path/to/analyze` or `digin /path` (after install). Examples: `digin /path --provider gemini --verbose`.
- Tests: `uv run pytest` (coverage enabled via config). HTML/XML reports also generated. Specific file: `uv run pytest tests/test_analyzer.py`.
- Quality: `uv run black src tests` • `uv run isort src tests` • `uv run flake8 src tests` • `uv run mypy src`.
- Pre-commit: `uv run pre-commit install` then `uv run pre-commit run --all-files`.

## Coding Style & Naming Conventions
- Formatting: Black (line length 88) and isort (`profile=black`). 4‑space indentation.
- Linting: flake8; fix warnings before PR.
- Typing: mypy strict; add type hints (no untyped defs in `src/`).
- Naming: modules/files `snake_case`; classes `PascalCase`; functions/vars `snake_case`; constants `UPPER_CASE`.

## Testing Guidelines
- Framework: pytest + pytest‑cov; keep tests deterministic and isolated (`tmp_path`, `pytest-mock`).
- Conventions: put tests in `tests/`; use markers `unit`, `integration`, `slow` (configured). Name per discovery rules above.
- Coverage: include tests for new/changed code and maintain or improve overall coverage.

## Commit & Pull Request Guidelines
- Commits follow Conventional Commits (e.g., `feat: add hidden-file exclusion`). Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`.
- Before opening a PR: describe intent and scope, link issues (`Closes #123`), include CLI/output screenshots when UX changes, and run: `black`, `isort`, `flake8`, `mypy`, `pytest`.
- Update docs/config when behavior or defaults change (`README.md`, `config/default.json`).
- CI: GitHub Actions runs pre-commit on pushes/PRs; all checks must pass.

## Security & Configuration Tips
- Do not commit API keys or provider tokens; configure Claude/Gemini CLI locally via environment/OS keychain.
- Prefer `.digin.json` for local overrides; respect `ignore_dirs`/`ignore_files` and `ignore_hidden` (true by default).
