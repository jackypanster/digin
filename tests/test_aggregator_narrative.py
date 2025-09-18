"""測試 SummaryAggregator 的敘述字段生成功能。"""

import pytest
from pathlib import Path
from unittest.mock import Mock

from src.aggregator import SummaryAggregator
from src.config import DigginSettings


class TestAggregatorNarrative:
    """測試 SummaryAggregator 的敘述功能。"""

    def setup_method(self):
        """設置測試環境。"""
        self.settings = DigginSettings()
        self.settings.narrative_enabled = True
        self.aggregator = SummaryAggregator(self.settings)

    def test_narrative_enabled_adds_narrative_fields(self):
        """測試啟用敘述模式時會添加敘述字段。"""
        directory = Path("/test/project")
        child_digests = [
            {
                "name": "auth",
                "kind": "service",
                "summary": "認證服務",
                "capabilities": ["用戶登入", "權限檢查"],
                "confidence": 85,
            }
        ]

        result = self.aggregator.aggregate_summaries(directory, child_digests)

        assert "narrative" in result
        assert "summary" in result["narrative"]
        assert "handshake" in result["narrative"]
        assert "next_steps" in result["narrative"]

    def test_narrative_disabled_no_narrative_fields(self):
        """測試禁用敘述模式時不添加敘述字段。"""
        self.settings.narrative_enabled = False
        aggregator = SummaryAggregator(self.settings)

        directory = Path("/test/project")
        child_digests = [
            {
                "name": "auth",
                "kind": "service",
                "summary": "認證服務",
                "capabilities": ["用戶登入"],
                "confidence": 85,
            }
        ]

        result = aggregator.aggregate_summaries(directory, child_digests)

        assert "narrative" not in result

    def test_conversational_summary_generation(self):
        """測試對話式摘要生成。"""
        directory = Path("/test/services")
        child_digests = [
            {
                "name": "user-service",
                "kind": "service",
                "summary": "用戶管理服務",
                "capabilities": ["用戶註冊", "用戶查詢"],
                "confidence": 90,
                "narrative": {"summary": "負責管理所有用戶相關操作"},
            },
            {
                "name": "auth-service",
                "kind": "service",
                "summary": "認證服務",
                "capabilities": ["登入認證", "權限檢查"],
                "confidence": 85,
                "narrative": {"summary": "確保系統安全認證"},
            },
        ]

        narrative = self.aggregator._generate_narrative_fields(
            directory, child_digests, None
        )

        summary = narrative["summary"]
        assert "services" in summary
        assert "2個模組" in summary  # Fixed: now shows module count correctly
        assert isinstance(summary, str)
        assert len(summary) > 10  # 確保生成了有意義的內容

    def test_handshake_generation_with_different_kinds(self):
        """測試不同類型的握手語生成。"""
        directory = Path("/test/libs")
        child_digests = [
            {
                "name": "utils",
                "kind": "lib",
                "capabilities": ["工具函數", "幫助方法"],
                "confidence": 80,
            }
        ]

        narrative = self.aggregator._generate_narrative_fields(
            directory, child_digests, None
        )

        handshake = narrative["handshake"]
        assert "👋" in handshake
        assert "工具庫和通用組件區" in handshake
        assert "1 個模組" in handshake

    def test_next_steps_with_multiple_children(self):
        """測試多個子模組的下一步建議。"""
        directory = Path("/test/complex")
        child_digests = [
            {
                "name": "high-importance",
                "kind": "service",
                "capabilities": ["核心功能", "主要邏輯", "關鍵服務"],
                "confidence": 95,
            },
            {
                "name": "medium-importance",
                "kind": "lib",
                "capabilities": ["輔助功能"],
                "confidence": 70,
            },
            {
                "name": "low-importance",
                "kind": "test",
                "capabilities": [],
                "confidence": 60,
            },
        ]

        narrative = self.aggregator._generate_narrative_fields(
            directory, child_digests, None
        )

        next_steps = narrative["next_steps"]
        assert "high-importance" in next_steps
        assert "medium-importance" in next_steps
        assert isinstance(next_steps, str)

    def test_domain_description_detection(self):
        """測試領域描述檢測。"""
        # Web 服務檢測
        child_digests = [
            {
                "name": "api",
                "capabilities": ["HTTP API", "Web server", "REST service"],
                "confidence": 80,
            }
        ]

        domain = self.aggregator._get_domain_description(child_digests)
        assert domain == "Web服務"

        # 數據處理檢測
        child_digests = [
            {
                "name": "data",
                "capabilities": ["database operations", "data storage"],
                "confidence": 80,
            }
        ]

        domain = self.aggregator._get_domain_description(child_digests)
        assert domain == "數據處理"

    def test_empty_child_digests(self):
        """測試空子摘要的處理。"""
        directory = Path("/test/empty")
        child_digests = []

        narrative = self.aggregator._generate_narrative_fields(
            directory, child_digests, None
        )

        assert "empty" in narrative["summary"]
        assert "歡迎查看" in narrative["handshake"]
        assert "直接文件" in narrative["next_steps"]

    def test_capability_summary_generation(self):
        """測試能力摘要生成。"""
        child_digests = [
            {"capabilities": ["功能A"], "confidence": 80},
            {"capabilities": ["功能B", "功能C"], "confidence": 90},
        ]

        summary = self.aggregator._get_top_capability_summary(child_digests)
        assert isinstance(summary, str)
        assert len(summary) > 0

        # 測試空能力
        empty_digests = [{"capabilities": [], "confidence": 80}]
        summary = self.aggregator._get_top_capability_summary(empty_digests)
        assert summary == "提供多種功能"

    def test_narrative_fields_are_cleaned(self):
        """測試敘述字段會被正確清理。"""
        directory = Path("/test/clean")
        child_digests = [
            {
                "name": "test",
                "kind": "service",
                "capabilities": ["test"],
                "confidence": 80,
            }
        ]

        result = self.aggregator.aggregate_summaries(directory, child_digests)

        # 確保敘述字段存在且不為空
        assert "narrative" in result
        narrative = result["narrative"]
        assert narrative["summary"]
        assert narrative["handshake"]
        assert narrative["next_steps"]

        # 確保沒有空字段被保留
        for field in ["summary", "handshake", "next_steps"]:
            assert narrative[field] is not None
            assert narrative[field] != ""

    def test_narrative_with_existing_child_narratives(self):
        """測試使用現有子敘述的聚合。"""
        directory = Path("/test/parent")
        child_digests = [
            {
                "name": "child1",
                "kind": "service",
                "capabilities": ["功能1"],
                "confidence": 80,
                "narrative": {
                    "summary": "這是子模組1的敘述",
                    "handshake": "歡迎來到子模組1",
                },
            },
            {
                "name": "child2",
                "kind": "lib",
                "capabilities": ["功能2"],
                "confidence": 85,
                "narrative": {
                    "summary": "這是子模組2的敘述",
                    "handshake": "歡迎來到子模組2",
                },
            },
        ]

        narrative = self.aggregator._generate_narrative_fields(
            directory, child_digests, None
        )

        summary = narrative["summary"]
        # 應該包含子敘述的內容
        assert "2 個功能模組" in summary
        assert "parent" in summary


if __name__ == "__main__":
    pytest.main([__file__])