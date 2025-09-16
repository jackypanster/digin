# Code Review - src/

Summary
- Target-specific configuration is accidentally ignored and certain project names short-circuit analysis, so core workflows can fail without obvious feedback.

High
- ✅ **FIXED** `src/config.py:109` — ~~使用 `Path.cwd()` 查找 `.digin.json`，导致当用户在任意目录执行 `digin /path/to/project` 时不会加载目标仓库下的配置，项目专属忽略规则/模型参数全部失效，分析结果偏差很大。~~ **解决方案：完全删除项目级 `.digin.json` 配置功能，简化配置系统为 default.json → CLI 参数两层结构，符合项目 "Less is More" 理念。**
- `src/traverser.py:65` — 根目录名若命中忽略规则（例如项目叫 `dist`/`build`），`find_leaf_directories` 会直接返回空列表，整棵树被跳过，最终得到“Analysis failed…”的空摘要。这与忽略子目录的初衷相违背，应始终遍历根目录本身。

Medium
- `src/__main__.py:350` — `setup_analyzer` 在 dry-run 模式下也强制检测 AI CLI 是否存在，无法在未安装 Claude/Gemini CLI 时预览分析计划，降低可维护性。建议仅在真正执行分析时检查 CLI。

Quick Wins
- 目前无。

Tests
- 未执行（仅做静态代码审查）。

Patch Ideas
- ✅ `src/config.py`：~~在加载配置时接受目标路径参数，优先读取 `target_path / ".digin.json"`。~~ **已通过删除项目级配置功能解决。**
- `src/traverser.py`：移除对根目录的忽略判断，或单独放行第一层调用。
- `src/__main__.py`：在 dry-run 分支前跳过 `is_cli_available` 检查，或延迟到真正调用 AI 时再验证。
