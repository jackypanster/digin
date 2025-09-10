"""
Digin 包入口與對外 API。

導出：
- `CodebaseAnalyzer`：可被其他工具/腳本直接調用以執行分析。
- `main`：CLI 入口函數（對應 `digin` 命令）。

用途：既支持命令行使用，也便於程序化集成到現有工作流。
"""

from .analyzer import CodebaseAnalyzer
from .__main__ import main

__all__ = ["CodebaseAnalyzer", "main"]
