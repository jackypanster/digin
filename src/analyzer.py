"""Core codebase analyzer that orchestrates the analysis process."""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from .config import DigginSettings
from .traverser import DirectoryTraverser
from .ai_client import AIClientFactory, AIClientError
from .cache import CacheManager
from .aggregator import SummaryAggregator


class AnalysisError(Exception):
    """Exception raised during analysis."""
    pass


class CodebaseAnalyzer:
    """Main codebase analyzer that orchestrates the analysis process."""
    
    def __init__(self, settings: DigginSettings):
        """Initialize codebase analyzer.
        
        Args:
            settings: Configuration settings
        """
        self.settings = settings
        self.traverser = DirectoryTraverser(settings)
        self.ai_client = AIClientFactory.create_client(settings)
        self.cache_manager = CacheManager(settings)
        self.aggregator = SummaryAggregator(settings)
        
        # Analysis statistics
        self.stats = {
            "directories_analyzed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "ai_calls": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
            "total_files": 0
        }
    
    def analyze(self, root_path: Path) -> Dict[str, Any]:
        """Analyze a codebase starting from root path.
        
        Args:
            root_path: Root directory to analyze
            
        Returns:
            Analysis result for root directory
        """
        self.stats["start_time"] = time.time()
        
        if self.settings.verbose:
            print(f"Starting analysis of {root_path}")
        
        try:
            # Verify AI client availability
            if not self.ai_client.is_available():
                raise AnalysisError(
                    f"AI provider '{self.settings.api_provider}' CLI not available"
                )
            
            # Get analysis order (bottom-up)
            analysis_order = self.traverser.get_analysis_order(root_path)
            
            if not analysis_order:
                return self._create_empty_result(root_path)
            
            if self.settings.verbose:
                print(f"Will analyze {len(analysis_order)} directories")
            
            # Analyze directories in order
            digests = {}
            for i, directory in enumerate(analysis_order):
                if self.settings.verbose:
                    print(f"[{i+1}/{len(analysis_order)}] Analyzing {directory.name}")
                
                try:
                    digest = self._analyze_directory(directory, root_path, digests)
                    if digest:
                        digests[str(directory)] = digest
                        self.stats["directories_analyzed"] += 1
                        
                except Exception as e:
                    self.stats["errors"] += 1
                    if self.settings.verbose:
                        print(f"Error analyzing {directory}: {e}")
                    # Continue with other directories
                    continue
            
            # Return root directory result
            root_digest = digests.get(str(root_path))
            if not root_digest:
                return self._create_empty_result(root_path)
            
            return root_digest
            
        except KeyboardInterrupt:
            if self.settings.verbose:
                print("Analysis interrupted by user")
            raise
            
        except Exception as e:
            raise AnalysisError(f"Analysis failed: {e}")
            
        finally:
            self.stats["end_time"] = time.time()
    
    def _analyze_directory(self, directory: Path, root_path: Path, 
                          completed_digests: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Analyze a single directory.
        
        Args:
            directory: Directory to analyze
            root_path: Root path of analysis  
            completed_digests: Already completed directory digests
            
        Returns:
            Directory digest or None if analysis failed
        """
        # Check cache first
        if self.settings.cache_enabled:
            cached_digest = self.cache_manager.get_cached_digest(directory)
            if cached_digest:
                self.stats["cache_hits"] += 1
                return cached_digest
        
        self.stats["cache_misses"] += 1
        
        # Collect directory information
        directory_info = self.traverser.collect_directory_info(directory)
        self.stats["total_files"] += directory_info.get("total_files", 0)
        
        # Get child digests for aggregation
        child_digests = self._get_child_digests(directory, completed_digests)
        
        # Determine if this is a leaf directory
        is_leaf = not child_digests
        
        if is_leaf:
            # Leaf directory: analyze with AI
            digest = self._analyze_leaf_directory(directory_info)
        else:
            # Parent directory: aggregate child summaries
            digest = self._analyze_parent_directory(directory, child_digests, directory_info)
        
        # Save to cache if successful
        if digest and self.settings.cache_enabled:
            self.cache_manager.save_digest(directory, digest)
        
        return digest
    
    def _analyze_leaf_directory(self, directory_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze leaf directory using AI.
        
        Args:
            directory_info: Information about the directory
            
        Returns:
            AI analysis digest or None if failed
        """
        try:
            self.stats["ai_calls"] += 1
            digest = self.ai_client.analyze_directory(directory_info)
            
            if not digest:
                if self.settings.verbose:
                    print(f"AI analysis returned no result for {directory_info.get('path')}")
                return None
            
            # Validate digest has required fields
            if not isinstance(digest, dict):
                if self.settings.verbose:
                    print(f"AI analysis returned invalid format for {directory_info.get('path')}")
                return None
            
            # Ensure basic required fields
            if "name" not in digest:
                digest["name"] = directory_info.get("name", "unknown")
            if "path" not in digest:
                digest["path"] = directory_info.get("path", "")
            
            return digest
            
        except AIClientError as e:
            if self.settings.verbose:
                print(f"AI client error: {e}")
            return None
        except Exception as e:
            if self.settings.verbose:
                print(f"Unexpected error in AI analysis: {e}")
            return None
    
    def _analyze_parent_directory(self, directory: Path, child_digests: List[Dict[str, Any]], 
                                 directory_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze parent directory by aggregating children.
        
        Args:
            directory: Parent directory
            child_digests: Child directory digests
            directory_info: Information about direct files in parent
            
        Returns:
            Aggregated digest
        """
        try:
            return self.aggregator.aggregate_summaries(
                directory, child_digests, directory_info
            )
        except Exception as e:
            if self.settings.verbose:
                print(f"Aggregation error for {directory}: {e}")
            return None
    
    def _get_child_digests(self, directory: Path, 
                          completed_digests: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get digests for child directories.
        
        Args:
            directory: Parent directory
            completed_digests: Map of completed digests
            
        Returns:
            List of child directory digests
        """
        child_digests = []
        
        try:
            for item in directory.iterdir():
                if (item.is_dir() and 
                    not self.traverser._should_ignore_directory(item)):
                    
                    child_digest = completed_digests.get(str(item))
                    if child_digest:
                        child_digests.append(child_digest)
        except PermissionError:
            pass
        
        return child_digests
    
    def _create_empty_result(self, root_path: Path) -> Dict[str, Any]:
        """Create empty result for failed analysis.
        
        Args:
            root_path: Root directory
            
        Returns:
            Empty analysis result
        """
        return {
            "name": root_path.name,
            "path": str(root_path),
            "kind": "unknown",
            "summary": "Analysis failed or no analyzable content found",
            "confidence": 0,
            "analyzed_at": time.time(),
            "analyzer_version": "unknown"
        }
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """Get analysis statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = self.stats.copy()
        
        # Calculate derived stats
        if stats["start_time"] and stats["end_time"]:
            stats["duration_seconds"] = stats["end_time"] - stats["start_time"]
        else:
            stats["duration_seconds"] = 0
            
        stats["cache_hit_rate"] = (
            stats["cache_hits"] / max(stats["cache_hits"] + stats["cache_misses"], 1) * 100
        )
        
        return stats
    
    def get_traverser(self) -> DirectoryTraverser:
        """Get the directory traverser instance.
        
        Returns:
            DirectoryTraverser instance
        """
        return self.traverser
    
    def clear_cache(self, root_path: Path) -> None:
        """Clear cache for the given path.
        
        Args:
            root_path: Root path to clear cache for
        """
        self.cache_manager.clear_cache(root_path, recursive=True)
        if self.settings.verbose:
            print(f"Cleared cache for {root_path}")
    
    def dry_run(self, root_path: Path) -> Dict[str, Any]:
        """Perform dry run to show what would be analyzed.
        
        Args:
            root_path: Root directory to analyze
            
        Returns:
            Dry run information
        """
        analysis_order = self.traverser.get_analysis_order(root_path)
        
        # Count leaf vs parent directories
        leaf_count = len(self.traverser.find_leaf_directories(root_path))
        parent_count = len(analysis_order) - leaf_count
        
        # Estimate file counts
        total_files = 0
        for directory in analysis_order[:10]:  # Sample first 10
            dir_info = self.traverser.collect_directory_info(directory)
            total_files += dir_info.get("total_files", 0)
        
        # Extrapolate if we have more directories
        if len(analysis_order) > 10:
            avg_files_per_dir = total_files / 10
            total_files = int(avg_files_per_dir * len(analysis_order))
        
        return {
            "total_directories": len(analysis_order),
            "leaf_directories": leaf_count,
            "parent_directories": parent_count,
            "estimated_files": total_files,
            "ai_provider": self.settings.api_provider,
            "cache_enabled": self.settings.cache_enabled,
            "analysis_order": [str(d) for d in analysis_order]
        }