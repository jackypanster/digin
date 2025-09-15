# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Digin is an AI-powered codebase archaeology tool that analyzes code repositories using a bottom-up approach. It leverages AI CLI tools (Claude/Gemini) to understand code structure and generates structured JSON summaries for each directory in a project.

## Development Commands

### Environment Setup
```bash
# Install dependencies using uv
uv sync

# Install development dependencies
uv sync --dev

# Install package in development mode
uv pip install -e .
```

### Running the Application
```bash
# Primary method: Run directly via Python module
python -m src /path/to/analyze

# Alternative with uv
uv run python -m src /path/to/analyze

# After installation, use the digin command
digin /path/to/analyze
digin /path/to/analyze --provider claude --verbose

# Common usage patterns
python -m src . --dry-run                    # Preview analysis plan
python -m src . --force --verbose           # Force refresh with detailed output
python -m src . --output-format json        # JSON output format
```

### Testing

**CRITICAL PRINCIPLE**: All tests MUST use real Claude and Gemini CLI commands. NO mocking or fake data is allowed for AI functionality testing.

```bash
# Run all tests (includes real AI calls)
uv run pytest

# Run only unit tests (no AI calls)
uv run pytest -m "unit and not real_ai"

# Run only real AI tests (requires claude and gemini CLI installed)
uv run pytest -m real_ai

# Run tests with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_analyzer.py

# Run specific test function
uv run pytest tests/test_analyzer.py::test_analyze_directory -v

# Run tests by category (using markers)
uv run pytest -m unit              # Unit tests only
uv run pytest -m integration       # Integration tests only
uv run pytest -m real_ai           # Real AI CLI tests only
uv run pytest -m "not slow"        # Skip slow tests
uv run pytest -m "not real_ai"     # Skip real AI tests (for CI without API keys)

# Run tests in verbose mode
uv run pytest -v
```

**Test Markers:**
- `unit`: Pure unit tests with no external dependencies
- `integration`: Integration tests with file system or other components
- `real_ai`: Tests that make actual calls to Claude/Gemini CLI (requires installation)
- `slow`: Tests that take significant time to run

### Code Quality
```bash
# Format code
uv run black src tests

# Sort imports
uv run isort src tests

# Lint code
uv run flake8 src tests

# Type checking
uv run mypy src

# Run all quality checks
uv run black src tests && uv run isort src tests && uv run flake8 src tests && uv run mypy src

# Pre-commit hooks (automatically run on commit)
uv run pre-commit install
uv run pre-commit run --all-files
```

## Architecture Overview

### Core Components

The application follows a modular architecture with clear separation of concerns:

**CodebaseAnalyzer** (`src/analyzer.py`): Main orchestrator that coordinates the analysis process. It manages statistics, handles the bottom-up traversal order, and coordinates between other components.

**DirectoryTraverser** (`src/traverser.py`): Handles directory scanning and file collection. Implements filtering logic for ignored directories/files and collects file metadata including content previews for small text files.

**AIClient** (`src/ai_client.py`): Abstracts AI provider interactions (Claude/Gemini CLI). Builds analysis prompts and parses AI responses into structured JSON format.

**CacheManager** (`src/cache.py`): Manages digest caching to avoid redundant AI calls. Uses file content hashing to detect changes.

**SummaryAggregator** (`src/aggregator.py`): Handles aggregation of child directory summaries for parent directories.

**ConfigManager** (`src/config.py`): Manages configuration loading from multiple sources (default.json, .digin.json, CLI options).

### Analysis Flow

1. **Configuration Loading**: Three-tier precedence system
   - Base: `config/default.json` (built-in defaults)
   - Override: `.digin.json` in project root (project-specific)
   - Final: CLI options (highest priority, overrides all)
2. **Directory Traversal**: Scans repository, identifies leaf directories first
3. **Bottom-up Analysis**: 
   - Leaf directories: AI analysis of files via `src/ai_client.py`
   - Parent directories: Aggregation of child summaries via `src/aggregator.py`
4. **Caching**: Results cached as digest.json files (managed by `src/cache.py`)
5. **Output**: Structured JSON with project understanding

### Key Patterns

- **Bottom-up Processing**: Analyzes leaf directories first, then aggregates upward
- **Configurable Filtering**: Extensive ignore patterns and file extension filtering
- **Provider Abstraction**: Supports multiple AI providers through unified interface
- **Rich CLI**: Uses Rich library for formatted output and progress indication
- **Error Resilience**: Continues analysis even if individual directories fail

## Configuration

Default configuration is in `config/default.json`. Users can override with `.digin.json` in project root or via CLI options. Key settings:

- `ignore_dirs`: Directories to skip (node_modules, .git, etc.)
- `ignore_files`: File patterns to ignore (*.pyc, *.log, etc.) 
- `include_extensions`: File extensions to analyze
- `api_provider`: AI provider (gemini/claude, default: gemini)
- `cache_enabled`: Whether to use digest caching
- `max_depth`: Maximum directory depth to analyze

## Python Coding Guidelines

### Core Philosophy
Write simple, readable Python code for this project. Prioritize maintainability over performance. Follow "fail fast" principle.

### Testing Philosophy - REAL AI COMMANDS ONLY

**CRITICAL RULE**: This project MUST test with real Claude and Gemini CLI commands. No mocking, stubbing, or fake data is permitted for AI functionality.

**Why this matters:**
- AI CLI behavior can change with updates
- Real prompts may fail in ways mocks cannot simulate
- Response parsing must handle actual AI output variations
- Integration issues only surface with real commands

**Implementation Requirements:**
- All AI client tests marked with `@pytest.mark.real_ai`
- Tests must verify actual Claude/Gemini CLI installation and availability
- Test failures with real AI indicate actual integration problems
- Mock only non-AI components (file system, config, etc.)

**Developer Setup:**
- Install `claude` and `gemini` CLI tools locally
- Verify with: `claude --version` and `gemini --version`
- Run AI tests: `uv run pytest -m real_ai`
- For CI/environments without AI tools: `uv run pytest -m "not real_ai"`

### Key Rules

1. **NO Exception Handling Unless Absolutely Necessary**
   - Let errors crash immediately with clear messages
   - Only catch exceptions for external APIs or expected business logic
   - Never use bare `except:` or silent failures

2. **Simple and Direct**
   - Prefer functions over classes where possible
   - No unnecessary design patterns or abstractions
   - Maximum 20 lines per function
   - Each function does ONE thing
   - Flat structure - avoid deeply nested code

3. **Minimum Code**
   - Every line must have clear purpose
   - Use Python built-ins and standard library
   - Delete code instead of commenting out
   - No boilerplate

4. **Readability First**
   - Full descriptive names, no abbreviations
   - Early returns to reduce nesting
   - Self-documenting code
   - F-strings for formatting

### Error Handling Philosophy

This codebase follows a "fail fast" approach:
- Errors crash immediately with clear messages rather than being silently handled
- Only catch exceptions for external APIs (AI CLI calls) or expected business logic
- Use custom exceptions like `AnalysisError` for domain-specific failures
- Let Python's built-in exceptions bubble up for programming errors

### Code Style Examples

```python
# GOOD - Simple and clear
def calculate_total_files(file_paths):
    if not file_paths:
        return 0
    return len([p for p in file_paths if p.is_file()])

# AVOID - Over-engineered for this project size
class FileCounter:
    def __init__(self):
        self.validator = PathValidator()
    
    def count(self, paths):
        try:
            validated = self.validator.validate(paths)
            return self._count_files(validated)
        except Exception:
            return 0
```

## Development Notes

- Uses `uv` as the package manager and task runner
- Python 3.8+ required (minimum 3.8.1 for mypy compatibility)
- Uses dataclasses for configuration and type hints throughout
- Rich library provides CLI formatting and progress indication
- AI CLI tools must be installed separately (claude/gemini)
- Prompt template in `config/prompt.txt` defines AI analysis instructions
- Pre-commit hooks enforce code quality (black, isort, flake8, mypy)
- Project entry point: `src:main` (can be run as `digin` command after installation)