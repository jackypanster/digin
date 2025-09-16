"""配置管理與合併。

來源順序：`config/default.json` → CLI 指定文件（後者覆蓋前者）。
DigginSettings 包含忽略規則、AI 供應商與選項、併發、深度、是否緩存、最大文件大小等。
提供 `get_max_file_size_bytes()`（人類可讀大小轉換）與 `save_config_template()`（輸出模板）。

設計重點：可配置但有良好默認值，方便在不同代碼倉快速落地並保持一致性。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LoggingSettings:
    """Logging configuration settings."""

    enabled: bool = True
    level: str = "INFO"
    log_dir: str = "logs"
    max_file_size: str = "10MB"
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ai_command_logging: bool = True
    ai_log_format: str = "readable"  # "readable" or "json"
    ai_log_detail_level: str = "summary"  # "summary" or "full"
    ai_log_prompt_max_chars: int = 200


@dataclass
class DigginSettings:
    """Configuration settings for digin."""

    # Directory and file filtering
    ignore_dirs: List[str] = field(default_factory=list)
    ignore_files: List[str] = field(default_factory=list)
    include_extensions: List[str] = field(default_factory=list)
    ignore_hidden: bool = True
    max_file_size: str = "1MB"

    # AI provider settings
    api_provider: str = "claude"
    api_options: Dict[str, Any] = field(default_factory=dict)

    # Analysis settings
    cache_enabled: bool = True
    parallel_workers: int = 1
    max_depth: int = 10
    verbose: bool = False

    # Logging settings
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    def get_max_file_size_bytes(self) -> int:
        """Convert max_file_size to bytes - fail fast on invalid input."""
        size_str = self.max_file_size.upper().strip()

        if not size_str:
            raise ValueError("max_file_size cannot be empty")

        if size_str.endswith("KB"):
            try:
                return int(size_str[:-2]) * 1024
            except ValueError:
                raise ValueError(
                    f"Invalid KB size format: '{self.max_file_size}'. Expected format: '10KB'"
                )
        elif size_str.endswith("MB"):
            try:
                return int(size_str[:-2]) * 1024 * 1024
            except ValueError:
                raise ValueError(
                    f"Invalid MB size format: '{self.max_file_size}'. Expected format: '10MB'"
                )
        elif size_str.endswith("GB"):
            try:
                return int(size_str[:-2]) * 1024 * 1024 * 1024
            except ValueError:
                raise ValueError(
                    f"Invalid GB size format: '{self.max_file_size}'. Expected format: '10GB'"
                )
        else:
            try:
                return int(size_str)
            except ValueError:
                raise ValueError(
                    f"Invalid size format: '{self.max_file_size}'. Expected format: '1024' (bytes) or '10KB/MB/GB'"
                )


class ConfigManager:
    """Manages configuration loading and merging."""

    def __init__(self, config_file: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_file: Optional path to custom config file
        """
        self.config_file = config_file
        self.default_config_path = (
            Path(__file__).parent.parent / "config" / "default.json"
        )

    def load_config(self) -> DigginSettings:
        """Load configuration from default and custom files.

        Returns:
            Merged configuration settings
        """
        # Load default configuration
        default_config = self._load_json_config(self.default_config_path)

        # Load custom configuration if specified
        custom_config = {}
        if self.config_file and self.config_file.exists():
            custom_config = self._load_json_config(self.config_file)

        # Merge configurations (custom overrides default)
        merged_config = {**default_config, **custom_config}

        # Convert to DigginSettings dataclass
        # Handle nested logging configuration
        if "logging" in merged_config:
            logging_config = merged_config.pop("logging")
            merged_config["logging"] = LoggingSettings(**logging_config)

        return DigginSettings(**merged_config)

    def _load_json_config(self, config_path: Path) -> Dict[str, Any]:
        """Load JSON configuration from file.

        Args:
            config_path: Path to JSON configuration file

        Returns:
            Configuration dictionary
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            if config_path == self.default_config_path:
                # Default config is required
                raise RuntimeError(f"Failed to load default configuration: {e}")
            # Other configs are optional
            return {}

    def save_config_template(self, output_path: Path) -> None:
        """Save a configuration template file.

        Args:
            output_path: Where to save the template
        """
        template = {
            "ignore_dirs": [
                "node_modules",
                ".git",
                "dist",
                "build",
                "__pycache__",
                ".pytest_cache",
                "venv",
                ".venv",
                "env",
                ".env",
            ],
            "ignore_files": [
                "*.pyc",
                "*.log",
                ".DS_Store",
                "*.tmp",
                "*.swp",
                "package-lock.json",
                "yarn.lock",
                "uv.lock",
            ],
            "include_extensions": [
                ".py",
                ".js",
                ".ts",
                ".jsx",
                ".tsx",
                ".java",
                ".go",
                ".rs",
            ],
            "max_file_size": "1MB",
            "api_provider": "gemini",
            "api_options": {"model": "gemini-1.5-pro", "max_tokens": 4000},
            "cache_enabled": True,
            "parallel_workers": 1,
            "max_depth": 10,
            "verbose": False,
            "logging": {
                "enabled": True,
                "level": "INFO",
                "log_dir": "logs",
                "max_file_size": "10MB",
                "backup_count": 5,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "ai_command_logging": True,
                "ai_log_format": "readable",
                "ai_log_detail_level": "summary",
                "ai_log_prompt_max_chars": 200,
            },
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
