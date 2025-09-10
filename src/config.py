"""Configuration management for digin."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class DigginSettings:
    """Configuration settings for digin."""
    
    # Directory and file filtering
    ignore_dirs: List[str] = field(default_factory=list)
    ignore_files: List[str] = field(default_factory=list)
    include_extensions: List[str] = field(default_factory=list)
    max_file_size: str = "1MB"
    
    # AI provider settings
    api_provider: str = "claude"
    api_options: Dict[str, Any] = field(default_factory=dict)
    
    # Analysis settings
    cache_enabled: bool = True
    parallel_workers: int = 1
    max_depth: int = 10
    verbose: bool = False
    
    def get_max_file_size_bytes(self) -> int:
        """Convert max_file_size to bytes."""
        size_str = self.max_file_size.upper()
        if size_str.endswith("KB"):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith("MB"):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith("GB"):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)


class ConfigManager:
    """Manages configuration loading and merging."""
    
    def __init__(self, config_file: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_file: Optional path to custom config file
        """
        self.config_file = config_file
        self.default_config_path = Path(__file__).parent.parent / "config" / "default.json"
        
    def load_config(self) -> DigginSettings:
        """Load configuration from default and custom files.
        
        Returns:
            Merged configuration settings
        """
        # Load default configuration
        default_config = self._load_json_config(self.default_config_path)
        
        # Load project-specific configuration if exists
        project_config = {}
        project_config_path = Path.cwd() / ".digin.json"
        if project_config_path.exists():
            project_config = self._load_json_config(project_config_path)
        
        # Load custom configuration if specified
        custom_config = {}
        if self.config_file and self.config_file.exists():
            custom_config = self._load_json_config(self.config_file)
        
        # Merge configurations (custom overrides project overrides default)
        merged_config = {**default_config, **project_config, **custom_config}
        
        # Convert to DigginSettings dataclass
        return DigginSettings(**merged_config)
    
    def _load_json_config(self, config_path: Path) -> Dict[str, Any]:
        """Load JSON configuration from file.
        
        Args:
            config_path: Path to JSON configuration file
            
        Returns:
            Configuration dictionary
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
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
                "node_modules", ".git", "dist", "build", "__pycache__",
                ".pytest_cache", "venv", ".venv", "env", ".env"
            ],
            "ignore_files": [
                "*.pyc", "*.log", ".DS_Store", "*.tmp", "*.swp",
                "package-lock.json", "yarn.lock", "uv.lock"
            ],
            "include_extensions": [
                ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs"
            ],
            "max_file_size": "1MB",
            "api_provider": "claude",
            "api_options": {
                "model": "claude-3-sonnet",
                "max_tokens": 4000
            },
            "cache_enabled": True,
            "parallel_workers": 1,
            "max_depth": 10,
            "verbose": False
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2, ensure_ascii=False)