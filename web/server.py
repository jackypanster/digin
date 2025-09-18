"""FastAPI 服务器，提供 Digin 分析结果的 Web 界面。

简单的只读服务，用于展示 digest.json 文件内容。
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Import project map functionality
import sys
sys.path.append(str(Path(__file__).parent.parent))
from src.project_map import ProjectMapBuilder
from src.config import DigginSettings


class DiginWebServer:
    """Digin Web 服务器类。"""

    def __init__(self, target_path: Path):
        """初始化服务器。

        Args:
            target_path: 分析的目标目录（包含 digest.json 文件）
        """
        self.target_path = target_path.resolve()
        self.app = FastAPI(title="Digin Web Viewer", version="0.1.0")
        self._setup_routes()

    def _setup_routes(self) -> None:
        """设置路由。"""
        # 挂载静态文件
        static_path = Path(__file__).parent / "static"
        self.app.mount("/static", StaticFiles(directory=static_path), name="static")

        # 根路径返回主页
        @self.app.get("/")
        async def root() -> FileResponse:
            """返回主页。"""
            return FileResponse(static_path / "index.html")

        # API 路由：获取 digest.json
        @self.app.get("/api/digest")
        async def get_digest(path: str = Query("/", description="目录路径")) -> Dict[str, Any]:
            """获取指定路径的 digest.json 内容。

            Args:
                path: 相对于目标目录的路径

            Returns:
                digest.json 的内容

            Raises:
                HTTPException: 路径不安全或文件不存在
            """
            return self._read_digest_safely(path)

        # API 路由：获取目录信息
        @self.app.get("/api/info")
        async def get_info() -> Dict[str, Any]:
            """获取目标目录基本信息。"""
            return {
                "target_path": str(self.target_path),
                "target_name": self.target_path.name,
                "has_root_digest": (self.target_path / "digest.json").exists()
            }

        # API 路由：获取项目地图
        @self.app.get("/api/project-map")
        async def get_project_map() -> Dict[str, Any]:
            """获取项目地图数据，包含树结构和引导路径。

            Returns:
                项目地图数据

            Raises:
                HTTPException: 生成项目地图失败
            """
            return self._build_project_map()

    def _read_digest_safely(self, relative_path: str) -> Dict[str, Any]:
        """安全地读取 digest.json 文件。

        Args:
            relative_path: 相对路径

        Returns:
            digest.json 内容

        Raises:
            HTTPException: 路径不安全或文件不存在
        """
        # 规范化路径
        if relative_path.startswith("/"):
            relative_path = relative_path[1:]

        # 构建完整路径
        if relative_path:
            full_path = self.target_path / relative_path
        else:
            full_path = self.target_path

        # 安全检查：确保路径在目标目录内
        try:
            resolved_path = full_path.resolve()
            if not str(resolved_path).startswith(str(self.target_path)):
                raise HTTPException(status_code=403, detail="路径不安全：不能访问目标目录外的文件")
        except (OSError, ValueError):
            raise HTTPException(status_code=400, detail="无效的路径格式")

        # 检查 digest.json 是否存在
        digest_file = resolved_path / "digest.json"
        if not digest_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"未找到 digest.json 文件：{relative_path or '根目录'}"
            )

        # 读取并返回内容
        try:
            with open(digest_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="digest.json 文件格式错误")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取文件失败：{str(e)}")

    def _build_project_map(self) -> Dict[str, Any]:
        """构建项目地图数据。

        Returns:
            项目地图数据

        Raises:
            HTTPException: 构建失败
        """
        try:
            # 创建默认配置（用于项目地图生成）
            settings = DigginSettings()

            # 构建项目地图
            builder = ProjectMapBuilder(settings)
            project_map = builder.build_project_map(self.target_path)

            # 转换为可序列化的字典
            return self._serialize_project_map(project_map)

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"构建项目地图失败：{str(e)}"
            )

    def _serialize_project_map(self, project_map) -> Dict[str, Any]:
        """将项目地图序列化为字典格式。

        Args:
            project_map: ProjectMap 对象

        Returns:
            可序列化的字典
        """
        def serialize_tree_node(node) -> Dict[str, Any]:
            """递归序列化树节点。"""
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
                "children": [serialize_tree_node(child) for child in node.children],
            }

        return {
            "project_name": project_map.project_name,
            "root_path": project_map.root_path,
            "tree": serialize_tree_node(project_map.tree),
            "onboarding_path": {
                "steps": project_map.onboarding_path.steps,
                "total_steps": project_map.onboarding_path.total_steps,
                "estimated_time": project_map.onboarding_path.estimated_time,
                "difficulty": project_map.onboarding_path.difficulty,
            },
            "recommended_reading": project_map.recommended_reading,
            "statistics": project_map.statistics,
            "generated_at": project_map.generated_at,
            "version": project_map.version,
        }


def create_app(target_path: Path) -> FastAPI:
    """创建 FastAPI 应用。

    Args:
        target_path: 目标分析目录

    Returns:
        配置好的 FastAPI 应用
    """
    server = DiginWebServer(target_path)
    return server.app