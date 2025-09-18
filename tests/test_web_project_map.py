"""測試 Web API 項目地圖端點。"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from web.server import DiginWebServer, create_app
from src.project_map import ProjectMap, TreeNode, OnboardingPath


class TestDiginWebServerProjectMap:
    """測試 DiginWebServer 的項目地圖功能。"""

    def setup_method(self):
        """設置測試環境。"""
        self.test_path = Path("/test/project")
        self.server = DiginWebServer(self.test_path)
        self.client = TestClient(self.server.app)

    def test_project_map_endpoint_exists(self):
        """測試項目地圖端點存在。"""
        # 模擬項目地圖數據
        mock_project_map = self._create_mock_project_map()

        with patch.object(
            self.server, "_build_project_map", return_value=mock_project_map
        ):
            response = self.client.get("/api/project-map")
            assert response.status_code == 200

    def test_project_map_response_structure(self):
        """測試項目地圖響應結構。"""
        mock_project_map = self._create_mock_project_map()

        with patch.object(
            self.server, "_build_project_map", return_value=mock_project_map
        ):
            response = self.client.get("/api/project-map")
            data = response.json()

            # 檢查基本結構
            assert "project_name" in data
            assert "root_path" in data
            assert "tree" in data
            assert "onboarding_path" in data
            assert "recommended_reading" in data
            assert "statistics" in data
            assert "generated_at" in data
            assert "version" in data

    def test_project_map_tree_structure(self):
        """測試項目地圖樹結構。"""
        mock_project_map = self._create_mock_project_map()

        with patch.object(
            self.server, "_build_project_map", return_value=mock_project_map
        ):
            response = self.client.get("/api/project-map")
            data = response.json()

            tree = data["tree"]
            assert "name" in tree
            assert "path" in tree
            assert "kind" in tree
            assert "summary" in tree
            assert "capabilities" in tree
            assert "confidence" in tree
            assert "importance_score" in tree
            assert "children" in tree
            assert "is_onboarding_path" in tree
            assert "is_recommended_reading" in tree

    def test_project_map_onboarding_path_structure(self):
        """測試引導路徑結構。"""
        mock_project_map = self._create_mock_project_map()

        with patch.object(
            self.server, "_build_project_map", return_value=mock_project_map
        ):
            response = self.client.get("/api/project-map")
            data = response.json()

            onboarding_path = data["onboarding_path"]
            assert "steps" in onboarding_path
            assert "total_steps" in onboarding_path
            assert "estimated_time" in onboarding_path
            assert "difficulty" in onboarding_path

            if onboarding_path["steps"]:
                step = onboarding_path["steps"][0]
                assert "step" in step
                assert "title" in step
                assert "path" in step

    def test_build_project_map_success(self):
        """測試成功構建項目地圖。"""
        mock_project_map = self._create_mock_project_map()

        with patch("web.server.DigginSettings"), patch(
            "web.server.ProjectMapBuilder"
        ) as mock_builder_class:
            mock_builder = Mock()
            mock_builder.build_project_map.return_value = mock_project_map
            mock_builder_class.return_value = mock_builder

            result = self.server._build_project_map()

            assert isinstance(result, dict)
            assert "project_name" in result
            assert "tree" in result

    def test_build_project_map_error_handling(self):
        """測試項目地圖構建錯誤處理。"""
        with patch("web.server.DigginSettings"), patch(
            "web.server.ProjectMapBuilder"
        ) as mock_builder_class:
            mock_builder = Mock()
            mock_builder.build_project_map.side_effect = Exception("構建失敗")
            mock_builder_class.return_value = mock_builder

            response = self.client.get("/api/project-map")
            assert response.status_code == 500
            assert "構建項目地圖失敗" in response.json()["detail"]

    def test_serialize_project_map(self):
        """測試項目地圖序列化。"""
        # 創建項目地圖對象
        tree = TreeNode(
            name="root",
            path="",
            kind="infra",
            summary="根目錄",
            capabilities=["功能1"],
            confidence=80,
            importance_score=10.5,
        )
        tree.is_onboarding_path = True
        tree.is_recommended_reading = False

        child = TreeNode(
            name="child",
            path="child",
            kind="service",
            summary="子目錄",
            capabilities=["功能2", "功能3"],
            confidence=90,
            importance_score=15.0,
        )
        tree.children = [child]

        onboarding_path = OnboardingPath(
            steps=[{"step": 1, "title": "步驟1", "path": "step1"}],
            total_steps=1,
            estimated_time="10-15 分鐘",
            difficulty="medium",
        )

        project_map = ProjectMap(
            project_name="test_project",
            root_path="/test",
            tree=tree,
            onboarding_path=onboarding_path,
            recommended_reading=[{"title": "推薦1", "path": "rec1"}],
            statistics={"total_modules": 2},
            generated_at="2023-01-01T00:00:00",
            version="1.0",
        )

        result = self.server._serialize_project_map(project_map)

        # 檢查序列化結果
        assert result["project_name"] == "test_project"
        assert result["root_path"] == "/test"

        # 檢查樹序列化
        tree_data = result["tree"]
        assert tree_data["name"] == "root"
        assert tree_data["confidence"] == 80
        assert tree_data["importance_score"] == 10.5
        assert tree_data["is_onboarding_path"] == True
        assert len(tree_data["children"]) == 1

        # 檢查子節點
        child_data = tree_data["children"][0]
        assert child_data["name"] == "child"
        assert child_data["importance_score"] == 15.0
        assert len(child_data["capabilities"]) == 2

        # 檢查引導路徑
        onboarding_data = result["onboarding_path"]
        assert onboarding_data["total_steps"] == 1
        assert onboarding_data["difficulty"] == "medium"
        assert len(onboarding_data["steps"]) == 1

    def test_serialize_empty_tree(self):
        """測試空樹序列化。"""
        tree = TreeNode(name="empty", path="", kind="unknown", summary="空目錄")

        onboarding_path = OnboardingPath()

        project_map = ProjectMap(
            project_name="empty_project",
            root_path="/empty",
            tree=tree,
            onboarding_path=onboarding_path,
        )

        result = self.server._serialize_project_map(project_map)

        assert result["project_name"] == "empty_project"
        assert result["tree"]["name"] == "empty"
        assert len(result["tree"]["children"]) == 0
        assert result["onboarding_path"]["total_steps"] == 0

    def test_create_app_function(self):
        """測試 create_app 函數。"""
        test_path = Path("/test/app")
        app = create_app(test_path)

        assert app is not None
        client = TestClient(app)

        # 測試基本端點
        with patch.object(DiginWebServer, "_build_project_map", return_value={}):
            response = client.get("/api/info")
            assert response.status_code == 200

    def test_narrative_fields_in_response(self):
        """測試響應中的敘述字段。"""
        # 創建帶敘述字段的樹節點
        tree = TreeNode(
            name="root",
            path="",
            kind="service",
            summary="根目錄",
            narrative={
                "summary": "這是人話版本的摘要",
                "handshake": "👋 歡迎探索項目",
                "next_steps": "建議先查看核心模組",
            },
        )

        project_map = ProjectMap(
            project_name="test",
            root_path="/test",
            tree=tree,
            onboarding_path=OnboardingPath(),
        )

        result = self.server._serialize_project_map(project_map)

        tree_data = result["tree"]
        assert "narrative" in tree_data
        narrative = tree_data["narrative"]
        assert narrative["summary"] == "這是人話版本的摘要"
        assert narrative["handshake"] == "👋 歡迎探索項目"
        assert narrative["next_steps"] == "建議先查看核心模組"

    def test_complex_nested_tree_serialization(self):
        """測試複雜嵌套樹的序列化。"""
        # 創建多層嵌套樹
        root = TreeNode(name="root", path="", kind="infra", summary="根")

        level1_1 = TreeNode(name="src", path="src", kind="lib", summary="源碼")
        level1_2 = TreeNode(name="tests", path="tests", kind="test", summary="測試")

        level2_1 = TreeNode(
            name="auth", path="src/auth", kind="service", summary="認證"
        )
        level2_2 = TreeNode(name="utils", path="src/utils", kind="lib", summary="工具")

        # 建立樹結構
        root.children = [level1_1, level1_2]
        level1_1.children = [level2_1, level2_2]

        project_map = ProjectMap(
            project_name="complex",
            root_path="/complex",
            tree=root,
            onboarding_path=OnboardingPath(),
        )

        result = self.server._serialize_project_map(project_map)

        # 檢查嵌套結構
        tree_data = result["tree"]
        assert len(tree_data["children"]) == 2

        src_node = tree_data["children"][0]
        assert src_node["name"] == "src"
        assert len(src_node["children"]) == 2

        auth_node = src_node["children"][0]
        assert auth_node["name"] == "auth"
        assert auth_node["path"] == "src/auth"

    def _create_mock_project_map(self):
        """創建模擬項目地圖數據。"""
        tree = TreeNode(
            name="test_project",
            path="",
            kind="infra",
            summary="測試項目",
            capabilities=["功能1", "功能2"],
            confidence=85,
            importance_score=12.5,
        )

        child = TreeNode(
            name="src",
            path="src",
            kind="lib",
            summary="源碼目錄",
            capabilities=["核心功能"],
            confidence=90,
            importance_score=15.0,
        )
        child.is_onboarding_path = True

        tree.children = [child]

        onboarding_path = OnboardingPath(
            steps=[
                {
                    "step": 1,
                    "title": "src",
                    "path": "src",
                    "description": "源碼目錄",
                    "estimated_time": "10-15 分鐘",
                    "difficulty": "easy",
                }
            ],
            total_steps=1,
            estimated_time="10-15 分鐘",
            difficulty="easy",
        )

        return {
            "project_name": "test_project",
            "root_path": "/test",
            "tree": self._serialize_tree_node(tree),
            "onboarding_path": {
                "steps": onboarding_path.steps,
                "total_steps": onboarding_path.total_steps,
                "estimated_time": onboarding_path.estimated_time,
                "difficulty": onboarding_path.difficulty,
            },
            "recommended_reading": [{"title": "推薦閱讀", "path": "recommended"}],
            "statistics": {"total_modules": 2},
            "generated_at": "2023-01-01T00:00:00",
            "version": "1.0",
        }

    def _serialize_tree_node(self, node):
        """序列化樹節點（測試輔助函數）。"""
        return {
            "name": node.name,
            "path": node.path,
            "kind": node.kind,
            "summary": node.summary,
            "capabilities": node.capabilities,
            "confidence": node.confidence,
            "importance_score": node.importance_score,
            "narrative": node.narrative,
            "is_onboarding_path": node.is_onboarding_path,
            "is_recommended_reading": node.is_recommended_reading,
            "children": [self._serialize_tree_node(child) for child in node.children],
        }


class TestWebProjectMapIntegration:
    """項目地圖 Web 端點集成測試。"""

    @pytest.mark.integration
    def test_full_project_map_workflow(self):
        """測試完整的項目地圖工作流程。"""
        test_path = Path("/test/integration")
        server = DiginWebServer(test_path)
        client = TestClient(server.app)

        # 模擬完整的項目地圖構建流程
        with patch("web.server.DigginSettings") as mock_settings, patch(
            "web.server.ProjectMapBuilder"
        ) as mock_builder_class:

            # 設置模擬對象
            mock_settings.return_value = Mock()
            mock_builder = Mock()
            mock_builder_class.return_value = mock_builder

            # 創建真實的項目地圖結構
            tree = TreeNode(
                name="integration_test",
                path="",
                kind="infra",
                summary="集成測試項目",
                confidence=80,
            )

            project_map = ProjectMap(
                project_name="integration_test",
                root_path=str(test_path),
                tree=tree,
                onboarding_path=OnboardingPath(
                    steps=[{"step": 1, "title": "開始", "path": ""}], total_steps=1
                ),
                statistics={"total_modules": 1},
                generated_at="2023-01-01T00:00:00",
            )

            mock_builder.build_project_map.return_value = project_map

            # 測試 API 調用
            response = client.get("/api/project-map")

            assert response.status_code == 200
            data = response.json()
            assert data["project_name"] == "integration_test"
            assert data["onboarding_path"]["total_steps"] == 1

    @pytest.mark.integration
    def test_error_handling_integration(self):
        """測試錯誤處理集成。"""
        test_path = Path("/test/error")
        server = DiginWebServer(test_path)
        client = TestClient(server.app)

        # 測試構建失敗的情況
        with patch("web.server.DigginSettings"), patch(
            "web.server.ProjectMapBuilder"
        ) as mock_builder_class:

            mock_builder = Mock()
            mock_builder.build_project_map.side_effect = ValueError("測試錯誤")
            mock_builder_class.return_value = mock_builder

            response = client.get("/api/project-map")

            assert response.status_code == 500
            error_data = response.json()
            assert "構建項目地圖失敗" in error_data["detail"]
            assert "測試錯誤" in error_data["detail"]


if __name__ == "__main__":
    pytest.main([__file__])