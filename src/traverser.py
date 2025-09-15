"""目錄遍歷與文件信息收集。

業務邏輯：
- 忽略規則：隱藏文件/夾、ignore_dirs/ignore_files、include_extensions 白名單。
- 葉子判定：無可分析子目錄即為葉子；供「自底向上」序列使用。
- 收集信息：文件名、大小、擴展名、是否文本、最多 2KB 內容預覽；統計文件數/總大小。
- 僅針對小文本讀取片段，避免大文件 I/O 開銷。

設計意圖：為 AI 準備足夠上下文，同時控制 IO 與成本。
"""

import fnmatch
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DigginSettings
from .logger import get_logger


class DirectoryTraverser:
    """Handles directory scanning and file collection."""

    def __init__(self, settings: DigginSettings):
        """Initialize directory traverser.

        Args:
            settings: Configuration settings
        """
        self.settings = settings
        self.logger = get_logger("traverser")

    def find_leaf_directories(self, root_path: Path) -> List[Path]:
        """Find all leaf directories (directories with no subdirectories).

        Args:
            root_path: Root directory to scan

        Returns:
            List of leaf directory paths
        """
        leaf_dirs = []

        def _scan_directory(directory: Path):
            """Recursively scan directory, avoiding ignored ones."""
            try:
                subdirs = []
                for child in directory.iterdir():
                    if child.is_dir() and not self._should_ignore_directory(child):
                        subdirs.append(child)
            except PermissionError:
                self.logger.warning(f"Permission denied accessing directory: {directory}")
                return

            # If no subdirectories, this is a leaf
            if not subdirs:
                leaf_dirs.append(directory)
                return

            # Otherwise, recursively scan subdirectories
            for subdir in subdirs:
                _scan_directory(subdir)

        # Start scanning from root, but check if root itself should be processed
        if not self._should_ignore_directory(root_path):
            _scan_directory(root_path)

        return sorted(leaf_dirs)

    def get_analysis_order(self, root_path: Path) -> List[Path]:
        """Get directories in bottom-up analysis order."""
        leaf_dirs = self.find_leaf_directories(root_path)
        analysis_order = leaf_dirs.copy()
        processed = set(leaf_dirs)
        current_level = leaf_dirs

        while current_level:
            next_level = self._get_next_level_parents(
                current_level, processed, root_path
            )
            analysis_order.extend(next_level)
            current_level = next_level

        if root_path not in analysis_order:
            analysis_order.append(root_path)

        return analysis_order

    def _get_next_level_parents(
        self, current_level: List[Path], processed: set, root_path: Path
    ) -> List[Path]:
        """Get parent directories ready for next level processing."""
        next_level = []

        for directory in current_level:
            parent = directory.parent

            if self._should_skip_parent(parent, root_path, processed):
                continue

            if (
                self._all_children_processed(parent, processed)
                and parent not in next_level
            ):
                next_level.append(parent)
                processed.add(parent)

        return next_level

    def _should_skip_parent(
        self, parent: Path, root_path: Path, processed: set
    ) -> bool:
        """Check if parent should be skipped."""
        return (
            parent == root_path.parent
            or parent in processed
            or self._should_ignore_directory(parent)
        )

    def _all_children_processed(self, parent: Path, processed: set) -> bool:
        """Check if all children of parent have been processed."""
        try:
            for child in parent.iterdir():
                if (
                    child.is_dir()
                    and not self._should_ignore_directory(child)
                    and child not in processed
                ):
                    return False
            return True
        except PermissionError:
            return False

    def collect_directory_info(self, directory: Path) -> Dict[str, Any]:
        """Collect detailed information about a directory.

        Args:
            directory: Directory to analyze

        Returns:
            Dictionary containing directory information
        """
        info = {
            "path": str(directory),
            "name": directory.name,
            "files": [],
            "subdirs": [],
            "total_files": 0,
            "total_size": 0,
        }

        try:
            for item in directory.iterdir():
                if item.is_file() and not self._should_ignore_file(item):
                    file_info = self._collect_file_info(item)
                    if file_info:
                        info["files"].append(file_info)
                        info["total_files"] += 1
                        info["total_size"] += file_info.get("size", 0)

                elif item.is_dir() and not self._should_ignore_directory(item):
                    info["subdirs"].append({"name": item.name, "path": str(item)})
        except PermissionError:
            pass

        return info

    def _collect_file_info(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Collect information about a single file.

        Args:
            file_path: File to analyze

        Returns:
            File information dictionary or None if file should be skipped
        """
        try:
            stat = file_path.stat()
            max_size = self.settings.get_max_file_size_bytes()

            # Skip files that are too large
            if stat.st_size > max_size:
                self.logger.debug(f"Skipping large file ({stat.st_size} bytes): {file_path}")
                return None

            file_info = {
                "name": file_path.name,
                "path": str(file_path),
                "size": stat.st_size,
                "extension": file_path.suffix.lower(),
                "is_text": self._is_text_file(file_path),
            }

            # Add content preview for text files with generous limits for AI analysis
            # Use larger limits for modern AI models with large context windows
            max_file_size = 100 * 1024  # 100KB per file (up from 8KB)
            max_content_read = 50 * 1024  # Read up to 50KB per file (up from 2KB)

            if file_info["is_text"] and stat.st_size <= max_file_size:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(max_content_read)
                        if content.strip():
                            file_info["content_preview"] = content
                except (UnicodeDecodeError, PermissionError) as e:
                    self.logger.debug(f"Failed to read content preview for {file_path}: {e}")
                    pass

            return file_info

        except (OSError, PermissionError):
            return None

    def _should_ignore_directory(self, directory: Path) -> bool:
        """Check if directory should be ignored.

        Args:
            directory: Directory to check

        Returns:
            True if directory should be ignored
        """
        dir_name = directory.name

        # Check if it's a hidden directory (starts with .)
        if self.settings.ignore_hidden and dir_name.startswith("."):
            return True

        # Check against ignore patterns
        for pattern in self.settings.ignore_dirs:
            if fnmatch.fnmatch(dir_name, pattern):
                return True

        return False

    # Public wrappers for cross-module use (avoid private access)
    def should_ignore_directory(self, directory: Path) -> bool:
        """Public: whether directory should be ignored (wrapper)."""
        return self._should_ignore_directory(directory)

    def should_ignore_file(self, file_path: Path) -> bool:
        """Public: whether file should be ignored (wrapper)."""
        return self._should_ignore_file(file_path)

    def _should_ignore_file(self, file_path: Path) -> bool:
        """Check if file should be ignored.

        Args:
            file_path: File to check

        Returns:
            True if file should be ignored
        """
        file_name = file_path.name
        extension = file_path.suffix.lower()

        # Check if it's a hidden file (starts with .)
        if self.settings.ignore_hidden and file_name.startswith("."):
            return True

        # Check against ignore patterns
        for pattern in self.settings.ignore_files:
            if fnmatch.fnmatch(file_name, pattern):
                return True

        # Check if extension is in include list
        if self.settings.include_extensions:
            return extension not in self.settings.include_extensions

        return False

    def _is_text_file(self, file_path: Path) -> bool:
        """Determine if file is a text file.

        Args:
            file_path: File to check

        Returns:
            True if file appears to be text
        """
        # Check by extension first
        extension = file_path.suffix.lower()
        if extension in self.settings.include_extensions:
            return True

        # Use mimetypes to guess
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type.startswith("text/"):
            return True

        # Try to read a small sample
        try:
            with open(file_path, "rb") as f:
                sample = f.read(1024)
                # Check if sample contains mostly printable characters
                if len(sample) == 0:
                    return True

                text_chars = sum(
                    1 for byte in sample if byte in b"\t\n\r" or 32 <= byte <= 126
                )
                return text_chars / len(sample) > 0.7
        except (OSError, PermissionError):
            return False
