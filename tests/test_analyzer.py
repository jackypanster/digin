"""Tests for the main codebase analyzer."""

from unittest.mock import Mock, patch

import pytest

from src.analyzer import AnalysisError, CodebaseAnalyzer
from src.config import DigginSettings


class TestCodebaseAnalyzer:
    """Test CodebaseAnalyzer functionality."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return DigginSettings(api_provider="claude", cache_enabled=True, verbose=False)

    @pytest.fixture
    def analyzer(self, settings):
        """Create CodebaseAnalyzer with mocked dependencies."""
        with patch("src.analyzer.AIClientFactory.create_client") as mock_factory:
            mock_client = Mock()
            mock_client.is_available.return_value = True
            mock_factory.return_value = mock_client

            analyzer = CodebaseAnalyzer(settings)
            analyzer.ai_client = mock_client
            return analyzer

    def test_init(self, settings):
        """Test analyzer initialization."""
        with patch("src.analyzer.AIClientFactory.create_client"):
            analyzer = CodebaseAnalyzer(settings)

            assert analyzer.settings == settings
            assert "directories_analyzed" in analyzer.stats
            assert "cache_hits" in analyzer.stats
            assert analyzer.stats["directories_analyzed"] == 0

    def test_analyze_ai_unavailable(self, analyzer, tmp_path):
        """Test analysis when AI client is unavailable."""
        analyzer.ai_client.is_available.return_value = False

        with pytest.raises(AnalysisError, match="AI provider.*not available"):
            analyzer.analyze(tmp_path)

    def test_analyze_empty_directory(self, analyzer, tmp_path):
        """Test analysis of empty directory."""
        # Mock empty analysis order
        analyzer.traverser.get_analysis_order = Mock(return_value=[])

        result = analyzer.analyze(tmp_path)

        # Should return empty result
        assert result["name"] == tmp_path.name
        assert result["confidence"] == 0
        assert "Analysis failed" in result["summary"]

    def test_analyze_single_directory(self, analyzer, tmp_path):
        """Test analysis of single directory."""
        # Setup mocks
        analyzer.traverser.get_analysis_order = Mock(return_value=[tmp_path])

        directory_info = {
            "name": tmp_path.name,
            "path": str(tmp_path),
            "files": [{"name": "test.py", "size": 100}],
            "total_files": 1,
        }
        analyzer.traverser.collect_directory_info = Mock(return_value=directory_info)

        digest_result = {
            "name": tmp_path.name,
            "kind": "lib",
            "summary": "Test library",
        }
        analyzer.ai_client.analyze_directory = Mock(return_value=digest_result)

        # Mock cache miss
        analyzer.cache_manager.get_cached_digest = Mock(return_value=None)

        result = analyzer.analyze(tmp_path)

        assert result["name"] == tmp_path.name
        assert result["kind"] == "lib"
        assert result["summary"] == "Test library"
        assert analyzer.stats["directories_analyzed"] == 1
        assert analyzer.stats["cache_misses"] == 1
        assert analyzer.stats["ai_calls"] == 1

    def test_analyze_with_cache_hit(self, analyzer, tmp_path):
        """Test analysis with cache hit."""
        analyzer.traverser.get_analysis_order = Mock(return_value=[tmp_path])

        cached_digest = {
            "name": tmp_path.name,
            "kind": "service",
            "summary": "Cached service",
        }
        analyzer.cache_manager.get_cached_digest = Mock(return_value=cached_digest)

        result = analyzer.analyze(tmp_path)

        assert result["summary"] == "Cached service"
        assert analyzer.stats["cache_hits"] == 1
        assert analyzer.stats["ai_calls"] == 0  # No AI call needed

    def test_analyze_nested_directories(self, analyzer, tmp_path):
        """Test analysis of nested directories."""
        # Create structure: root -> app -> services (leaf)
        app_dir = tmp_path / "app"
        services_dir = app_dir / "services"

        analysis_order = [services_dir, app_dir, tmp_path]
        analyzer.traverser.get_analysis_order = Mock(return_value=analysis_order)

        # Mock directory info
        def mock_collect_info(directory):
            return {
                "name": directory.name,
                "path": str(directory),
                "files": [],
                "total_files": 0,
            }

        analyzer.traverser.collect_directory_info = Mock(side_effect=mock_collect_info)

        # Mock AI analysis for leaf directory
        leaf_digest = {
            "name": "services",
            "kind": "service",
            "summary": "Services module",
        }
        analyzer.ai_client.analyze_directory = Mock(return_value=leaf_digest)

        # Mock aggregation for parent directories
        def mock_aggregate(directory, child_digests, directory_info):
            return {
                "name": directory.name,
                "kind": "infra",
                "summary": (
                    f"Aggregated {directory.name} "
                    f"with {len(child_digests)} children"
                ),
            }

        analyzer.aggregator.aggregate_summaries = Mock(side_effect=mock_aggregate)

        # No cache hits
        analyzer.cache_manager.get_cached_digest = Mock(return_value=None)

        # Mock _get_child_digests to return proper child relationships
        def mock_get_children(directory, completed_digests):
            if directory == tmp_path:
                # Root has app as child
                app_key = str(app_dir)
                return (
                    [completed_digests[app_key]] if app_key in completed_digests else []
                )
            elif directory == app_dir:
                # App has services as child
                services_key = str(services_dir)
                return (
                    [completed_digests[services_key]]
                    if services_key in completed_digests
                    else []
                )
            else:
                # Leaf directory has no children
                return []

        analyzer._get_child_digests = Mock(side_effect=mock_get_children)

        result = analyzer.analyze(tmp_path)

        # Should analyze leaf with AI, aggregate parents
        assert analyzer.ai_client.analyze_directory.call_count == 1
        assert analyzer.aggregator.aggregate_summaries.call_count == 2
        assert (
            "Aggregated" in result["summary"] and "with 1 children" in result["summary"]
        )
        assert analyzer.stats["directories_analyzed"] == 3

    def test_analyze_with_errors(self, analyzer, tmp_path):
        """Test analysis continues despite errors."""
        leaf_dir = tmp_path / "leaf"
        analysis_order = [leaf_dir, tmp_path]

        analyzer.traverser.get_analysis_order = Mock(return_value=analysis_order)
        analyzer.cache_manager.get_cached_digest = Mock(return_value=None)

        # Mock directory info - error for leaf, success for root
        def mock_collect_info(directory):
            if directory == leaf_dir:
                raise Exception("Permission denied")
            return {
                "name": directory.name,
                "path": str(directory),
                "files": [{"name": "test.py"}],
                "total_files": 1,
            }

        analyzer.traverser.collect_directory_info = Mock(side_effect=mock_collect_info)

        # Mock AI analysis for successful root (since it has files, it's a leaf)
        analyzer.ai_client.analyze_directory = Mock(
            return_value={"name": tmp_path.name, "summary": "Root directory"}
        )

        # Mock empty children due to error
        analyzer._get_child_digests = Mock(return_value=[])

        result = analyzer.analyze(tmp_path)

        # Should complete despite error in leaf directory
        assert analyzer.stats["errors"] == 1
        assert analyzer.stats["directories_analyzed"] == 1  # Only root succeeded
        assert result["summary"] == "Root directory"

    def test_analyze_keyboard_interrupt(self, analyzer, tmp_path):
        """Test analysis handles keyboard interrupt."""
        analyzer.traverser.get_analysis_order = Mock(return_value=[tmp_path])
        analyzer.cache_manager.get_cached_digest = Mock(return_value=None)
        analyzer.traverser.collect_directory_info = Mock(
            side_effect=KeyboardInterrupt()
        )

        with pytest.raises(KeyboardInterrupt):
            analyzer.analyze(tmp_path)

    def test_dry_run(self, analyzer, tmp_path):
        """Test dry run functionality."""
        leaf_dirs = [tmp_path / "lib", tmp_path / "app"]
        all_dirs = leaf_dirs + [tmp_path]

        analyzer.traverser.find_leaf_directories = Mock(return_value=leaf_dirs)
        analyzer.traverser.get_analysis_order = Mock(return_value=all_dirs)

        # Mock directory info for file count estimation
        def mock_collect_info(directory):
            return {"total_files": 5}

        analyzer.traverser.collect_directory_info = Mock(side_effect=mock_collect_info)

        result = analyzer.dry_run(tmp_path)

        assert result["total_directories"] == 3
        assert result["leaf_directories"] == 2
        assert result["parent_directories"] == 1
        assert result["estimated_files"] == 15  # 3 dirs * 5 files
        assert result["ai_provider"] == "claude"
        assert result["cache_enabled"] is True

    def test_get_analysis_stats(self, analyzer):
        """Test getting analysis statistics."""
        # Set some stats
        analyzer.stats.update(
            {"start_time": 100.0, "end_time": 105.5, "cache_hits": 3, "cache_misses": 2}
        )

        stats = analyzer.get_analysis_stats()

        assert stats["duration_seconds"] == 5.5
        assert stats["cache_hit_rate"] == 60.0  # 3/(3+2) * 100

    def test_clear_cache(self, analyzer, tmp_path):
        """Test cache clearing."""
        analyzer.cache_manager.clear_cache = Mock()

        analyzer.clear_cache(tmp_path)

        analyzer.cache_manager.clear_cache.assert_called_once_with(
            tmp_path, recursive=True
        )

    def test_get_traverser(self, analyzer):
        """Test getting traverser instance."""
        traverser = analyzer.get_traverser()

        assert traverser is analyzer.traverser

    def test_analyze_leaf_directory_success(self, analyzer):
        """Test successful leaf directory analysis."""
        directory_info = {"name": "test", "path": "/test", "files": []}

        expected_digest = {"name": "test", "kind": "lib"}
        analyzer.ai_client.analyze_directory = Mock(return_value=expected_digest)

        result = analyzer._analyze_leaf_directory(directory_info)

        assert result["name"] == "test"
        assert result["kind"] == "lib"

    def test_analyze_leaf_directory_failure(self, analyzer):
        """Test failed leaf directory analysis."""
        directory_info = {"name": "test", "path": "/test", "files": []}

        from src.ai_client import AIClientError

        analyzer.ai_client.analyze_directory = Mock(
            side_effect=AIClientError("API error")
        )

        result = analyzer._analyze_leaf_directory(directory_info)

        assert result is None
        assert analyzer.stats["ai_calls"] == 1

    def test_analyze_leaf_directory_invalid_response(self, analyzer):
        """Test leaf directory analysis with invalid AI response."""
        directory_info = {"name": "test", "path": "/test", "files": []}

        # AI returns non-dict response
        analyzer.ai_client.analyze_directory = Mock(return_value="invalid response")

        result = analyzer._analyze_leaf_directory(directory_info)

        assert result is None

    def test_analyze_parent_directory(self, analyzer, tmp_path):
        """Test parent directory analysis."""
        child_digests = [
            {"name": "child1", "kind": "service"},
            {"name": "child2", "kind": "lib"},
        ]
        directory_info = {"name": "parent", "files": []}

        expected_aggregate = {
            "name": "parent",
            "kind": "infra",
            "summary": "Parent with 2 children",
        }
        analyzer.aggregator.aggregate_summaries = Mock(return_value=expected_aggregate)

        result = analyzer._analyze_parent_directory(
            tmp_path, child_digests, directory_info
        )

        assert result["summary"] == "Parent with 2 children"
        analyzer.aggregator.aggregate_summaries.assert_called_once_with(
            tmp_path, child_digests, directory_info
        )
