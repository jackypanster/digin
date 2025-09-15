"""Tests for cache management functionality."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cache import CacheManager
from src.config import DigginSettings


class TestCacheManager:
    """Test CacheManager functionality."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return DigginSettings(
            cache_enabled=True,
            ignore_files=["*.pyc", "*.log"],
            include_extensions=[".py", ".js", ".md"],
        )

    @pytest.fixture
    def cache_manager(self, settings):
        """Create CacheManager instance."""
        return CacheManager(settings)

    def test_cache_disabled(self):
        """Test cache manager with caching disabled."""
        settings = DigginSettings(cache_enabled=False)
        cache_manager = CacheManager(settings)

        # Should return None when cache is disabled
        result = cache_manager.get_cached_digest(Path("/test"))
        assert result is None

    def test_get_cached_digest_missing_files(self, cache_manager, tmp_path):
        """Test getting cached digest when files are missing."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # No digest.json or .digin_hash files
        result = cache_manager.get_cached_digest(test_dir)
        assert result is None

    def test_get_cached_digest_invalid_hash(self, cache_manager, tmp_path):
        """Test getting cached digest with invalid hash."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create digest and hash files
        digest_path = test_dir / "digest.json"
        hash_path = test_dir / ".digin_hash"

        digest_data = {"name": "test", "summary": "test module"}
        with open(digest_path, "w") as f:
            json.dump(digest_data, f)

        with open(hash_path, "w") as f:
            f.write("invalid_hash")

        # Add a file to change the hash
        (test_dir / "test.py").write_text("print('hello')")

        result = cache_manager.get_cached_digest(test_dir)
        assert result is None

    def test_get_cached_digest_valid(self, cache_manager, tmp_path):
        """Test getting valid cached digest."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create test file
        test_file = test_dir / "test.py"
        test_file.write_text("print('hello')")

        # Calculate correct hash
        correct_hash = cache_manager._calculate_directory_hash(test_dir)

        # Create digest and hash files
        digest_data = {"name": "test", "summary": "test module"}

        digest_path = test_dir / "digest.json"
        with open(digest_path, "w") as f:
            json.dump(digest_data, f)

        hash_path = test_dir / ".digin_hash"
        with open(hash_path, "w") as f:
            f.write(correct_hash)

        result = cache_manager.get_cached_digest(test_dir)
        assert result == digest_data

    def test_save_digest(self, cache_manager, tmp_path):
        """Test saving digest to cache."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create test file
        (test_dir / "test.py").write_text("print('hello')")

        digest_data = {"name": "test", "summary": "test module"}

        cache_manager.save_digest(test_dir, digest_data)

        # Check files were created
        digest_path = test_dir / "digest.json"
        hash_path = test_dir / ".digin_hash"

        assert digest_path.exists()
        assert hash_path.exists()

        # Verify digest content
        with open(digest_path, "r") as f:
            saved_digest = json.load(f)
        assert saved_digest == digest_data

        # Verify hash
        with open(hash_path, "r") as f:
            saved_hash = f.read().strip()

        expected_hash = cache_manager._calculate_directory_hash(test_dir)
        assert saved_hash == expected_hash

    def test_save_digest_disabled(self):
        """Test save digest when caching is disabled."""
        settings = DigginSettings(cache_enabled=False)
        cache_manager = CacheManager(settings)

        # Should not raise error, just do nothing
        cache_manager.save_digest(Path("/test"), {"name": "test"})

    def test_clear_cache(self, cache_manager, tmp_path):
        """Test clearing cache files."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create cache files
        digest_path = test_dir / "digest.json"
        hash_path = test_dir / ".digin_hash"

        digest_path.write_text('{"name": "test"}')
        hash_path.write_text("test_hash")

        cache_manager.clear_cache(test_dir)

        assert not digest_path.exists()
        assert not hash_path.exists()

    def test_clear_cache_recursive(self, cache_manager, tmp_path):
        """Test clearing cache recursively."""
        # Create nested structure with cache files
        (tmp_path / "app" / "services").mkdir(parents=True)
        (tmp_path / "app" / "utils").mkdir(parents=True)

        # Create cache files in multiple directories
        for subdir in ["app", "app/services", "app/utils"]:
            dir_path = tmp_path / subdir
            (dir_path / "digest.json").write_text('{"name": "test"}')
            (dir_path / ".digin_hash").write_text("test_hash")

        cache_manager.clear_cache(tmp_path, recursive=True)

        # All cache files should be gone
        assert not (tmp_path / "app" / "digest.json").exists()
        assert not (tmp_path / "app" / "services" / "digest.json").exists()
        assert not (tmp_path / "app" / "utils" / "digest.json").exists()

    def test_calculate_directory_hash(self, cache_manager, tmp_path):
        """Test directory hash calculation."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create files
        (test_dir / "test.py").write_text("print('hello')")
        (test_dir / "README.md").write_text("# Test")

        hash1 = cache_manager._calculate_directory_hash(test_dir)

        # Hash should be consistent
        hash2 = cache_manager._calculate_directory_hash(test_dir)
        assert hash1 == hash2

        # Changing content should change hash
        (test_dir / "test.py").write_text("print('goodbye')")
        hash3 = cache_manager._calculate_directory_hash(test_dir)
        assert hash1 != hash3

        # Adding file should change hash
        (test_dir / "new.js").write_text("console.log('new');")
        hash4 = cache_manager._calculate_directory_hash(test_dir)
        assert hash3 != hash4

    def test_hash_ignores_cache_files(self, cache_manager, tmp_path):
        """Test that hash ignores its own cache files."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create regular file
        (test_dir / "test.py").write_text("print('hello')")

        hash1 = cache_manager._calculate_directory_hash(test_dir)

        # Add cache files
        (test_dir / "digest.json").write_text('{"name": "test"}')
        (test_dir / ".digin_hash").write_text("some_hash")

        hash2 = cache_manager._calculate_directory_hash(test_dir)

        # Hash should be the same (cache files ignored)
        assert hash1 == hash2

    def test_hash_respects_ignore_patterns(self, cache_manager, tmp_path):
        """Test that hash respects ignore patterns."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Create files
        (test_dir / "test.py").write_text("print('hello')")  # Should be included

        hash1 = cache_manager._calculate_directory_hash(test_dir)

        # Add ignored files
        (test_dir / "cache.pyc").write_text("cached")  # Should be ignored
        (test_dir / "debug.log").write_text("logs")  # Should be ignored

        hash2 = cache_manager._calculate_directory_hash(test_dir)

        # Hash should be the same (ignored files don't affect hash)
        assert hash1 == hash2

    def test_get_cache_stats(self, cache_manager, tmp_path):
        """Test getting cache statistics."""
        # Create directory structure with mixed cache states
        (tmp_path / "app").mkdir()
        (tmp_path / "lib").mkdir()
        (tmp_path / "tests").mkdir()

        # Valid cache
        (tmp_path / "app" / "main.py").write_text("print('app')")
        valid_hash = cache_manager._calculate_directory_hash(tmp_path / "app")
        (tmp_path / "app" / "digest.json").write_text('{"name": "app"}')
        (tmp_path / "app" / ".digin_hash").write_text(valid_hash)

        # Invalid cache (wrong hash)
        (tmp_path / "lib" / "utils.py").write_text("def util(): pass")
        (tmp_path / "lib" / "digest.json").write_text('{"name": "lib"}')
        (tmp_path / "lib" / ".digin_hash").write_text("wrong_hash")

        # Missing hash
        (tmp_path / "tests" / "test.py").write_text("def test(): pass")
        (tmp_path / "tests" / "digest.json").write_text('{"name": "tests"}')

        stats = cache_manager.get_cache_stats(tmp_path)

        assert stats["total_digests"] == 3
        assert stats["cached_digests"] == 1
        assert stats["invalid_caches"] == 1
        assert stats["missing_hashes"] == 1

    def test_permission_error_handling(self, cache_manager, tmp_path):
        """Test handling of permission errors."""
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            # Should not raise error
            result = cache_manager.get_cached_digest(test_dir)
            assert result is None

            # Save should also not raise error
            cache_manager.save_digest(test_dir, {"name": "test"})

    def test_is_text_file(self, cache_manager):
        """Test text file detection."""
        assert cache_manager._is_text_file(Path("test.py"))
        assert cache_manager._is_text_file(Path("app.js"))
        assert cache_manager._is_text_file(Path("README.md"))
        assert cache_manager._is_text_file(Path("config.json"))

        assert not cache_manager._is_text_file(Path("image.png"))
        assert not cache_manager._is_text_file(Path("data.bin"))
