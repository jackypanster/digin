"""摘要緩存管理（目錄級）。

業務邏輯：
- 以目錄內「相對路徑 + 元信息（mtime/size）+ 小文本文件內容（≤8KB）」計算哈希。
- 命中：返回現有 `digest.json`；不一致：視為失效重新計算。
- 存儲：寫入 `digest.json` 與 `.digin_hash`；支持遞歸清理與緩存統計。

目的：降低重複 AI 調用成本，支撐可預期的增量分析工作流。
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DigginSettings
from .logger import get_logger


class CacheManager:
    """Manages digest caching using file content hashing."""

    def __init__(self, settings: DigginSettings):
        """Initialize cache manager.

        Args:
            settings: Configuration settings
        """
        self.settings = settings
        self.cache_enabled = settings.cache_enabled
        self.logger = get_logger("cache")

    def get_cached_digest(self, directory: Path) -> Optional[Dict[str, Any]]:
        """Get cached digest for directory if still valid.

        Args:
            directory: Directory to check cache for

        Returns:
            Cached digest dictionary or None if not cached/invalid
        """
        if not self.cache_enabled:
            self.logger.debug(f"Cache disabled, skipping lookup for: {directory}")
            return None

        digest_path = directory / "digest.json"
        hash_path = directory / ".digin_hash"

        # Check if both files exist
        if not (digest_path.exists() and hash_path.exists()):
            self.logger.debug(f"Cache files missing for: {directory}")
            return None

        # Load stored hash
        with open(hash_path, "r", encoding="utf-8") as f:
            stored_hash = f.read().strip()

        # Calculate current hash
        current_hash = self._calculate_directory_hash(directory)

        # Compare hashes
        if stored_hash != current_hash:
            # Content changed, cache invalid
            self.logger.debug(f"Cache invalid (hash mismatch) for: {directory}")
            return None

        # Load and return cached digest
        with open(digest_path, "r", encoding="utf-8") as f:
            digest = json.load(f)

        self.logger.debug(f"Cache hit for: {directory}")
        if self.settings.verbose:
            print(f"Cache hit for {directory}")

        return digest

    def save_digest(self, directory: Path, digest: Dict[str, Any]) -> None:
        """Save digest and hash to cache.

        Args:
            directory: Directory being cached
            digest: Analysis digest to save
        """
        if not self.cache_enabled:
            self.logger.debug(f"Cache disabled, skipping save for: {directory}")
            return

        # Save digest
        digest_path = directory / "digest.json"
        with open(digest_path, "w", encoding="utf-8") as f:
            json.dump(digest, f, indent=2, ensure_ascii=False)

        # Save hash
        directory_hash = self._calculate_directory_hash(directory)
        hash_path = directory / ".digin_hash"
        with open(hash_path, "w", encoding="utf-8") as f:
            f.write(directory_hash)

        self.logger.debug(f"Saved cache for: {directory}")
        if self.settings.verbose:
            print(f"Cached digest for {directory}")

    def clear_cache(self, directory: Path, recursive: bool = False) -> None:
        """Clear cache files for directory.

        Args:
            directory: Directory to clear cache for
            recursive: Whether to clear caches recursively
        """

        def clear_single_dir(dir_path: Path) -> None:
            """Clear cache for a single directory."""
            digest_path = dir_path / "digest.json"
            hash_path = dir_path / ".digin_hash"

            try:
                if digest_path.exists():
                    digest_path.unlink()
                if hash_path.exists():
                    hash_path.unlink()
            except PermissionError:
                pass

        clear_single_dir(directory)

        if recursive:
            for item in directory.rglob("*"):
                if item.is_dir():
                    clear_single_dir(item)

    def _calculate_directory_hash(self, directory: Path) -> str:
        """Calculate hash for directory contents including child digests and configuration."""
        hasher = hashlib.sha256()

        # Include configuration that affects analysis output
        config_items = [
            f"narrative_enabled:{self.settings.narrative_enabled}",
            f"api_provider:{self.settings.api_provider}",
        ]
        for item in sorted(config_items):
            hasher.update(item.encode("utf-8"))

        files_to_hash = self._get_files_to_hash(directory)

        # Hash each file's metadata and content
        for file_path in files_to_hash:
            self._hash_single_file(hasher, file_path, directory)

        # Include child directory hashes to invalidate parent on child changes
        try:
            for child in directory.iterdir():
                if child.is_dir():
                    child_hash_file = child / ".digin_hash"
                    if child_hash_file.exists():
                        hasher.update(
                            str(child_hash_file.relative_to(directory)).encode("utf-8")
                        )
                        hasher.update(child_hash_file.read_bytes())
        except PermissionError:
            pass

        return hasher.hexdigest()

    def _get_files_to_hash(self, directory: Path) -> List[Path]:
        """Get sorted list of files to include in hash."""
        files_to_hash = []

        for item in directory.iterdir():
            if item.is_file() and not self._should_ignore_for_hash(item):
                files_to_hash.append(item)

        files_to_hash.sort(key=lambda p: str(p))
        return files_to_hash

    def _hash_single_file(
        self, hasher: hashlib.sha256, file_path: Path, directory: Path
    ) -> None:
        """Hash a single file's metadata and optionally content."""
        rel_path = file_path.relative_to(directory)
        hasher.update(str(rel_path).encode("utf-8"))

        stat = file_path.stat()
        hasher.update(str(stat.st_mtime).encode("utf-8"))
        hasher.update(str(stat.st_size).encode("utf-8"))

        if stat.st_size <= 8192 and self._is_text_file(file_path):
            self._hash_file_content(hasher, file_path)

    def _hash_file_content(self, hasher: hashlib.sha256, file_path: Path) -> None:
        """Hash file content for small text files."""
        with open(file_path, "rb") as f:
            content = f.read()
            hasher.update(content)

    def _should_ignore_for_hash(self, file_path: Path) -> bool:
        """Check if file should be ignored when calculating hash.

        Args:
            file_path: File to check

        Returns:
            True if file should be ignored for hashing
        """
        file_name = file_path.name

        # Always ignore our own cache files
        if file_name in ("digest.json", ".digin_hash"):
            return True

        # Use same ignore logic as traverser
        return self._should_ignore_file_by_patterns(file_path)

    def _should_ignore_file_by_patterns(self, file_path: Path) -> bool:
        """Check file against ignore patterns."""
        import fnmatch

        file_name = file_path.name
        extension = file_path.suffix.lower()

        # Check against ignore patterns
        for pattern in self.settings.ignore_files:
            if fnmatch.fnmatch(file_name, pattern):
                return True

        # Check if extension is in include list
        if self.settings.include_extensions:
            return extension not in self.settings.include_extensions

        return False

    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is text file (for content hashing)."""
        extension = file_path.suffix.lower()

        # Check if extension is in our include list
        if extension in self.settings.include_extensions:
            return True

        # Check common text extensions
        text_extensions = {
            ".txt",
            ".md",
            ".rst",
            ".json",
            ".yaml",
            ".yml",
            ".xml",
            ".html",
            ".css",
            ".js",
            ".py",
            ".java",
            ".c",
            ".cpp",
            ".h",
        }

        return extension in text_extensions

    def get_cache_stats(self, root_directory: Path) -> Dict[str, int]:
        """Get cache statistics for directory tree.

        Args:
            root_directory: Root directory to check

        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "total_digests": 0,
            "cached_digests": 0,
            "invalid_caches": 0,
            "missing_hashes": 0,
        }

        for directory in root_directory.rglob("*"):
            if not directory.is_dir():
                continue

            digest_path = directory / "digest.json"
            hash_path = directory / ".digin_hash"

            if digest_path.exists():
                stats["total_digests"] += 1

                if hash_path.exists():
                    # Check if cache is valid
                    try:
                        with open(hash_path, "r", encoding="utf-8") as f:
                            stored_hash = f.read().strip()
                        current_hash = self._calculate_directory_hash(directory)

                        if stored_hash == current_hash:
                            stats["cached_digests"] += 1
                        else:
                            stats["invalid_caches"] += 1
                    except (OSError, PermissionError):
                        stats["invalid_caches"] += 1
                else:
                    stats["missing_hashes"] += 1

        return stats
