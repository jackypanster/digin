#!/usr/bin/env markdown
# 架構導覽與上手路線（Digin）

> 目標：幫讀者在 30–60 分鐘內「跑起來 → 看懂主線 → 掌握各模塊用途」。

## 一、項目總覽：自底向上理解代碼庫
- 工作流：葉子目錄用 AI 產生 `digest.json` → 父級聚合 → 根目錄得到全局摘要與統計。
- 節流策略：嚴格文件過濾、文本預覽（≤2KB）、目錄級緩存，控制 token 與 IO 成本。
- 關鍵目錄：
  - `src/` 主要代碼與 CLI 入口。
  - `config/` 默認配置與 Prompt 模板。
  - `tests/` 行為與邏輯的最佳參考實例。
  - `docs/PRD.md` 產品層面的意圖與邊界。

## 二、快速跑通（5 分鐘）
- 安裝依賴：`uv sync --dev`（或 `uv sync`）
- 開啟預覽：`digin --dry-run -v` 或 `python -m src --dry-run -v`
  - 觀察：葉/父目錄數量、分析順序、估算文件數。
- 正式分析：`digin .`（可加 `--provider gemini`、`--verbose`）
- 清理緩存：`digin . --clear-cache`；忽略緩存：`digin . --force`

## 三、循序切入代碼（建議閱讀順序）
1) `src/__main__.py`（CLI 入口）
- 負責 CLI 參數、配置合併、dry-run、進度展示與結果輸出。
- 看點：`main()` 的參數處理、`_show_dry_run()`、`_display_results_*()`。

2) `src/config.py` + `config/default.json`
- 配置優先級：默認 → CLI 指定文件。
- 關注鍵：`ignore_dirs`/`ignore_files`/`include_extensions`、`api_provider`、`cache_enabled`。

3) `src/traverser.py`
- 生成「葉 → 父 → 根」的分析順序；收集文件信息與內容預覽。
- 先看 `get_analysis_order()`，再看 `_should_ignore_*()` 與 `_collect_file_info()`。

4) `src/ai_client.py`
- 讀取 `config/prompt.txt` 組裝 Prompt；調用 Claude/Gemini CLI；解析 JSON（含容錯提取）。
- 入口：`ClaudeClient.analyze_directory()`；關注 `_build_prompt()` 與 `_parse_response()`。

5) `src/analyzer.py`
- Orchestrator：對每個目錄 `_analyze_directory()`；葉用 AI，父用 `SummaryAggregator`。
- 看 `analyze()` 主循環與 `dry_run()` 統計如何產生。

6) `src/aggregator.py`
- 聚合子摘要：kind 推斷、能力/接口/依賴/配置/風險合併、置信度計算與證據匯總。
- 從 `aggregate_summaries()` 入手，逐步追 `_determine_aggregated_kind()`、`_merge_*()`。

7) `src/cache.py`
- 以「相對路徑+元信息+小文本內容」計算哈希，維護 `digest.json`/`.digin_hash`。
- 看 `get_cached_digest()`、`save_digest()` 與 `_calculate_directory_hash()`。

8) `tests/`
- 定位真實意圖與邊界條件。建議先讀：`tests/test_traverser.py`、`tests/test_analyzer.py`。

## 四、實操路線（帶檢查點）
- Step A：`digin --dry-run -v`
  - 檢查：葉/父比例是否合理；分析順序與實際目錄結構是否一致。
- Step B：`digin . --provider claude --verbose`
  - 檢查：緩存命中率、AI 調用次數、風險/能力是否對齊你的直覺。
- Step C：改動某個小文件後重跑
  - 檢查：對應目錄哈希與 `digest.json` 是否被刷新；父級摘要是否受影響。

## 五、模塊對照速覽
- `src/__main__.py`：CLI 與展示層，掌控流程與可視化輸出。
- `src/config.py`：配置合併與模板導出。
- `src/traverser.py`：掃描與過濾策略、葉子判定、文件信息收集。
- `src/ai_client.py`：提示構建、CLI 調用、JSON 解析、供應商抽象。
- `src/analyzer.py`：整體調度、緩存優先、錯誤韌性與統計。
- `src/aggregator.py`：父級聚合規則與置信度。
- `src/cache.py`：目錄級緩存與清理。

## 六、常見擴展
- 新 AI 供應商：按 `BaseAIClient` 實作，並在 `AIClientFactory` 增加分支。
- 自定義提示詞：修改 `config/prompt.txt`，保留 JSON 輸出約束。
- 分析範圍：調整 `include_extensions` 與忽略規則；必要時擴展 `traverser` 的文本判定。

## 七、參考資料
- `README.md`：安裝與使用示例
- `docs/PRD.md`：產品需求與場景
- `AGENTS.md`：貢獻指南與風格規範
