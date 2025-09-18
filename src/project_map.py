"""項目地圖與引導路徑生成。

核心功能：
- 從 digest 文件構建項目樹結構
- 計算重要性評分並生成引導路徑
- 提供推薦閱讀列表和探索建議
- 支持多語言導覽（中文/英文）

設計理念：幫助新人快速理解代碼庫結構，找到最佳的學習路徑。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from .config import DigginSettings
from .logger import get_logger


@dataclass
class TreeNode:
    """項目樹節點，表示一個目錄或模塊。"""

    name: str
    path: str
    kind: str
    summary: str
    capabilities: List[str] = field(default_factory=list)
    confidence: int = 0
    importance_score: float = 0.0
    children: List["TreeNode"] = field(default_factory=list)
    narrative: Optional[Dict[str, str]] = None
    is_onboarding_path: bool = False
    is_recommended_reading: bool = False


@dataclass
class OnboardingPath:
    """引導路徑，包含建議的學習順序和說明。"""

    steps: List[Dict[str, Any]] = field(default_factory=list)
    total_steps: int = 0
    estimated_time: str = ""
    difficulty: str = "medium"  # easy, medium, hard


@dataclass
class ProjectMap:
    """完整的項目地圖結構。"""

    project_name: str
    root_path: str
    tree: TreeNode
    onboarding_path: OnboardingPath
    recommended_reading: List[Dict[str, Any]] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""
    version: str = "1.0"


class ProjectMapBuilder:
    """項目地圖構建器，負責從 digest 文件生成完整的項目地圖。"""

    def __init__(self, settings: DigginSettings):
        """初始化項目地圖構建器。

        Args:
            settings: 配置設置
        """
        self.settings = settings
        self.logger = get_logger("project_map")

    def build_project_map(self, root_path: Path) -> ProjectMap:
        """構建完整的項目地圖。

        Args:
            root_path: 項目根路徑

        Returns:
            完整的項目地圖
        """
        self.logger.info(f"Building project map for: {root_path}")

        # 收集所有 digest 文件
        digest_files = self._collect_digest_files(root_path)
        if not digest_files:
            return self._create_empty_project_map(root_path)

        # 構建樹結構
        tree = self._build_tree_structure(root_path, digest_files)

        # 計算重要性評分
        self._calculate_importance_scores(tree)

        # 生成引導路徑
        onboarding_path = self._generate_onboarding_path(tree)

        # 選擇推薦閱讀
        recommended_reading = self._select_recommended_reading(tree)

        # 計算統計信息
        statistics = self._calculate_statistics(tree, digest_files)

        return ProjectMap(
            project_name=root_path.name,
            root_path=str(root_path),
            tree=tree,
            onboarding_path=onboarding_path,
            recommended_reading=recommended_reading,
            statistics=statistics,
            generated_at=self._get_current_time(),
        )

    def _collect_digest_files(self, root_path: Path) -> Dict[str, Dict[str, Any]]:
        """收集所有 digest.json 文件。

        Args:
            root_path: 根路徑

        Returns:
            路徑到 digest 內容的映射
        """
        digest_files = {}

        for digest_file in root_path.rglob("digest.json"):
            try:
                with open(digest_file, "r", encoding="utf-8") as f:
                    digest_data = json.load(f)

                relative_path = str(digest_file.parent.relative_to(root_path))
                if relative_path == ".":
                    relative_path = ""

                digest_files[relative_path] = digest_data
                self.logger.debug(f"Loaded digest: {relative_path}")

            except (json.JSONDecodeError, OSError) as e:
                self.logger.warning(f"Failed to load digest {digest_file}: {e}")

        self.logger.info(f"Collected {len(digest_files)} digest files")
        return digest_files

    def _build_tree_structure(
        self, root_path: Path, digest_files: Dict[str, Dict[str, Any]]
    ) -> TreeNode:
        """構建樹結構。

        Args:
            root_path: 根路徑
            digest_files: digest 文件數據

        Returns:
            根節點
        """
        # 創建路徑到節點的映射
        nodes = {}

        # 按路徑深度排序，確保父節點先創建
        sorted_paths = sorted(digest_files.keys(), key=lambda p: len(p.split("/")))

        for path, digest_data in [(p, digest_files[p]) for p in sorted_paths]:
            node = TreeNode(
                name=digest_data.get("name", path.split("/")[-1] if path else root_path.name),
                path=path,
                kind=digest_data.get("kind", "unknown"),
                summary=digest_data.get("summary", ""),
                capabilities=digest_data.get("capabilities", []),
                confidence=digest_data.get("confidence", 0),
                narrative=digest_data.get("narrative"),
            )

            nodes[path] = node

            # 找到父節點並建立關係
            if path:  # 非根節點
                parent_path = "/".join(path.split("/")[:-1])
                if parent_path in nodes:
                    nodes[parent_path].children.append(node)
                elif "" in nodes:  # 直接添加到根節點
                    nodes[""].children.append(node)

        # 返回根節點，如果沒有根 digest 則創建虛擬根節點
        if "" in nodes:
            return nodes[""]
        else:
            # 創建虛擬根節點
            root_node = TreeNode(
                name=root_path.name,
                path="",
                kind="infra",
                summary=f"項目 {root_path.name} 的根目錄",
            )
            # 添加所有頂級節點作為子節點
            for path, node in nodes.items():
                if "/" not in path:  # 頂級路徑
                    root_node.children.append(node)

            return root_node

    def _calculate_importance_scores(self, tree: TreeNode) -> None:
        """計算重要性評分。

        Args:
            tree: 樹根節點
        """

        def calculate_node_score(node: TreeNode) -> float:
            """計算單個節點的重要性評分。"""
            score = 0.0

            # 基礎評分：置信度
            score += node.confidence * 0.1

            # 功能數量加成
            score += len(node.capabilities) * 2

            # 根據類型加權
            kind_weights = {
                "service": 10,  # 業務服務最重要
                "lib": 8,  # 工具庫次之
                "infra": 7,  # 基礎設施
                "ui": 6,  # 用戶界面
                "config": 4,  # 配置
                "test": 3,  # 測試
                "docs": 2,  # 文檔
            }
            score += kind_weights.get(node.kind, 1)

            # 子節點數量加成（表示架構重要性）
            score += len(node.children) * 1.5

            # 特殊加成：如果是入口點（包含 main, index, app 等關鍵詞）
            entry_keywords = ["main", "index", "app", "server", "client", "core"]
            if any(keyword in node.name.lower() for keyword in entry_keywords):
                score += 5

            return score

        def apply_scores(node: TreeNode) -> None:
            """遞歸應用評分。"""
            node.importance_score = calculate_node_score(node)
            for child in node.children:
                apply_scores(child)

        apply_scores(tree)
        self.logger.debug("Calculated importance scores for all nodes")

    def _generate_onboarding_path(self, tree: TreeNode) -> OnboardingPath:
        """生成引導路徑。

        Args:
            tree: 樹根節點

        Returns:
            引導路徑
        """

        def collect_nodes(node: TreeNode) -> List[TreeNode]:
            """收集所有節點。"""
            nodes = [node]
            for child in node.children:
                nodes.extend(collect_nodes(child))
            return nodes

        all_nodes = collect_nodes(tree)

        # 按重要性評分排序，選取前 5-7 個節點作為引導路徑
        sorted_nodes = sorted(all_nodes, key=lambda n: n.importance_score, reverse=True)
        path_nodes = sorted_nodes[:min(7, len(sorted_nodes))]

        # 標記引導路徑節點
        for node in path_nodes:
            node.is_onboarding_path = True

        # 生成引導步驟
        steps = []
        for i, node in enumerate(path_nodes):
            step = {
                "step": i + 1,
                "title": node.name,
                "path": node.path,
                "kind": node.kind,
                "description": node.summary,
                "estimated_time": self._estimate_reading_time(node),
                "difficulty": self._assess_difficulty(node),
            }

            # 添加 narrative 信息如果存在
            if node.narrative:
                step["handshake"] = node.narrative.get("handshake", "")
                step["next_steps"] = node.narrative.get("next_steps", "")

            steps.append(step)

        return OnboardingPath(
            steps=steps,
            total_steps=len(steps),
            estimated_time=f"{len(steps) * 15}-{len(steps) * 30} 分鐘",
            difficulty=self._assess_overall_difficulty(path_nodes),
        )

    def _select_recommended_reading(self, tree: TreeNode) -> List[Dict[str, Any]]:
        """選擇推薦閱讀。

        Args:
            tree: 樹根節點

        Returns:
            推薦閱讀列表
        """

        def collect_nodes(node: TreeNode) -> List[TreeNode]:
            nodes = [node]
            for child in node.children:
                nodes.extend(collect_nodes(child))
            return nodes

        all_nodes = collect_nodes(tree)

        # 選擇推薦閱讀：高置信度 + 豐富功能的節點
        recommended_nodes = [
            node
            for node in all_nodes
            if node.confidence >= 70 and len(node.capabilities) >= 2
        ]

        # 按評分排序，選取前 10 個
        recommended_nodes.sort(key=lambda n: n.importance_score, reverse=True)
        recommended_nodes = recommended_nodes[:10]

        # 標記推薦閱讀節點
        for node in recommended_nodes:
            node.is_recommended_reading = True

        # 生成推薦閱讀列表
        reading_list = []
        for node in recommended_nodes:
            item = {
                "title": node.name,
                "path": node.path,
                "kind": node.kind,
                "summary": node.summary,
                "capabilities": node.capabilities[:3],  # 只顯示前 3 個功能
                "confidence": node.confidence,
                "reason": self._generate_recommendation_reason(node),
            }
            reading_list.append(item)

        return reading_list

    def _calculate_statistics(
        self, tree: TreeNode, digest_files: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """計算統計信息。

        Args:
            tree: 樹根節點
            digest_files: digest 文件數據

        Returns:
            統計信息
        """

        def collect_nodes(node: TreeNode) -> List[TreeNode]:
            nodes = [node]
            for child in node.children:
                nodes.extend(collect_nodes(child))
            return nodes

        all_nodes = collect_nodes(tree)

        # 按類型分組統計
        kind_counts = defaultdict(int)
        for node in all_nodes:
            kind_counts[node.kind] += 1

        # 計算平均置信度
        avg_confidence = (
            sum(node.confidence for node in all_nodes) / len(all_nodes)
            if all_nodes
            else 0
        )

        return {
            "total_modules": len(all_nodes),
            "total_digests": len(digest_files),
            "kind_distribution": dict(kind_counts),
            "average_confidence": round(avg_confidence, 1),
            "onboarding_path_length": len([n for n in all_nodes if n.is_onboarding_path]),
            "recommended_reading_count": len(
                [n for n in all_nodes if n.is_recommended_reading]
            ),
        }

    def _create_empty_project_map(self, root_path: Path) -> ProjectMap:
        """創建空的項目地圖。"""
        empty_tree = TreeNode(
            name=root_path.name,
            path="",
            kind="unknown",
            summary="暫無分析結果的項目",
        )

        return ProjectMap(
            project_name=root_path.name,
            root_path=str(root_path),
            tree=empty_tree,
            onboarding_path=OnboardingPath(),
            statistics={"total_modules": 0, "total_digests": 0},
            generated_at=self._get_current_time(),
        )

    def _estimate_reading_time(self, node: TreeNode) -> str:
        """估算閱讀時間。"""
        base_time = 10  # 基礎 10 分鐘
        complexity_bonus = len(node.capabilities) * 3
        confidence_factor = (100 - node.confidence) / 100 * 5
        total_time = base_time + complexity_bonus + confidence_factor
        return f"{int(total_time)}-{int(total_time * 1.5)} 分鐘"

    def _assess_difficulty(self, node: TreeNode) -> str:
        """評估難度。"""
        if node.confidence >= 80 and len(node.capabilities) <= 3:
            return "easy"
        elif node.confidence >= 60 and len(node.capabilities) <= 6:
            return "medium"
        else:
            return "hard"

    def _assess_overall_difficulty(self, nodes: List[TreeNode]) -> str:
        """評估整體難度。"""
        difficulties = [self._assess_difficulty(node) for node in nodes]
        hard_count = difficulties.count("hard")
        medium_count = difficulties.count("medium")

        if hard_count >= len(nodes) * 0.4:
            return "hard"
        elif medium_count + hard_count >= len(nodes) * 0.6:
            return "medium"
        else:
            return "easy"

    def _generate_recommendation_reason(self, node: TreeNode) -> str:
        """生成推薦理由。"""
        reasons = []

        if node.confidence >= 90:
            reasons.append("分析置信度很高")
        if len(node.capabilities) >= 4:
            reasons.append("功能豐富")
        if node.kind in ["service", "lib"]:
            reasons.append("核心業務模塊")
        if node.importance_score >= 15:
            reasons.append("架構重要性高")

        return "、".join(reasons) if reasons else "值得深入了解"

    def _get_current_time(self) -> str:
        """獲取當前時間字符串。"""
        from datetime import datetime

        return datetime.now().isoformat()


def validate_project_map(project_map: ProjectMap) -> List[str]:
    """驗證項目地圖的有效性。

    Args:
        project_map: 要驗證的項目地圖

    Returns:
        驗證錯誤列表，空列表表示驗證通過
    """
    errors = []

    # 基本字段驗證
    if not project_map.project_name:
        errors.append("項目名稱不能為空")

    if not project_map.root_path:
        errors.append("根路徑不能為空")

    # 樹結構驗證
    if not project_map.tree:
        errors.append("項目樹不能為空")
    else:
        tree_errors = _validate_tree_node(project_map.tree)
        errors.extend(tree_errors)

    # 引導路徑驗證
    if project_map.onboarding_path.steps:
        for i, step in enumerate(project_map.onboarding_path.steps):
            if not step.get("title"):
                errors.append(f"引導路徑步驟 {i+1} 缺少標題")
            if not step.get("path"):
                errors.append(f"引導路徑步驟 {i+1} 缺少路徑")

    return errors


def _validate_tree_node(node: TreeNode, path_prefix: str = "") -> List[str]:
    """驗證樹節點的有效性。"""
    errors = []

    if not node.name:
        errors.append(f"節點 {path_prefix} 缺少名稱")

    if node.kind not in [
        "service",
        "lib",
        "ui",
        "infra",
        "config",
        "test",
        "docs",
        "unknown",
    ]:
        errors.append(f"節點 {path_prefix} 類型無效: {node.kind}")

    if not 0 <= node.confidence <= 100:
        errors.append(f"節點 {path_prefix} 置信度無效: {node.confidence}")

    # 遞歸驗證子節點
    for child in node.children:
        child_path = f"{path_prefix}/{child.name}" if path_prefix else child.name
        child_errors = _validate_tree_node(child, child_path)
        errors.extend(child_errors)

    return errors