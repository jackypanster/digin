"""Directory traversal and file collection for codebase analysis."""

import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional
import mimetypes

from .config import DigginSettings


class DirectoryTraverser:
    """Handles directory scanning and file collection."""
    
    def __init__(self, settings: DigginSettings):
        """Initialize directory traverser.
        
        Args:
            settings: Configuration settings
        """
        self.settings = settings
        
    def find_leaf_directories(self, root_path: Path) -> List[Path]:
        """Find all leaf directories (directories with no subdirectories).
        
        Args:
            root_path: Root directory to scan
            
        Returns:
            List of leaf directory paths
        """
        leaf_dirs = []
        
        for path in root_path.rglob("*"):
            if not path.is_dir() or self._should_ignore_directory(path):
                continue
                
            # Check if this directory has any non-ignored subdirectories
            has_subdirs = False
            try:
                for child in path.iterdir():
                    if (child.is_dir() and 
                        not self._should_ignore_directory(child)):
                        has_subdirs = True
                        break
            except PermissionError:
                continue
                
            if not has_subdirs:
                leaf_dirs.append(path)
                
        return sorted(leaf_dirs)
    
    def get_analysis_order(self, root_path: Path) -> List[Path]:
        """Get directories in bottom-up analysis order.
        
        Args:
            root_path: Root directory to analyze
            
        Returns:
            List of directories in analysis order (leaf to root)
        """
        # Start with leaf directories
        leaf_dirs = self.find_leaf_directories(root_path)
        analysis_order = leaf_dirs.copy()
        
        # Add parent directories level by level
        processed = set(leaf_dirs)
        current_level = leaf_dirs
        
        while current_level:
            next_level = []
            for directory in current_level:
                parent = directory.parent
                
                # Skip if parent is root or already processed
                if (parent == root_path.parent or 
                    parent in processed or
                    self._should_ignore_directory(parent)):
                    continue
                
                # Check if all children of this parent have been processed
                all_children_processed = True
                try:
                    for child in parent.iterdir():
                        if (child.is_dir() and 
                            not self._should_ignore_directory(child) and
                            child not in processed):
                            all_children_processed = False
                            break
                except PermissionError:
                    continue
                
                if all_children_processed and parent not in next_level:
                    next_level.append(parent)
                    processed.add(parent)
            
            analysis_order.extend(next_level)
            current_level = next_level
        
        # Ensure root directory is last if not already included
        if root_path not in analysis_order:
            analysis_order.append(root_path)
            
        return analysis_order
    
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
            "total_size": 0
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
                    info["subdirs"].append({
                        "name": item.name,
                        "path": str(item)
                    })
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
                return None
            
            file_info = {
                "name": file_path.name,
                "path": str(file_path),
                "size": stat.st_size,
                "extension": file_path.suffix.lower(),
                "is_text": self._is_text_file(file_path)
            }
            
            # Add content preview for small text files
            if (file_info["is_text"] and 
                stat.st_size <= 8192):  # 8KB preview limit
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(2048)  # First 2KB
                        if content.strip():
                            file_info["content_preview"] = content
                except (UnicodeDecodeError, PermissionError):
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
        
        # Check against ignore patterns
        for pattern in self.settings.ignore_dirs:
            if fnmatch.fnmatch(dir_name, pattern):
                return True
                
        return False
    
    def _should_ignore_file(self, file_path: Path) -> bool:
        """Check if file should be ignored.
        
        Args:
            file_path: File to check
            
        Returns:
            True if file should be ignored
        """
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
        if mime_type and mime_type.startswith('text/'):
            return True
            
        # Try to read a small sample
        try:
            with open(file_path, 'rb') as f:
                sample = f.read(1024)
                # Check if sample contains mostly printable characters
                if len(sample) == 0:
                    return True
                    
                text_chars = sum(1 for byte in sample if byte in b'\t\n\r' or 32 <= byte <= 126)
                return text_chars / len(sample) > 0.7
        except (OSError, PermissionError):
            return False