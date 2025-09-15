"""Tests for configuration management."""

import json
from pathlib import Path

import pytest

from src.config import ConfigManager, DigginSettings


class TestDigginSettings:
    """Test DigginSettings dataclass."""

    def test_default_settings(self):
        """Test default settings creation."""
        settings = DigginSettings()

        assert settings.api_provider == "claude"
        assert settings.cache_enabled is True
        assert settings.parallel_workers == 1
        assert settings.verbose is False

    def test_get_max_file_size_bytes(self):
        """Test file size conversion."""
        settings = DigginSettings()

        # Test default
        settings.max_file_size = "1MB"
        assert settings.get_max_file_size_bytes() == 1024 * 1024

        # Test KB
        settings.max_file_size = "512KB"
        assert settings.get_max_file_size_bytes() == 512 * 1024

        # Test GB
        settings.max_file_size = "2GB"
        assert settings.get_max_file_size_bytes() == 2 * 1024 * 1024 * 1024

        # Test plain bytes
        settings.max_file_size = "2048"
        assert settings.get_max_file_size_bytes() == 2048


class TestConfigManager:
    """Test ConfigManager functionality."""

    def test_load_default_config(self, tmp_path):
        """Test loading default configuration."""
        # Create temporary default config
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_config = config_dir / "default.json"

        config_data = {
            "api_provider": "claude",
            "cache_enabled": True,
            "verbose": False,
            "ignore_dirs": ["node_modules", ".git"],
        }

        with open(default_config, "w") as f:
            json.dump(config_data, f)

        # Mock the default config path
        manager = ConfigManager()
        manager.default_config_path = default_config

        settings = manager.load_config()

        assert settings.api_provider == "claude"
        assert settings.cache_enabled is True
        assert "node_modules" in settings.ignore_dirs

    def test_load_project_config_override(self, tmp_path):
        """Test project config overriding default."""
        # Create default config
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_config = config_dir / "default.json"

        with open(default_config, "w") as f:
            json.dump({"api_provider": "claude", "verbose": False}, f)

        # Create project config
        project_config = tmp_path / ".digin.json"
        with open(project_config, "w") as f:
            json.dump({"api_provider": "gemini", "cache_enabled": False}, f)

        # Change to temp directory
        import os

        old_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            manager = ConfigManager()
            manager.default_config_path = default_config

            settings = manager.load_config()

            # Project config should override default
            assert settings.api_provider == "gemini"
            assert settings.cache_enabled is False
            assert settings.verbose is False  # From default
        finally:
            os.chdir(old_cwd)

    def test_load_custom_config(self, tmp_path):
        """Test loading custom config file."""
        # Create default config
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_config = config_dir / "default.json"

        with open(default_config, "w") as f:
            json.dump({"api_provider": "claude"}, f)

        # Create custom config
        custom_config = tmp_path / "custom.json"
        with open(custom_config, "w") as f:
            json.dump({"api_provider": "gemini", "verbose": True}, f)

        manager = ConfigManager(config_file=custom_config)
        manager.default_config_path = default_config

        settings = manager.load_config()

        assert settings.api_provider == "gemini"
        assert settings.verbose is True

    def test_missing_default_config(self):
        """Test error when default config is missing."""
        manager = ConfigManager()
        manager.default_config_path = Path("/nonexistent/default.json")

        with pytest.raises(RuntimeError, match="Failed to load default configuration"):
            manager.load_config()

    def test_invalid_json_config(self, tmp_path):
        """Test handling of invalid JSON in optional configs."""
        # Create valid default config
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        default_config = config_dir / "default.json"

        with open(default_config, "w") as f:
            json.dump({"api_provider": "claude"}, f)

        # Create invalid project config
        project_config = tmp_path / ".digin.json"
        with open(project_config, "w") as f:
            f.write("invalid json {")

        import os

        old_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            manager = ConfigManager()
            manager.default_config_path = default_config

            # Should not raise error, just ignore invalid project config
            settings = manager.load_config()
            assert settings.api_provider == "claude"
        finally:
            os.chdir(old_cwd)

    def test_save_config_template(self, tmp_path):
        """Test saving configuration template."""
        manager = ConfigManager()
        template_path = tmp_path / "template.json"

        manager.save_config_template(template_path)

        assert template_path.exists()

        # Load and verify template
        with open(template_path, "r") as f:
            template = json.load(f)

        assert "ignore_dirs" in template
        assert "api_provider" in template
        assert "cache_enabled" in template
        assert template["api_provider"] == "gemini"
