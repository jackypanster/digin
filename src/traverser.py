"""
Directory traversal and file collection
"""

import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Set
import os

from .config import DigginSettings


class DirectoryTraverser:
    """Handles directory traversal and file collection"""
    
    def __init__(self, settings: DigginSettings):
        self.settings = settings
        self._ignored_dirs = set(settings.ignore_dirs)
        self._ignored_patterns = settings.ignore_files
        self._include_extensions = set(settings.include_extensions)
    
    def get_analysis_order(self, root_path: Path) -> List[Path]:
        """
        Get directories in analysis order (leaf nodes first, then parents)
        
        Args:
            root_path: Root directory to analyze
            
        Returns:
            List of directories in bottom-up order
        """
        all_dirs = self._collect_all_directories(root_path)
        
        # Sort by depth (deeper first for bottom-up analysis)
        return sorted(all_dirs, key=lambda p: (len(p.parts), str(p)), reverse=True)
    
    def _collect_all_directories(self, root_path: Path) -> List[Path]:
        """Collect all directories that should be analyzed"""
        directories = []
        
        def visit_directory(current_dir: Path, depth: int = 0) -> None:
            if depth > self.settings.max_depth:
                return
            
            if self._should_ignore_directory(current_dir):
                return
            
            # Add current directory to analysis list
            directories.append(current_dir)
            
            # Visit subdirectories
            try:
                for item in current_dir.iterdir():
                    if item.is_dir() and not self._should_ignore_directory(item):
                        visit_directory(item, depth + 1)
            except PermissionError:
                # Skip directories we can't read
                pass
        
        visit_directory(root_path)
        return directories
    
    def _should_ignore_directory(self, directory: Path) -> bool:
        """Check if directory should be ignored"""
        dir_name = directory.name
        
        # Check against ignored directory names
        if dir_name in self._ignored_dirs:
            return True
        
        # Check against ignored patterns
        for pattern in self._ignored_patterns:
            if fnmatch.fnmatch(dir_name, pattern):
                return True
        
        # Skip hidden directories (except .git which is already in ignore list)
        if dir_name.startswith('.') and dir_name not in {'.github', '.vscode'}:
            return True
        
        return False
    
    def collect_directory_info(self, directory: Path) -> Dict[str, Any]:
        """
        Collect information about a directory
        
        Args:
            directory: Directory to analyze
            
        Returns:
            Dictionary with directory information
        """
        info = {
            "name": directory.name,
            "path": str(directory),
            "files": [],
            "subdirs": [],
            "total_files": 0,
            "total_size": 0,
        }
        
        try:
            for item in directory.iterdir():
                if item.is_file():
                    if self._should_include_file(item):
                        file_info = self._get_file_info(item)
                        if file_info:
                            info["files"].append(file_info)
                            info["total_files"] += 1
                            info["total_size"] += file_info.get("size", 0)
                
                elif item.is_dir() and not self._should_ignore_directory(item):
                    info["subdirs"].append(item)
        
        except PermissionError:
            # Handle permission errors gracefully
            pass
        
        return info
    
    def _should_include_file(self, file_path: Path) -> bool:
        """Check if file should be included in analysis"""
        file_name = file_path.name
        
        # Check against ignored patterns
        for pattern in self._ignored_patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return False
        
        # Check file extension
        if self._include_extensions:
            return file_path.suffix.lower() in self._include_extensions
        
        # If no extensions specified, include all non-ignored files
        return True
    
    def _get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get information about a file"""
        try:
            stat = file_path.stat()
            file_info = {
                "name": file_path.name,
                "path": str(file_path),
                "extension": file_path.suffix.lower(),
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }
            
            # Check if file size is within limits
            max_size = self._parse_size(self.settings.max_file_size)
            if stat.st_size > max_size:
                file_info["too_large"] = True
            else:
                # Try to read file content for small files
                if self._is_text_file(file_path) and stat.st_size < 50000:  # 50KB limit
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            file_info["content_preview"] = content[:1000]  # First 1KB
                            file_info["line_count"] = len(content.splitlines())
                    except (UnicodeDecodeError, OSError):
                        pass
            
            return file_info
        
        except OSError:
            return None
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '1MB' to bytes"""
        size_str = size_str.upper().strip()
        
        if size_str.endswith('KB'):
            return int(float(size_str[:-2]) * 1024)
        elif size_str.endswith('MB'):
            return int(float(size_str[:-2]) * 1024 * 1024)
        elif size_str.endswith('GB'):
            return int(float(size_str[:-2]) * 1024 * 1024 * 1024)
        else:
            return int(size_str)
    
    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is likely a text file"""
        text_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
            '.cpp', '.c', '.h', '.rb', '.php', '.cs', '.vue', '.svelte',
            '.html', '.css', '.scss', '.less', '.xml', '.json', '.yaml',
            '.yml', '.toml', '.ini', '.cfg', '.conf', '.md', '.txt',
            '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
            '.dockerfile', '.sql', '.r', '.R', '.m', '.swift', '.kt',
        }
        
        return file_path.suffix.lower() in text_extensions
    
    def get_leaf_directories(self, root_path: Path) -> List[Path]:
        """Get only leaf directories (directories with no subdirectories)"""
        all_dirs = self._collect_all_directories(root_path)
        leaf_dirs = []
        
        for directory in all_dirs:
            has_subdirs = False
            try:
                for item in directory.iterdir():
                    if item.is_dir() and not self._should_ignore_directory(item):
                        has_subdirs = True
                        break
            except PermissionError:
                continue
            
            if not has_subdirs:
                leaf_dirs.append(directory)
        
        return leaf_dirs