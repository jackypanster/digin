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
# Run directly via Python module
python -m src /path/to/analyze

# After installation, use the digin command
digin /path/to/analyze
digin /path/to/analyze --provider gemini --verbose
```

### Testing
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_analyzer.py

# Run tests in verbose mode
uv run pytest -v
```

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

1. **Configuration Loading**: Merges default config → .digin.json → CLI options
2. **Directory Traversal**: Scans repository, identifies leaf directories first
3. **Bottom-up Analysis**: 
   - Leaf directories: AI analysis of files
   - Parent directories: Aggregation of child summaries
4. **Caching**: Results cached as digest.json files
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
- `api_provider`: AI provider (claude/gemini)
- `cache_enabled`: Whether to use digest caching
- `max_depth`: Maximum directory depth to analyze

## Development Notes

- Uses `uv` as the package manager and task runner
- Python 3.8+ required
- Uses dataclasses for configuration and type hints throughout
- Rich library provides CLI formatting and progress indication
- AI CLI tools must be installed separately (claude/gemini)
- Prompt template in `config/prompt.txt` defines AI analysis instructions