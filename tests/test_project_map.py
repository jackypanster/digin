"""測試項目地圖構建功能。"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from src.project_map import (
    ProjectMapBuilder,
    TreeNode,
    OnboardingPath,
    ProjectMap,
    validate_project_map,
)
from src.config import DigginSettings


class TestProjectMapBuilder:
    """測試項目地圖構建器。"""

    def setup_method(self):
        """設置測試環境。"""
        self.settings = DigginSettings()
        self.builder = ProjectMapBuilder(self.settings)

    def test_collect_digest_files(self):
        """測試 digest 文件收集。"""
        # 模擬目錄結構
        root_path = Path("/test/project")

        # 模擬 digest 文件內容
        digest_data = {
            "name": "test",
            "kind": "service",
            "summary": "測試服務",
            "capabilities": ["功能1"],
            "confidence": 80,
        }

        with patch.object(Path, "rglob") as mock_rglob, patch(
            "builtins.open", mock_open(read_data=json.dumps(digest_data))
        ):
            # 模擬找到的 digest 文件
            mock_digest_files = [
                root_path / "digest.json",
                root_path / "subdir" / "digest.json",
            ]
            mock_rglob.return_value = mock_digest_files

            # 模擬文件路徑操作
            with patch.object(Path, "parent") as mock_parent, patch.object(
                Path, "relative_to"
            ) as mock_relative:
                mock_parent.side_effect = [root_path, root_path / "subdir"]
                mock_relative.side_effect = [Path("."), Path("subdir")]

                digest_files = self.builder._collect_digest_files(root_path)

                assert len(digest_files) == 2
                assert "" in digest_files  # 根目錄
                assert "subdir" in digest_files

    def test_build_tree_structure(self):
        """測試樹結構構建。"""
        root_path = Path("/test/project")
        digest_files = {
            "": {
                "name": "project",
                "kind": "infra",
                "summary": "項目根目錄",
                "capabilities": [],
                "confidence": 70,
            },
            "src": {
                "name": "src",
                "kind": "lib",
                "summary": "源代碼目錄",
                "capabilities": ["核心功能"],
                "confidence": 85,
            },
            "src/auth": {
                "name": "auth",
                "kind": "service",
                "summary": "認證服務",
                "capabilities": ["用戶認證", "權限管理"],
                "confidence": 90,
            },
        }

        tree = self.builder._build_tree_structure(root_path, digest_files)

        # 檢查根節點
        assert tree.name == "project"
        assert tree.kind == "infra"
        assert len(tree.children) == 1

        # 檢查 src 節點
        src_node = tree.children[0]
        assert src_node.name == "src"
        assert src_node.kind == "lib"
        assert len(src_node.children) == 1

        # 檢查 auth 節點
        auth_node = src_node.children[0]
        assert auth_node.name == "auth"
        assert auth_node.kind == "service"
        assert len(auth_node.children) == 0

    def test_calculate_importance_scores(self):
        """測試重要性評分計算。"""
        # 創建測試樹
        tree = TreeNode(
            name="root",
            path="",
            kind="infra",
            summary="根目錄",
            confidence=70,
            capabilities=["功能1", "功能2"],
        )

        child1 = TreeNode(
            name="service",
            path="service",
            kind="service",
            summary="服務",
            confidence=90,
            capabilities=["核心服務", "API", "業務邏輯"],
        )

        child2 = TreeNode(
            name="lib",
            path="lib",
            kind="lib",
            summary="庫",
            confidence=80,
            capabilities=["工具函數"],
        )

        tree.children = [child1, child2]

        self.builder._calculate_importance_scores(tree)

        # 服務類型的評分應該更高
        assert child1.importance_score > child2.importance_score
        assert tree.importance_score > 0

        # 檢查特殊關鍵詞加成
        main_node = TreeNode(
            name="main",
            path="main",
            kind="service",
            summary="主服務",
            confidence=80,
            capabilities=["核心"],
        )
        tree.children.append(main_node)

        self.builder._calculate_importance_scores(tree)
        # main 節點應該獲得額外加成
        assert main_node.importance_score > child2.importance_score

    def test_generate_onboarding_path(self):
        """測試引導路徑生成。"""
        # 創建測試樹
        tree = TreeNode(name="root", path="", kind="infra", summary="根目錄")

        # 添加不同重要性的子節點
        high_importance = TreeNode(
            name="core",
            path="core",
            kind="service",
            summary="核心服務",
            confidence=95,
            capabilities=["主要功能", "核心邏輯", "關鍵組件"],
        )
        high_importance.importance_score = 20

        medium_importance = TreeNode(
            name="utils",
            path="utils",
            kind="lib",
            summary="工具庫",
            confidence=80,
            capabilities=["輔助功能"],
        )
        medium_importance.importance_score = 10

        low_importance = TreeNode(
            name="tests",
            path="tests",
            kind="test",
            summary="測試",
            confidence=70,
            capabilities=["單元測試"],
        )
        low_importance.importance_score = 5

        tree.children = [high_importance, medium_importance, low_importance]

        onboarding_path = self.builder._generate_onboarding_path(tree)

        # 檢查引導路徑
        assert isinstance(onboarding_path, OnboardingPath)
        assert onboarding_path.total_steps > 0
        assert len(onboarding_path.steps) > 0

        # 高重要性節點應該在引導路徑中
        assert high_importance.is_onboarding_path
        assert any(step["path"] == "core" for step in onboarding_path.steps)

        # 檢查步驟內容
        first_step = onboarding_path.steps[0]
        assert "step" in first_step
        assert "title" in first_step
        assert "path" in first_step
        assert "description" in first_step

    def test_select_recommended_reading(self):
        """測試推薦閱讀選擇。"""
        tree = TreeNode(name="root", path="", kind="infra", summary="根目錄")

        # 高置信度、豐富功能的節點
        good_node = TreeNode(
            name="good",
            path="good",
            kind="service",
            summary="優質模組",
            confidence=85,
            capabilities=["功能1", "功能2", "功能3"],
        )
        good_node.importance_score = 15

        # 低置信度節點
        poor_node = TreeNode(
            name="poor",
            path="poor",
            kind="unknown",
            summary="未知模組",
            confidence=40,
            capabilities=["功能1"],
        )
        poor_node.importance_score = 5

        tree.children = [good_node, poor_node]

        reading_list = self.builder._select_recommended_reading(tree)

        # 優質節點應該被推薦
        assert good_node.is_recommended_reading
        assert not poor_node.is_recommended_reading

        # 檢查推薦項目內容
        if reading_list:
            item = reading_list[0]
            assert "title" in item
            assert "path" in item
            assert "reason" in item

    def test_build_project_map_empty_directory(self):
        """測試空目錄的項目地圖構建。"""
        root_path = Path("/test/empty")

        with patch.object(self.builder, "_collect_digest_files", return_value={}):
            project_map = self.builder.build_project_map(root_path)

            assert isinstance(project_map, ProjectMap)
            assert project_map.project_name == "empty"
            assert project_map.tree.name == "empty"
            assert len(project_map.tree.children) == 0
            assert project_map.onboarding_path.total_steps == 0

    def test_estimate_reading_time(self):
        """測試閱讀時間估算。"""
        simple_node = TreeNode(
            name="simple",
            path="simple",
            kind="lib",
            summary="簡單模組",
            confidence=90,
            capabilities=["功能1"],
        )

        complex_node = TreeNode(
            name="complex",
            path="complex",
            kind="service",
            summary="複雜模組",
            confidence=60,
            capabilities=["功能1", "功能2", "功能3", "功能4"],
        )

        simple_time = self.builder._estimate_reading_time(simple_node)
        complex_time = self.builder._estimate_reading_time(complex_node)

        assert isinstance(simple_time, str)
        assert isinstance(complex_time, str)
        assert "-" in simple_time  # 格式應該是 "X-Y 分鐘"
        assert "分鐘" in simple_time

    def test_assess_difficulty(self):
        """測試難度評估。"""
        easy_node = TreeNode(
            name="easy",
            path="easy",
            kind="lib",
            summary="簡單模組",
            confidence=90,
            capabilities=["功能1"],
        )

        hard_node = TreeNode(
            name="hard",
            path="hard",
            kind="service",
            summary="複雜模組",
            confidence=50,
            capabilities=["功能1", "功能2", "功能3", "功能4", "功能5"],
        )

        easy_difficulty = self.builder._assess_difficulty(easy_node)
        hard_difficulty = self.builder._assess_difficulty(hard_node)

        assert easy_difficulty == "easy"
        assert hard_difficulty == "hard"

    def test_calculate_statistics(self):
        """測試統計信息計算。"""
        tree = TreeNode(name="root", path="", kind="infra", summary="根目錄")
        tree.children = [
            TreeNode(
                name="service1",
                path="service1",
                kind="service",
                summary="服務1",
                confidence=85,
            ),
            TreeNode(
                name="lib1", path="lib1", kind="lib", summary="庫1", confidence=90
            ),
        ]
        tree.children[0].is_onboarding_path = True
        tree.children[1].is_recommended_reading = True

        digest_files = {"": {}, "service1": {}, "lib1": {}}

        stats = self.builder._calculate_statistics(tree, digest_files)

        assert "total_modules" in stats
        assert "total_digests" in stats
        assert "kind_distribution" in stats
        assert "average_confidence" in stats
        assert "onboarding_path_length" in stats
        assert "recommended_reading_count" in stats

        assert stats["total_modules"] == 3  # root + 2 children
        assert stats["total_digests"] == 3
        assert stats["onboarding_path_length"] == 1
        assert stats["recommended_reading_count"] == 1


class TestProjectMapValidation:
    """測試項目地圖驗證功能。"""

    def test_validate_valid_project_map(self):
        """測試有效項目地圖的驗證。"""
        tree = TreeNode(
            name="test", path="", kind="service", summary="測試", confidence=80
        )
        onboarding_path = OnboardingPath(
            steps=[{"title": "步驟1", "path": "step1"}], total_steps=1
        )

        project_map = ProjectMap(
            project_name="test_project",
            root_path="/test",
            tree=tree,
            onboarding_path=onboarding_path,
        )

        errors = validate_project_map(project_map)
        assert len(errors) == 0

    def test_validate_invalid_project_map(self):
        """測試無效項目地圖的驗證。"""
        # 空項目名稱
        invalid_map = ProjectMap(
            project_name="",
            root_path="/test",
            tree=TreeNode(name="", path="", kind="invalid", summary="", confidence=-1),
            onboarding_path=OnboardingPath(steps=[{"title": "", "path": ""}]),
        )

        errors = validate_project_map(invalid_map)
        assert len(errors) > 0
        assert any("項目名稱不能為空" in error for error in errors)

    def test_validate_tree_node(self):
        """測試樹節點驗證。"""
        from src.project_map import _validate_tree_node

        # 有效節點
        valid_node = TreeNode(
            name="valid", path="valid", kind="service", summary="有效", confidence=80
        )
        errors = _validate_tree_node(valid_node)
        assert len(errors) == 0

        # 無效節點
        invalid_node = TreeNode(
            name="", path="", kind="invalid", summary="", confidence=150
        )
        errors = _validate_tree_node(invalid_node)
        assert len(errors) > 0


class TestTreeNode:
    """測試樹節點數據類。"""

    def test_tree_node_creation(self):
        """測試樹節點創建。"""
        node = TreeNode(
            name="test",
            path="test/path",
            kind="service",
            summary="測試節點",
            capabilities=["功能1", "功能2"],
            confidence=85,
        )

        assert node.name == "test"
        assert node.path == "test/path"
        assert node.kind == "service"
        assert node.summary == "測試節點"
        assert len(node.capabilities) == 2
        assert node.confidence == 85
        assert node.importance_score == 0.0
        assert len(node.children) == 0
        assert not node.is_onboarding_path
        assert not node.is_recommended_reading

    def test_tree_node_with_children(self):
        """測試帶子節點的樹節點。"""
        parent = TreeNode(
            name="parent", path="parent", kind="infra", summary="父節點"
        )
        child = TreeNode(name="child", path="parent/child", kind="lib", summary="子節點")

        parent.children.append(child)

        assert len(parent.children) == 1
        assert parent.children[0] == child


if __name__ == "__main__":
    pytest.main([__file__])