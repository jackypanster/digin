# Digin - 代码考古工具产品需求文档

## 1. 项目概述

### 1.1 背景
面对遗留代码库或陌生项目，开发者需要快速理解代码结构和功能意图。传统的代码阅读方式效率低下，缺乏系统性的理解方法。

### 1.2 目标
构建一个自动化工具，利用 AI 能力对代码库进行"考古式"分析，生成结构化的项目理解文档，帮助开发者快速掌握项目全貌。

### 1.3 核心理念
- **分而治之**：将大型项目拆解为可管理的小单元
- **自底向上**：从叶子目录开始，逐层构建理解
- **结构化输出**：统一的 JSON 格式便于程序化处理
- **增量分析**：通过缓存避免重复分析，节省成本

## 2. 功能需求

### 2.1 核心功能

#### 2.1.1 目录遍历与分析
- 自动识别源代码目录结构
- 从叶子节点开始，逐层向上分析
- 智能忽略无关目录（node_modules、.git、dist 等）
- 支持配置自定义忽略规则

#### 2.1.2 AI 驱动的代码理解
- 调用 AI CLI（claude/gemini）分析每个目录
- 生成标准化的 JSON 摘要（digest.json）
- 包含目录功能、接口、依赖等关键信息
- 父目录整合子目录摘要，形成层次化理解

#### 2.1.3 缓存机制
- 基于文件内容生成 hash
- 内容未变化时跳过重复分析
- 缓存文件存储在各自目录（.hash）
- 支持强制刷新模式

#### 2.1.4 错误处理
- API 调用失败不阻塞整体流程
- 记录错误日志（errors.log）
- 提供错误统计和分析

### 2.2 命令行接口

#### 2.2.1 基本命令
```bash
# 分析当前目录
digin

# 分析指定目录
digin /path/to/project

# 使用不同的 AI 提供商
digin /path/to/project --provider gemini

# 强制刷新缓存
digin /path/to/project --force

# 详细输出
digin /path/to/project --verbose

# 配置文件
digin /path/to/project --config custom.json
```

### 2.3 输出格式

#### 2.3.1 digest.json Schema
```json
{
  "name": "string - 目录名称",
  "path": "string - 相对于根目录的路径",
  "kind": "service|lib|ui|infra|config|test|docs|unknown - 目录类型",
  "summary": "string - 功能概述（人话描述）",
  "capabilities": ["string - 核心能力列表"],
  "public_interfaces": {
    "http": [{"method": "string", "path": "string", "handler": "string", "evidence": ["string"]}],
    "rpc": [{"service": "string", "method": "string", "evidence": ["string"]}],
    "cli": [{"cmd": "string", "evidence": ["string"]}],
    "api": [{"function": "string", "signature": "string", "evidence": ["string"]}]
  },
  "dependencies": {
    "internal": ["string - 内部依赖"],
    "external": ["string - 外部依赖"]
  },
  "configuration": {
    "env": ["string - 环境变量"],
    "files": ["string - 配置文件"]
  },
  "risks": ["string - 潜在风险"],
  "evidence": {
    "files": ["string - 证据文件列表"]
  },
  "confidence": "number - 分析置信度 0-100",
  "analyzed_at": "string - 分析时间 ISO 8601",
  "analyzer_version": "string - 工具版本"
}
```

### 2.4 配置管理

#### 2.4.1 配置系统
默认配置定义在 `config/default.json` 中，包含所有默认设置。用户可通过 CLI 参数覆盖特定配置：

```bash
# 使用不同的 AI 提供商
digin . --provider claude

# 强制重新分析
digin . --force

# 详细输出
digin . --verbose
```

## 3. 技术方案

### 3.1 技术栈
- **语言**: Python 3.8+
- **包管理**: uv
- **CLI框架**: Click
- **JSON处理**: Standard json library
- **Hash计算**: hashlib
- **并发**: asyncio (future)

### 3.2 项目结构
```
digin/
├── README.md
├── PRD.md
├── pyproject.toml           # uv 配置
├── .gitignore
├── src/                     # 源代码
│   ├── __init__.py
│   ├── __main__.py         # CLI 入口
│   ├── analyzer.py         # 核心分析逻辑
│   ├── traverser.py        # 目录遍历
│   ├── ai_client.py        # AI API 封装
│   ├── cache.py            # 缓存管理
│   ├── aggregator.py       # 摘要聚合
│   └── config.py           # 配置管理
├── config/
│   ├── default.json        # 默认配置
│   └── prompt.txt          # 提示词模板
├── tests/                  # 测试
├── docs/                   # 文档
├── scripts/                # 脚本
└── examples/               # 示例
```

### 3.3 核心组件

#### 3.3.1 目录遍历器（DirectoryTraverser）
```python
class DirectoryTraverser:
    def find_leaf_directories(self, root_path: str) -> List[Path]
    def should_ignore(self, path: Path) -> bool
    def get_traversal_order(self, root_path: str) -> List[Path]
```

#### 3.3.2 AI 分析器（AIAnalyzer）
```python
class AIAnalyzer:
    def __init__(self, provider: str = "claude")
    def analyze_directory(self, path: Path) -> Dict
    def build_prompt(self, path: Path, children_digests: List[Dict]) -> str
    def parse_response(self, response: str) -> Dict
```

#### 3.3.3 缓存管理器（CacheManager）
```python
class CacheManager:
    def calculate_hash(self, path: Path) -> str
    def is_cache_valid(self, path: Path) -> bool
    def save_cache(self, path: Path, digest: Dict) -> None
    def load_cache(self, path: Path) -> Optional[Dict]
```

#### 3.3.4 摘要聚合器（SummaryAggregator）
```python
class SummaryAggregator:
    def aggregate_digests(self, path: Path, children: List[Dict]) -> Dict
    def merge_capabilities(self, digests: List[Dict]) -> List[str]
    def merge_dependencies(self, digests: List[Dict]) -> Dict
```

### 3.4 工作流程

```
1. 初始化
   ├── 加载配置文件
   ├── 验证 AI CLI 可用性
   └── 创建工作目录

2. 目录扫描
   ├── 递归遍历目标目录
   ├── 应用忽略规则
   ├── 识别叶子目录
   └── 构建处理队列

3. 叶子目录分析
   ├── 检查缓存有效性
   ├── 收集目录内容
   ├── 构建分析提示词
   ├── 调用 AI API
   ├── 解析 JSON 响应
   └── 保存 digest.json

4. 逐层聚合
   ├── 从叶子向根遍历
   ├── 加载子目录 digest.json
   ├── 分析当前层直接文件
   ├── 聚合子目录信息
   ├── 生成当前层 digest.json
   └── 更新缓存

5. 完成
   ├── 生成分析报告
   ├── 输出统计信息
   └── 清理临时文件
```

### 3.5 提示词模板

```
你是严谨的软件考古助手。分析当前目录，输出标准 JSON。

## 分析上下文

**目录路径**: {directory_path}
**直接文件**: 
{file_list}

**关键代码片段**:
{code_snippets}

**子目录摘要**:
{children_digests}

## 输出要求

1. **只输出 JSON**，无任何额外文字或解释
2. **基于证据推断**，不确定的字段直接省略
3. **用通俗语言**描述功能意图，避免技术术语堆砌
4. **confidence 字段**反映分析的确定程度（0-100）

## JSON Schema

{json_schema}

## 分析规则

- **kind 分类**：根据目录内容和结构判断类型
- **capabilities**：列出该目录提供的核心功能
- **public_interfaces**：识别对外暴露的接口
- **dependencies**：区分内部和外部依赖
- **risks**：识别潜在的技术风险或问题
- **evidence**：列出支持结论的具体文件

请开始分析：
```

## 4. 非功能需求

### 4.1 性能要求
- 单个目录分析时间 < 30秒
- 支持中断后续传
- 内存占用 < 500MB
- 支持 1万+ 文件的项目

### 4.2 可用性要求
- 清晰的进度提示
- 友好的错误信息
- 支持 verbose 模式
- 彩色输出支持

### 4.3 成本控制
- 通过缓存减少 API 调用
- 单线程执行避免限流
- 提供 dry-run 模式
- Token 使用统计

### 4.4 兼容性
- 支持 macOS、Linux、Windows
- 兼容 Python 3.8+
- 支持 claude 和 gemini CLI

## 5. 使用场景

### 5.1 新项目上手
```bash
# 快速理解项目结构
digin /path/to/new/project
```

### 5.2 代码审查准备
```bash
# 生成项目摘要用于 PR 审查
digin --verbose --output summary.md
```

### 5.3 技术债务分析
```bash
# 识别风险点
digin --focus risks
```

### 5.4 文档生成
```bash
# 生成架构文档基础材料
digin --format markdown --output docs/
```

## 6. 交付计划

### 6.1 第一阶段（MVP - 2周）
- [x] 项目结构搭建
- [x] 基础文档（README、PRD）
- [ ] 核心分析逻辑
- [ ] Claude CLI 集成
- [ ] 基础缓存机制
- [ ] 命令行界面

### 6.2 第二阶段（增强 - 2周）
- [ ] Gemini CLI 支持
- [ ] 配置文件系统
- [ ] 错误处理优化
- [ ] 单元测试覆盖
- [ ] 性能优化

### 6.3 第三阶段（完善 - 2周）
- [ ] 可视化输出
- [ ] 增量更新
- [ ] 并发处理
- [ ] 详细文档
- [ ] 发布准备

## 7. 成功标准

### 7.1 技术指标
- 准确识别 90% 以上的模块功能
- API 成本降低 60%（通过缓存）
- 分析速度 < 1秒/目录（缓存命中）
- 零配置启动成功率 95%

### 7.2 用户价值
- 新人上手时间减少 70%
- 代码理解效率提升 5 倍
- 生成的文档可直接用于技术决策
- 支持主流编程语言项目

### 7.3 质量标准
- 单元测试覆盖率 > 80%
- 集成测试覆盖核心流程
- 错误处理覆盖异常情况
- 用户文档完整清晰

## 8. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|-----|------|------|------|
| API 成本过高 | 中 | 高 | 缓存机制、可选模型、token 限制 |
| AI 理解偏差 | 高 | 中 | 置信度标记、人工审核流程 |
| 大型项目超时 | 中 | 中 | 分批处理、断点续传、并发优化 |
| CLI 工具不兼容 | 低 | 高 | 多提供商支持、版本检查 |
| 隐私安全问题 | 低 | 高 | 本地处理、敏感信息过滤 |

## 9. 监控指标

### 9.1 技术指标
- API 调用次数和成本
- 缓存命中率
- 平均分析时间
- 错误率统计

### 9.2 质量指标
- 用户满意度评分
- 功能识别准确率
- 文档有用性评分
- Bug 报告数量

## 10. 后续规划

### 短期（1-3 月）
- IDE 插件开发
- Web 可视化界面
- 团队协作功能
- 更多语言支持

### 中期（3-6 月）
- 项目对比功能
- 代码质量评分
- 自动文档生成
- CI/CD 集成

### 长期（6-12 月）
- 知识图谱构建
- 代码重构建议
- 技术栈升级建议
- 开源社区生态

## 11. 附录

### 11.1 术语表
- **叶子目录**：不包含任何子目录的目录
- **代码考古**：对遗留代码的系统性分析和理解过程
- **摘要文件**：包含目录分析结果的 digest.json 文件
- **置信度**：AI 对分析结果确信程度的量化指标

### 11.2 参考资料
- [Claude CLI Documentation](https://docs.anthropic.com/claude/reference/cli)
- [Gemini CLI Documentation](https://ai.google.dev/gemini-api/docs/cli)
- [UV Package Manager](https://github.com/astral-sh/uv)
- [Click CLI Framework](https://click.palletsprojects.com/)

### 11.3 相关项目
- SourceGraph - 代码搜索和导航
- GitHub Copilot - AI 代码理解
- CodeQL - 静态代码分析
- tree-sitter - 语法解析器