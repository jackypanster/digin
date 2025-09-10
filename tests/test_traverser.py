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
            include_extensions=[".py", ".js", ".md", ".json"],
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
    
    def test_should_ignore_hidden_directories(self, traverser):
        """Test hidden directory ignore logic."""
        # Should ignore hidden directories when ignore_hidden=True (default)
        assert traverser._should_ignore_directory(Path(".claude"))
        assert traverser._should_ignore_directory(Path(".cursor"))
        assert traverser._should_ignore_directory(Path(".git"))
        assert traverser._should_ignore_directory(Path(".vscode"))
        assert traverser._should_ignore_directory(Path(".idea"))
        
        # Should not ignore visible directories
        assert not traverser._should_ignore_directory(Path("src"))
        assert not traverser._should_ignore_directory(Path("docs"))
        
    def test_should_ignore_hidden_directories_disabled(self):
        """Test hidden directories are included when ignore_hidden=False."""
        settings = DigginSettings(
            ignore_dirs=["node_modules", ".git", "__pycache__"],
            ignore_files=["*.pyc", "*.log", ".DS_Store"],
            include_extensions=[".py", ".js", ".md"],
            ignore_hidden=False  # Disabled
        )
        traverser = DirectoryTraverser(settings)
        
        # Should not ignore hidden directories when ignore_hidden=False
        assert not traverser._should_ignore_directory(Path(".claude"))
        assert not traverser._should_ignore_directory(Path(".cursor"))
        assert not traverser._should_ignore_directory(Path(".vscode"))
        
        # But still ignore explicitly listed directories
        assert traverser._should_ignore_directory(Path(".git"))  # In ignore_dirs
        assert traverser._should_ignore_directory(Path("node_modules"))
    
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
    
    def test_should_ignore_hidden_files(self, traverser):
        """Test hidden file ignore logic."""
        # Should ignore hidden files when ignore_hidden=True (default)
        assert traverser._should_ignore_file(Path(".DS_Store"))
        assert traverser._should_ignore_file(Path(".eslintrc.js"))  # Has .js extension
        assert traverser._should_ignore_file(Path(".prettierrc.json"))  # Has .json extension
        assert traverser._should_ignore_file(Path(".gitignore"))  # No extension, filtered by include_extensions
        assert traverser._should_ignore_file(Path(".dockerignore"))  # No extension, filtered by include_extensions
        assert traverser._should_ignore_file(Path(".env"))  # No extension, filtered by include_extensions
        
        # Should not ignore visible files
        assert not traverser._should_ignore_file(Path("README.md"))
        assert not traverser._should_ignore_file(Path("main.py"))
        assert not traverser._should_ignore_file(Path("config.json"))

    def test_should_ignore_hidden_files_disabled(self):
        """Test hidden files are included when ignore_hidden=False."""
        settings = DigginSettings(
            ignore_dirs=["node_modules"],
            ignore_files=["*.pyc", "*.log", ".DS_Store"],  # Still explicitly ignore .DS_Store
            include_extensions=[".py", ".js", ".md", ".json"],
            ignore_hidden=False  # Disabled
        )
        traverser = DirectoryTraverser(settings)
        
        # Should not ignore hidden files with valid extensions when ignore_hidden=False
        assert not traverser._should_ignore_file(Path(".eslintrc.js"))  # Has .js extension
        assert not traverser._should_ignore_file(Path(".prettierrc.json"))  # Has .json extension
        
        # But still ignore files without valid extensions (due to include_extensions)
        assert traverser._should_ignore_file(Path(".env"))  # No extension
        assert traverser._should_ignore_file(Path(".gitignore"))  # No extension
        
        # And still ignore explicitly listed files
        assert traverser._should_ignore_file(Path(".DS_Store"))  # In ignore_files
        assert traverser._should_ignore_file(Path("debug.log"))  # Matches *.log pattern
        
    def test_ignore_hidden_priority(self):
        """Test that ignore_hidden check happens before extension check."""
        settings = DigginSettings(
            ignore_dirs=[],
            ignore_files=[],
            include_extensions=[".txt"],  # Only .txt files allowed
            ignore_hidden=True
        )
        traverser = DirectoryTraverser(settings)
        
        # Hidden files should be ignored due to ignore_hidden, regardless of extension filtering
        assert traverser._should_ignore_file(Path(".env"))
        assert traverser._should_ignore_file(Path(".gitignore"))
        assert traverser._should_ignore_file(Path(".config.txt"))  # Hidden, even with valid extension
        
        # Visible files should be filtered by include_extensions
        assert not traverser._should_ignore_file(Path("config.txt"))  # Valid extension
        assert traverser._should_ignore_file(Path("main.py"))  # Invalid extension
    
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
    
    def test_find_leaf_directories_with_hidden(self, tmp_path):
        """Test that hidden directories are excluded from traversal."""
        settings = DigginSettings(
            ignore_dirs=["node_modules"],
            ignore_files=["*.pyc", "*.log"],
            include_extensions=[".py", ".js", ".md"],
            ignore_hidden=True  # Default behavior
        )
        traverser = DirectoryTraverser(settings)
        
        # Create mixed visible and hidden directories
        (tmp_path / "src").mkdir()
        (tmp_path / "docs").mkdir()
        (tmp_path / ".git").mkdir()
        (tmp_path / ".vscode").mkdir()
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".cursor").mkdir()
        
        # Add some files to make directories detectable
        (tmp_path / "src" / "main.py").write_text("print('main')")
        (tmp_path / "docs" / "README.md").write_text("# Docs")
        (tmp_path / ".git" / "config").write_text("[core]")
        (tmp_path / ".vscode" / "settings.json").write_text("{}")
        
        leaf_dirs = traverser.find_leaf_directories(tmp_path)
        relative_paths = [str(d.relative_to(tmp_path)) for d in leaf_dirs]
        
        # Should only find visible directories
        assert "src" in relative_paths
        assert "docs" in relative_paths
        assert ".git" not in relative_paths
        assert ".vscode" not in relative_paths
        assert ".claude" not in relative_paths
        assert ".cursor" not in relative_paths
    
    def test_collect_directory_info_with_hidden_files(self, tmp_path):
        """Test that hidden files are excluded from directory info."""
        settings = DigginSettings(
            ignore_dirs=[],
            ignore_files=[],
            include_extensions=[".py", ".md", ".json"],
            ignore_hidden=True  # Default behavior
        )
        traverser = DirectoryTraverser(settings)
        
        # Create mixed visible and hidden files
        (tmp_path / "main.py").write_text("print('main')")
        (tmp_path / "README.md").write_text("# README")
        (tmp_path / ".env").write_text("SECRET=123")
        (tmp_path / ".gitignore").write_text("*.pyc")
        (tmp_path / ".DS_Store").write_bytes(b'\x00\x01\x02')
        (tmp_path / ".vscode").mkdir()
        
        info = traverser.collect_directory_info(tmp_path)
        
        # Should only include visible files
        file_names = [f["name"] for f in info["files"]]
        assert "main.py" in file_names
        assert "README.md" in file_names
        assert ".env" not in file_names
        assert ".gitignore" not in file_names
        assert ".DS_Store" not in file_names
        
        # Should not include hidden subdirectories
        subdir_names = [d["name"] for d in info["subdirs"]]
        assert ".vscode" not in subdir_names
