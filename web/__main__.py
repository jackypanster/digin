"""Digin Web 可视化界面入口点。

使用方法：
    uv run python -m web /path/to/analyzed/project
"""

import sys
from pathlib import Path

import uvicorn

from .server import create_app


def validate_target_path(path_str: str) -> Path:
    """验证目标路径。

    Args:
        path_str: 路径字符串

    Returns:
        验证后的 Path 对象

    Raises:
        SystemExit: 路径无效时退出
    """
    path = Path(path_str)

    # 检查目录是否存在
    if not path.exists():
        print(f"❌ 错误：目录不存在 - {path}")
        sys.exit(1)

    if not path.is_dir():
        print(f"❌ 错误：不是一个目录 - {path}")
        sys.exit(1)

    # 检查是否包含 digest.json
    digest_file = path / "digest.json"
    if not digest_file.exists():
        print(f"❌ 错误：目录中没有找到 digest.json 文件 - {path}")
        print("💡 请先运行分析命令：uv run python -m src /path/to/project")
        sys.exit(1)

    return path.resolve()


def main() -> None:
    """主函数。"""
    # 检查命令行参数
    if len(sys.argv) != 2:
        print("❌ 用法错误")
        print("📖 正确用法：uv run python -m web /path/to/analyzed/project")
        print()
        print("🔍 示例：")
        print("   1. 先分析项目：uv run python -m src /path/to/project")
        print("   2. 启动 Web 界面：uv run python -m web /path/to/project")
        sys.exit(1)

    # 验证目标路径
    target_path = validate_target_path(sys.argv[1])

    # 创建应用
    app = create_app(target_path)

    # 显示启动信息
    print("🚀 启动 Digin Web 可视化界面...")
    print(f"📁 分析目标：{target_path}")
    print(f"🌐 访问地址：http://localhost:8000")
    print("🔄 手动刷新浏览器以获取最新数据")
    print("⏹️  按 Ctrl+C 停止服务")
    print()

    # 启动服务器
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            access_log=False,  # 减少日志噪音
        )
    except KeyboardInterrupt:
        print("\n👋 Web 服务器已停止")
    except Exception as e:
        print(f"\n❌ 启动失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()