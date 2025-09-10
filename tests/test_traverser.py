"""Tests for directory traversal functionality."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.config import DigginSettings
from src.traverser import DirectoryTraverser


class TestDirectoryTraverser:
    """Test DirectoryTraverser functionality."""
    
    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return DigginSettings(
            ignore_dirs=["node_modules", ".git", "__pycache__"],
            ignore_files=["*.pyc", "*.log", ".DS_Store"],
            include_extensions=[".py", ".js", ".md"],
            max_file_size="1MB"
        )
    
    @pytest.fixture
    def traverser(self, settings):
        """Create DirectoryTraverser instance."""
        return DirectoryTraverser(settings)
    
    def test_find_leaf_directories(self, traverser, tmp_path):
        """Test finding leaf directories."""
        # Create directory structure
        (tmp_path / "src" / "lib").mkdir(parents=True)
        (tmp_path / "src" / "utils").mkdir(parents=True)
        (tmp_path / "docs").mkdir()
        (tmp_path / "tests" / "unit").mkdir(parents=True)
        (tmp_path / "node_modules").mkdir()  # Should be ignored
        
        # Add files to make directories non-empty
        (tmp_path / "src" / "lib" / "core.py").touch()
        (tmp_path / "src" / "utils" / "helpers.py").touch()
        (tmp_path / "docs" / "README.md").touch()
        (tmp_path / "tests" / "unit" / "test_core.py").touch()
        
        leaf_dirs = traverser.find_leaf_directories(tmp_path)
        
        # Convert to relative paths for easier testing
        relative_paths = [str(d.relative_to(tmp_path)) for d in leaf_dirs]
        
        assert "src/lib" in relative_paths
        assert "src/utils" in relative_paths
        assert "docs" in relative_paths
        assert "tests/unit" in relative_paths
        assert not any("node_modules" in path for path in relative_paths)
    
    def test_get_analysis_order(self, traverser, tmp_path):
        """Test getting analysis order (bottom-up)."""
        # Create nested structure
        (tmp_path / "app" / "services" / "auth").mkdir(parents=True)
        (tmp_path / "app" / "services" / "user").mkdir(parents=True)
        (tmp_path / "app" / "utils").mkdir(parents=True)
        
        # Add files
        (tmp_path / "app" / "services" / "auth" / "login.py").touch()
        (tmp_path / "app" / "services" / "user" / "model.py").touch()
        (tmp_path / "app" / "utils" / "helpers.py").touch()
        (tmp_path / "app" / "main.py").touch()
        
        analysis_order = traverser.get_analysis_order(tmp_path)
        
        # Convert to relative paths
        relative_paths = [str(d.relative_to(tmp_path)) for d in analysis_order]
        
        # Leaf directories should come first
        auth_idx = relative_paths.index("app/services/auth")
        user_idx = relative_paths.index("app/services/user")
        utils_idx = relative_paths.index("app/utils")
        services_idx = relative_paths.index("app/services")
        app_idx = relative_paths.index("app")
        root_idx = relative_paths.index(".")
        
        # Verify bottom-up order
        assert auth_idx < services_idx < app_idx < root_idx
        assert user_idx < services_idx < app_idx < root_idx
        assert utils_idx < app_idx < root_idx
    
    def test_collect_directory_info(self, traverser, tmp_path):
        """Test collecting directory information."""
        # Create test files
        test_dir = tmp_path / "test_module"
        test_dir.mkdir()
        
        # Python file with content
        py_file = test_dir / "module.py"
        py_file.write_text("def hello():\n    return 'world'\n")
        
        # JavaScript file
        js_file = test_dir / "script.js"
        js_file.write_text("console.log('hello');")
        
        # File to ignore
        (test_dir / "cache.pyc").touch()
        
        # Subdirectory
        (test_dir / "subdir").mkdir()
        
        info = traverser.collect_directory_info(test_dir)
        
        assert info["name"] == "test_module"
        assert info["path"] == str(test_dir)
        assert info["total_files"] == 2  # Should not count .pyc file
        
        # Check files
        file_names = [f["name"] for f in info["files"]]
        assert "module.py" in file_names
        assert "script.js" in file_names
        assert "cache.pyc" not in file_names
        
        # Check subdirectories
        assert len(info["subdirs"]) == 1
        assert info["subdirs"][0]["name"] == "subdir"
        
        # Check content preview for small files
        py_file_info = next(f for f in info["files"] if f["name"] == "module.py")
        assert "content_preview" in py_file_info
        assert "def hello" in py_file_info["content_preview"]
    
    def test_should_ignore_directory(self, traverser):
        """Test directory ignore logic."""
        assert traverser._should_ignore_directory(Path("node_modules"))
        assert traverser._should_ignore_directory(Path(".git"))
        assert traverser._should_ignore_directory(Path("__pycache__"))
        assert not traverser._should_ignore_directory(Path("src"))
        assert not traverser._should_ignore_directory(Path("tests"))
    
    def test_should_ignore_file(self, traverser):
        """Test file ignore logic."""
        assert traverser._should_ignore_file(Path("test.pyc"))
        assert traverser._should_ignore_file(Path("debug.log"))
        assert traverser._should_ignore_file(Path(".DS_Store"))
        
        # Test extension filtering
        assert not traverser._should_ignore_file(Path("script.py"))
        assert not traverser._should_ignore_file(Path("app.js"))
        assert not traverser._should_ignore_file(Path("README.md"))
        
        # Files not in include_extensions should be ignored
        assert traverser._should_ignore_file(Path("image.png"))
        assert traverser._should_ignore_file(Path("data.csv"))
    
    def test_is_text_file(self, traverser):
        """Test text file detection."""
        assert traverser._is_text_file(Path("script.py"))
        assert traverser._is_text_file(Path("app.js"))
        assert traverser._is_text_file(Path("README.md"))
        
        # Not in include_extensions
        assert not traverser._is_text_file(Path("image.png"))
        assert not traverser._is_text_file(Path("data.bin"))
    
    def test_large_file_handling(self, traverser, tmp_path):
        """Test handling of large files."""
        large_file = tmp_path / "large.py"
        
        # Create file larger than max_file_size
        large_content = "# Large file\n" * 100000  # Much larger than 1MB when repeated
        large_file.write_text(large_content)
        
        info = traverser.collect_directory_info(tmp_path)
        
        # Large file should be filtered out
        assert info["total_files"] == 0
        assert len(info["files"]) == 0
    
    def test_permission_error_handling(self, traverser, tmp_path, monkeypatch):
        """Test handling of permission errors."""
        test_dir = tmp_path / "restricted"
        test_dir.mkdir()
        
        # Mock permission error
        def mock_iterdir(self):
            raise PermissionError("Access denied")
        
        monkeypatch.setattr(Path, "iterdir", mock_iterdir)
        
        # Should not raise exception
        info = traverser.collect_directory_info(test_dir)
        
        # Should return empty info
        assert info["total_files"] == 0
        assert len(info["files"]) == 0
        assert len(info["subdirs"]) == 0
    
    def test_binary_file_detection(self, traverser, tmp_path):
        """Test binary file detection."""
        # Create binary file
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b'\x00\x01\x02\xFF' * 100)
        
        # Create text file
        text_file = tmp_path / "test.py"
        text_file.write_text("print('hello')")
        
        info = traverser.collect_directory_info(tmp_path)
        
        # Only text file should be included and have content preview
        assert len(info["files"]) == 1
        file_info = info["files"][0]
        assert file_info["name"] == "test.py"
        assert file_info["is_text"] is True
        assert "content_preview" in file_info