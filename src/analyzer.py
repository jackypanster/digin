"""
Core codebase analyzer
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import time
from datetime import datetime

from .config import DigginSettings
from .traverser import DirectoryTraverser
from .ai_client import AIClient
from .cache import CacheManager
from .aggregator import SummaryAggregator
from .__version__ import __version__


class CodebaseAnalyzer:
    """Main codebase analyzer that orchestrates the analysis process"""
    
    def __init__(self, settings: DigginSettings):
        self.settings = settings
        self.traverser = DirectoryTraverser(settings)
        self.ai_client = AIClient(settings)
        self.cache_manager = CacheManager(settings)
        self.aggregator = SummaryAggregator(settings)
        
        # Statistics
        self.stats = {
            "directories_analyzed": 0,
            "files_processed": 0,
            "cache_hits": 0,
            "api_calls": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }
    
    def analyze(self, root_path: Path) -> Dict[str, Any]:
        """
        Analyze a codebase starting from the root path
        
        Args:
            root_path: Root directory to analyze
            
        Returns:
            Dictionary containing the analysis results
        """
        self.stats["start_time"] = time.time()
        
        try:
            # Get analysis order (leaf nodes first, then parents)
            analysis_order = self.traverser.get_analysis_order(root_path)
            
            if not analysis_order:
                return self._create_empty_result(root_path, "No directories to analyze")
            
            # Analyze each directory in order
            results = {}
            for directory in analysis_order:
                try:
                    digest = self._analyze_directory(directory, root_path)
                    if digest:
                        results[str(directory)] = digest
                        self.stats["directories_analyzed"] += 1
                except Exception as e:
                    self.stats["errors"] += 1
                    if self.settings.verbose:
                        print(f"Error analyzing {directory}: {e}")
            
            # Return the root directory result
            root_result = results.get(str(root_path))
            if not root_result:
                return self._create_empty_result(root_path, "Analysis failed")
            
            return root_result
            
        finally:
            self.stats["end_time"] = time.time()
    
    def _analyze_directory(self, directory: Path, root_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze a single directory"""
        
        # Check cache first
        if self.settings.cache_enabled:
            cached_result = self.cache_manager.get_cached_digest(directory)
            if cached_result:
                self.stats["cache_hits"] += 1
                return cached_result
        
        # Collect directory information
        directory_info = self.traverser.collect_directory_info(directory)
        
        if not directory_info["files"] and not directory_info["subdirs"]:
            # Empty directory, skip
            return None
        
        # Update file count
        self.stats["files_processed"] += len(directory_info["files"])
        
        # Get child digests for aggregation
        child_digests = self._get_child_digests(directory, directory_info["subdirs"])
        
        # If this is a leaf directory, analyze with AI
        if not child_digests:  # Leaf directory
            digest = self._analyze_leaf_directory(directory, root_path, directory_info)
        else:  # Parent directory - aggregate children
            digest = self.aggregator.aggregate_directory(
                directory, root_path, directory_info, child_digests
            )
        
        # Cache the result
        if digest and self.settings.cache_enabled:
            self.cache_manager.save_digest(directory, digest)
        
        return digest
    
    def _analyze_leaf_directory(
        self, 
        directory: Path, 
        root_path: Path, 
        directory_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Analyze a leaf directory using AI"""
        
        try:
            # Call AI for analysis
            ai_result = self.ai_client.analyze_directory(directory, directory_info)
            self.stats["api_calls"] += 1
            
            if not ai_result:
                return None
            
            # Add metadata
            ai_result.update({
                "analyzed_at": datetime.utcnow().isoformat() + "Z",
                "analyzer_version": f"digin-{__version__}",
                "path": str(directory.relative_to(root_path)) if directory != root_path else ".",
            })
            
            return ai_result
            
        except Exception as e:
            self.stats["errors"] += 1
            if self.settings.verbose:
                print(f"AI analysis failed for {directory}: {e}")
            return None
    
    def _get_child_digests(self, parent_dir: Path, subdirs: List[Path]) -> List[Dict[str, Any]]:
        """Get digests from child directories"""
        child_digests = []
        
        for subdir in subdirs:
            digest_file = subdir / "digest.json"
            if digest_file.exists():
                try:
                    with open(digest_file, 'r', encoding='utf-8') as f:
                        digest = json.load(f)
                        child_digests.append(digest)
                except (json.JSONDecodeError, IOError):
                    continue
        
        return child_digests
    
    def _create_empty_result(self, path: Path, reason: str) -> Dict[str, Any]:
        """Create an empty result for failed analysis"""
        return {
            "name": path.name,
            "path": ".",
            "kind": "unknown",
            "summary": reason,
            "confidence": 0,
            "analyzed_at": datetime.utcnow().isoformat() + "Z",
            "analyzer_version": f"digin-{__version__}",
            "evidence": {"files": []},
        }
    
    def get_traverser(self) -> DirectoryTraverser:
        """Get the directory traverser (for dry-run mode)"""
        return self.traverser
    
    def get_stats(self) -> Dict[str, Any]:
        """Get analysis statistics"""
        stats = self.stats.copy()
        if stats["start_time"] and stats["end_time"]:
            stats["duration"] = stats["end_time"] - stats["start_time"]
        return stats