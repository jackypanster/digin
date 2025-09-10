"""
Configuration management for Digin
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class DigginSettings:
    """Settings for Digin analysis"""
    
    # Core settings
    ignore_dirs: List[str]
    ignore_files: List[str]
    include_extensions: List[str]
    max_file_size: str
    
    # AI provider settings
    api_provider: str
    api_options: Dict[str, Any]
    
    # Analysis settings
    cache_enabled: bool
    parallel_workers: int
    max_depth: int
    verbose: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary"""
        return asdict(self)


class ConfigManager:
    """Manages configuration loading and validation"""
    
    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file
        self.default_config_path = Path(__file__).parent.parent / "config" / "default.json"
    
    def load_config(self) -> DigginSettings:
        """Load configuration from files"""
        # Start with default config
        default_config = self._load_json_config(self.default_config_path)
        
        # Load custom config if provided
        if self.config_file:
            custom_config = self._load_json_config(self.config_file)
            default_config.update(custom_config)
        
        # Look for .digin.json in current directory
        local_config_path = Path(".digin.json")
        if local_config_path.exists():
            local_config = self._load_json_config(local_config_path)
            default_config.update(local_config)
        
        return self._create_settings_from_dict(default_config)
    
    def _load_json_config(self, path: Path) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            if path == self.default_config_path:
                # Return built-in defaults if default config missing
                return self._get_builtin_defaults()
            return {}
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {path}: {e}")
    
    def _create_settings_from_dict(self, config_dict: Dict[str, Any]) -> DigginSettings:
        """Create DigginSettings from configuration dictionary"""
        return DigginSettings(
            ignore_dirs=config_dict.get("ignore_dirs", []),
            ignore_files=config_dict.get("ignore_files", []),
            include_extensions=config_dict.get("include_extensions", []),
            max_file_size=config_dict.get("max_file_size", "1MB"),
            api_provider=config_dict.get("api_provider", "claude"),
            api_options=config_dict.get("api_options", {}),
            cache_enabled=config_dict.get("cache_enabled", True),
            parallel_workers=config_dict.get("parallel_workers", 1),
            max_depth=config_dict.get("max_depth", 10),
            verbose=config_dict.get("verbose", False),
        )
    
    def _get_builtin_defaults(self) -> Dict[str, Any]:
        """Get built-in default configuration"""
        return {
            "ignore_dirs": [
                "node_modules", ".git", "dist", "build", "__pycache__",
                ".pytest_cache", "venv", ".venv", "env", ".env"
            ],
            "ignore_files": [
                "*.pyc", "*.log", ".DS_Store", "*.tmp", "*.swp"
            ],
            "include_extensions": [
                ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go"
            ],
            "max_file_size": "1MB",
            "api_provider": "claude",
            "api_options": {
                "model": "claude-3-sonnet",
                "max_tokens": 4000,
                "append_system_prompt": "ê“úJSONWµ%<	Schema"
            },
            "cache_enabled": True,
            "parallel_workers": 1,
            "max_depth": 10,
            "verbose": False
        }
    
    def save_config(self, settings: DigginSettings, path: Optional[Path] = None) -> None:
        """Save configuration to file"""
        if not path:
            path = Path(".digin.json")
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(settings.to_dict(), f, indent=2, ensure_ascii=False)


def load_default_settings() -> DigginSettings:
    """Quick function to load default settings"""
    manager = ConfigManager()
    return manager.load_config()