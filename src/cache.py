"""
Cache management for analysis results
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Optional

from .config import DigginSettings


class CacheManager:
    """Manages caching of analysis results"""
    
    def __init__(self, settings: DigginSettings):
        self.settings = settings
    
    def get_cached_digest(self, directory: Path) -> Optional[Dict[str, Any]]:
        """
        Get cached digest for directory if valid
        
        Args:
            directory: Directory to check cache for
            
        Returns:
            Cached digest or None if not found/invalid
        """
        if not self.settings.cache_enabled:
            return None
        
        digest_file = directory / "digest.json"
        hash_file = directory / ".hash"
        
        # Check if both files exist
        if not (digest_file.exists() and hash_file.exists()):
            return None
        
        try:
            # Load cached hash
            with open(hash_file, 'r') as f:
                cached_hash = f.read().strip()
            
            # Calculate current hash
            current_hash = self._calculate_directory_hash(directory)
            
            # If hashes match, load digest
            if cached_hash == current_hash:
                with open(digest_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            return None
        
        except (IOError, json.JSONDecodeError, ValueError):
            # If any error occurs, treat as cache miss
            return None
    
    def save_digest(self, directory: Path, digest: Dict[str, Any]) -> bool:
        """
        Save digest and hash for directory
        
        Args:
            directory: Directory to save cache for
            digest: Digest data to save
            
        Returns:
            True if saved successfully
        """
        if not self.settings.cache_enabled:
            return False
        
        try:
            # Save digest
            digest_file = directory / "digest.json"
            with open(digest_file, 'w', encoding='utf-8') as f:
                json.dump(digest, f, indent=2, ensure_ascii=False)
            
            # Save hash
            hash_file = directory / ".hash"
            current_hash = self._calculate_directory_hash(directory)
            with open(hash_file, 'w') as f:
                f.write(current_hash)
            
            return True
        
        except IOError:
            if self.settings.verbose:
                print(f"Failed to save cache for {directory}")
            return False
    
    def _calculate_directory_hash(self, directory: Path) -> str:
        """
        Calculate hash for directory contents
        
        Args:
            directory: Directory to hash
            
        Returns:
            Hash string
        """
        hasher = hashlib.md5()
        
        try:
            # Get all files in directory (excluding cache files)
            files = []
            for item in directory.iterdir():
                if item.is_file() and item.name not in {".hash", "digest.json"}:
                    files.append(item)
            
            # Sort for consistent hashing
            files.sort(key=lambda x: x.name)
            
            # Hash file names and modification times
            for file_path in files:
                try:
                    stat = file_path.stat()
                    hasher.update(file_path.name.encode('utf-8'))
                    hasher.update(str(stat.st_size).encode('utf-8'))
                    hasher.update(str(int(stat.st_mtime)).encode('utf-8'))
                except OSError:
                    # Skip files we can't access
                    continue
            
            return hasher.hexdigest()
        
        except OSError:
            # If we can't read directory, return empty hash
            return ""
    
    def clear_cache(self, directory: Path) -> bool:
        """
        Clear cache files for directory
        
        Args:
            directory: Directory to clear cache for
            
        Returns:
            True if cleared successfully
        """
        try:
            digest_file = directory / "digest.json"
            hash_file = directory / ".hash"
            
            success = True
            if digest_file.exists():
                try:
                    digest_file.unlink()
                except OSError:
                    success = False
            
            if hash_file.exists():
                try:
                    hash_file.unlink()
                except OSError:
                    success = False
            
            return success
        
        except Exception:
            return False
    
    def clear_all_cache(self, root_directory: Path) -> int:
        """
        Clear all cache files recursively
        
        Args:
            root_directory: Root directory to start clearing from
            
        Returns:
            Number of cache entries cleared
        """
        cleared = 0
        
        def clear_recursive(directory: Path):
            nonlocal cleared
            
            try:
                if self.clear_cache(directory):
                    cleared += 1
                
                # Recurse into subdirectories
                for item in directory.iterdir():
                    if item.is_dir():
                        clear_recursive(item)
            
            except OSError:
                # Skip directories we can't access
                pass
        
        clear_recursive(root_directory)
        return cleared