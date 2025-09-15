"""總控分析器（Orchestrator）。

核心流程：
1) 用 DirectoryTraverser 生成「葉 → 父 → 根」的分析序列。
2) 目錄級緩存命中即返回；未命中則：
   - 葉子：AIClient 生成 digest.json；
   - 父級：SummaryAggregator 聚合子摘要 + 本目錄直屬文件信息。
3) 記錄統計（AI 調用、緩存命中/未命中、文件數、錯誤與耗時），並提供 dry_run 粗估。

邊界與策略：不中斷失敗目錄，繼續分析；不執行用戶代碼，只基於文件/結構推理，降低風險與成本。
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .aggregator import SummaryAggregator
from .ai_client import analyze_directory_with_ai, is_cli_available
from .cache import CacheManager
from .config import DigginSettings
from .logger import get_logger
from .traverser import DirectoryTraverser


# Removed AnalysisError - now using standard exceptions for fail-fast behavior


class CodebaseAnalyzer:
    """Main codebase analyzer that orchestrates the analysis process."""

    def __init__(self, settings: DigginSettings):
        """Initialize codebase analyzer.

        Args:
            settings: Configuration settings
        """
        self.settings = settings
        self.traverser = DirectoryTraverser(settings)
        self.cache_manager = CacheManager(settings)
        self.aggregator = SummaryAggregator(settings)
        self.logger = get_logger("analyzer")

        # Analysis statistics
        self.stats = {
            "directories_analyzed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "ai_calls": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
            "total_files": 0,
        }

    def analyze(self, root_path: Path) -> Dict[str, Any]:
        """Analyze a codebase starting from root path.

        Args:
            root_path: Root directory to analyze

        Returns:
            Analysis result for root directory
        """
        self.stats["start_time"] = time.time()
        self.logger.info(f"Starting analysis of codebase: {root_path}")

        if self.settings.verbose:
            print(f"Starting analysis of {root_path}")

        # Verify AI client availability
        if not is_cli_available(self.settings.api_provider):
            raise RuntimeError(
                f"AI provider '{self.settings.api_provider}' CLI not available"
            )

        try:
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
                    error_msg = f"Error analyzing {directory}: {e}"
                    self.logger.error(error_msg)
                    if self.settings.verbose:
                        print(error_msg)
                    # Continue with other directories
                    continue

            # Return root directory result
            root_digest = digests.get(str(root_path))
            if not root_digest:
                return self._create_empty_result(root_path)

            return root_digest

        except KeyboardInterrupt:
            interrupt_msg = "Analysis interrupted by user"
            self.logger.warning(interrupt_msg)
            if self.settings.verbose:
                print(interrupt_msg)
            raise

        except Exception as e:
            error_msg = f"Analysis failed: {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        finally:
            self.stats["end_time"] = time.time()
            duration = self.stats["end_time"] - self.stats["start_time"]
            self.logger.info(
                f"Analysis completed. Duration: {duration:.2f}s, "
                f"Directories: {self.stats['directories_analyzed']}, "
                f"AI calls: {self.stats['ai_calls']}, "
                f"Cache hits: {self.stats['cache_hits']}, "
                f"Errors: {self.stats['errors']}"
            )

    def _analyze_directory(
        self,
        directory: Path,
        root_path: Path,
        completed_digests: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Analyze a single directory."""
        cached = self._check_cache(directory)
        if cached:
            self.logger.debug(f"Cache hit for directory: {directory}")
            return cached

        self.logger.debug(f"Cache miss for directory: {directory}")

        directory_info = self.traverser.collect_directory_info(directory)
        self.stats["total_files"] += directory_info.get("total_files", 0)

        child_digests = self._get_child_digests(directory, completed_digests)

        if not child_digests:
            digest = self._analyze_leaf_directory(directory_info)
        else:
            digest = self._analyze_parent_directory(
                directory, child_digests, directory_info
            )

        self._save_to_cache(directory, digest)
        return digest

    def _check_cache(self, directory: Path) -> Optional[Dict[str, Any]]:
        """Check cache for existing digest."""
        if not self.settings.cache_enabled:
            self.stats["cache_misses"] += 1
            return None

        cached_digest = self.cache_manager.get_cached_digest(directory)
        if cached_digest:
            self.stats["cache_hits"] += 1
            return cached_digest

        self.stats["cache_misses"] += 1
        return None

    def _save_to_cache(self, directory: Path, digest: Optional[Dict[str, Any]]) -> None:
        """Save digest to cache if enabled and digest exists."""
        if digest and self.settings.cache_enabled:
            self.cache_manager.save_digest(directory, digest)

    def _analyze_leaf_directory(
        self, directory_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze leaf directory using AI."""
        self.stats["ai_calls"] += 1

        digest = analyze_directory_with_ai(
            self.settings.api_provider,
            directory_info,
            children_digests=None,
            settings=self.settings
        )

        self._ensure_required_fields(digest, directory_info)
        return digest

    def _ensure_required_fields(
        self, digest: Dict[str, Any], directory_info: Dict[str, Any]
    ) -> None:
        """Ensure digest has required fields."""
        if "name" not in digest:
            digest["name"] = directory_info.get("name", "unknown")
        if "path" not in digest:
            digest["path"] = directory_info.get("path", "")

    def _analyze_parent_directory(
        self,
        directory: Path,
        child_digests: List[Dict[str, Any]],
        directory_info: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Analyze parent directory by aggregating children."""
        return self.aggregator.aggregate_summaries(
            directory, child_digests, directory_info
        )

    def _get_child_digests(
        self, directory: Path, completed_digests: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get digests for child directories."""
        child_digests = []

        try:
            for item in directory.iterdir():
                if not item.is_dir():
                    continue
                if self.traverser.should_ignore_directory(item):
                    continue

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
            "analyzer_version": "unknown",
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
            stats["cache_hits"]
            / max(stats["cache_hits"] + stats["cache_misses"], 1)
            * 100
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
            "analysis_order": [str(d) for d in analysis_order],
        }
