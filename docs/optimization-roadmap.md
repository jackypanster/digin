# Digin 优化路线图

> 让程序员快速上手陌生项目的优化迭代计划

## 当前状态总结

Digin 已经实现了基础的 AI 驱动代码分析功能，采用自底向上的策略生成项目摘要和对话式引导。当前版本能够有效支持标准化、模块化的项目，但在大文件处理、配置文件理解、文档一致性等方面仍有提升空间。

**核心优势：**
- ✅ 自底向上分析策略
- ✅ AI 驱动的语义理解
- ✅ 对话式叙事引导
- ✅ 项目地图与学习路径
- ✅ 智能缓存机制

**当前限制：**
- ⚠️ 大文件（>100KB）覆盖不足
- ⚠️ 配置文件语义理解较弱
- ⚠️ 缺少"快速开始"指南
- ⚠️ 未充分利用 AI 上下文容量

---

## Phase 1: 核心参数优化 ✅ (已完成)

**目标：** 提高文件覆盖率，充分利用 Gemini 2M token 上下文窗口

### 技术背景

```
Gemini 2.5 Pro 上下文窗口：200万 tokens (2M)
代码 token 密度：≈ 350 tokens/KB
理论容量：200万 ÷ 350 ≈ 5714 KB ≈ 5.6 MB

优化前使用：20 files × 50KB = 1 MB (≈18% 容量)
优化后使用：30 files × 150KB ≈ 4.5 MB (≈79% 容量)

📊 Gemini 2.5 Pro 的优势：
- 上下文容量是 1.5 Pro 的 2倍
- 可以处理更多文件或更大的文件
- 为未来智能采样策略预留空间
```

### 实施内容

#### 1. 新增 `AnalysisLimits` 配置类

**文件：** `src/config.py`

```python
@dataclass
class AnalysisLimits:
    """Analysis limits for AI processing.

    Controls how much content is sent to AI for analysis per directory.
    Optimized for Gemini 1.5 Pro's 1M token context window.
    """
    max_analysis_file_size: str = "200KB"  # 从 100KB 提升
    max_content_per_file: str = "150KB"     # 从 50KB 提升
    max_files_per_request: int = 30         # 从 20 提升
```

#### 2. 更新配置文件

**文件：** `config/default.json`

```json
{
  "analysis_limits": {
    "max_analysis_file_size": "200KB",
    "max_content_per_file": "150KB",
    "max_files_per_request": 30
  }
}
```

#### 3. 消除硬编码

**修改文件：**
- `src/traverser.py` - 使用 `settings.analysis_limits` 替代硬编码
- `src/ai_client.py` - 从配置读取 `max_files_per_request`

### 预期效果

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 单文件分析上限 | 100KB | 200KB | **+100%** |
| 单文件读取上限 | 50KB | 150KB | **+200%** |
| 每次文件数量 | 20 | 30 | **+50%** |
| 文件覆盖率 | 60-70% | 85-90% | **+25%** |

**典型收益：**
- 80% 的文件 < 20KB → 完全覆盖
- 15% 的文件 20-150KB → 大部分覆盖
- 5% 的文件 > 150KB → 部分覆盖（vs 之前跳过）

---

## Phase 2: 智能内容采样 🔄 (规划中)

**目标：** 在保证信息质量的前提下，处理更大的文件和目录

### 2.1 分层采样策略

**问题：** 当前遇到大文件（>200KB）仍会跳过，丢失关键信息

**解决方案：** 按文件重要性分层处理

```python
def collect_content_with_priority(files, total_budget=4*1024*1024):
    """智能采样：关键文件读完整，普通文件按优先级

    Gemini 2.5 Pro allows up to 5.6MB content, use 4MB for safety
    """

    # 第1层：配置/文档文件（读完整，不受大小限制）
    tier1_patterns = [
        "README*", "package.json", "requirements.txt",
        "Cargo.toml", "pom.xml", "build.gradle",
        "Dockerfile", "docker-compose.yml"
    ]

    # 第2层：小文件（<50KB，读完整）
    tier2 = [f for f in files if f.size < 50*1024]

    # 第3层：中文件（50-150KB，读100KB）
    tier3 = [f for f in files if 50*1024 <= f.size <= 150*1024]

    # 第4层：大文件（150-300KB，智能采样）
    tier4 = [f for f in files if 150*1024 < f.size <= 300*1024]

    # 按优先级分配预算...
```

### 2.2 大文件智能采样

**策略：** 头部 + 尾部 + 关键段

```python
def smart_sample(file_path, max_bytes):
    """对大文件进行智能采样"""
    sections = []

    # 1. 文件开头（imports, 类定义，函数签名）
    head_size = max_bytes // 2
    sections.append(("HEAD", read_head(file_path, head_size)))

    # 2. 文件结尾（main 函数、导出语句）
    tail_size = max_bytes // 4
    sections.append(("TAIL", read_tail(file_path, tail_size)))

    # 3. 关键段（包含装饰器、类定义的代码段）
    remaining = max_bytes - head_size - tail_size
    key_defs = extract_key_definitions(file_path)
    sections.append(("KEY_DEFS", key_defs[:remaining]))

    return combine_sections(sections)
```

### 2.3 动态预算管理

```python
def enforce_token_budget(content_map, max_tokens=1_600_000):
    """确保不超过 AI token 限制

    Gemini 2.5 Pro: 2M tokens total, use 80% (1.6M) for input
    """
    total_chars = sum(len(content) for content in content_map.values())
    estimated_tokens = total_chars * 0.35  # 保守估计

    if estimated_tokens > max_tokens:
        # 按优先级裁剪，保留最重要的文件
        return trim_by_priority(content_map, max_tokens)

    return content_map
```

### 实施计划

**时间估算：** 2 周

**文件改动：**
- `src/traverser.py` - 添加分层采样逻辑
- `src/file_sampler.py` - 新建，实现智能采样算法
- `src/ai_client.py` - 添加 token 预算管理

**测试重点：**
- 大型单体项目（legacy codebase）
- 包含自动生成代码的项目
- Token 使用量监控

---

## Phase 3: 配置文件专项解析 📋 (规划中)

**目标：** 自动提取"快速开始"信息，解决文档缺失问题

### 3.1 配置文件解析器

**支持格式：**
- `package.json` - Node.js 项目
- `requirements.txt` / `pyproject.toml` - Python 项目
- `Cargo.toml` - Rust 项目
- `pom.xml` / `build.gradle` - Java 项目
- `docker-compose.yml` - 服务架构
- `Makefile` - 构建命令

**提取信息：**
```python
class ConfigParser:
    def parse_package_json(content):
        """提取 npm scripts, dependencies, entry point"""
        return {
            "scripts": {
                "start": "node server.js",
                "test": "jest",
                "build": "webpack"
            },
            "dependencies": ["express", "react", "lodash"],
            "entry_point": "server.js"
        }

    def parse_docker_compose(content):
        """提取服务、端口、依赖关系"""
        return {
            "services": {
                "web": {"image": "nginx", "ports": ["80:80"]},
                "db": {"image": "postgres", "ports": ["5432:5432"]}
            },
            "architecture": "microservices"
        }
```

### 3.2 增强 Prompt

```python
def build_enhanced_prompt(directory_info, config_summary):
    """在原有 prompt 基础上增加配置信息"""

    additional_context = f"""
## 配置信息分析

**运行命令**:
{config_summary.get('scripts', '未发现')}

**依赖包**:
{', '.join(config_summary.get('dependencies', []))}

**服务架构**:
{config_summary.get('services', {})}

**环境要求**:
{config_summary.get('requirements', [])}

请结合配置信息理解代码的运行方式和依赖关系。
在 digest.json 中生成 "quick_start" 字段。
"""

    return original_prompt + additional_context
```

### 3.3 生成"快速开始"指南

**输出示例：**

```json
{
  "quick_start": {
    "setup_commands": [
      "npm install",
      "cp .env.example .env"
    ],
    "run_commands": [
      "npm start  # 启动开发服务器",
      "npm test   # 运行测试"
    ],
    "required_tools": [
      {"name": "node", "version": ">=18.0.0"},
      {"name": "docker", "optional": true}
    ],
    "environment_variables": [
      {"name": "DATABASE_URL", "required": true},
      {"name": "API_KEY", "required": false}
    ]
  }
}
```

### 实施计划

**时间估算：** 2-3 周

**文件改动：**
- `src/config_parser.py` - 新建，各类配置文件解析器
- `src/ai_client.py` - 增强 prompt 包含配置信息
- `config/prompt.txt` - 添加"快速开始"生成指引

**测试重点：**
- 各种语言/框架项目
- 无文档项目的快速启动
- 配置提取准确性

---

## Phase 4: 文档增强与一致性 📖 (规划中)

**目标：** 检测文档失真，补充缺失文档

### 4.1 README 优先处理

```python
def collect_directory_info_enhanced(directory):
    """README 不受大小限制，优先完整读取"""

    readme_content = None
    for item in directory.iterdir():
        if item.name.upper().startswith("README"):
            # README 总是完整读取
            with open(item) as f:
                readme_content = f.read()

    return {
        "files": files,
        "readme": readme_content,  # 单独提供，高优先级
        # ...
    }
```

### 4.2 文档与代码一致性检查

```python
def check_doc_code_consistency(readme_content, code_digests):
    """检查文档声称的功能 vs 实际代码能力"""

    # 从 README 提取声称的功能
    claimed_features = extract_features_from_readme(readme_content)
    # 例如："支持用户认证"、"提供 RESTful API"

    # 从代码提取实际功能
    actual_capabilities = [
        cap for digest in code_digests
        for cap in digest.get("capabilities", [])
    ]

    # 对比分析
    issues = []
    for feature in claimed_features:
        if not any(similar(feature, cap) for cap in actual_capabilities):
            issues.append({
                "type": "missing_in_code",
                "claim": feature,
                "severity": "warning"
            })

    undocumented = [
        cap for cap in actual_capabilities
        if not any(similar(cap, f) for f in claimed_features)
    ]

    return {
        "consistency_score": calculate_similarity(...),
        "missing_in_code": issues,
        "undocumented_features": undocumented,
        "documentation_quality": "good" | "outdated" | "missing"
    }
```

### 4.3 自动补充缺失文档

**在 digest.json 中添加：**

```json
{
  "documentation_analysis": {
    "readme_exists": false,
    "documentation_quality": "missing",
    "suggested_readme": {
      "title": "Authentication Service",
      "description": "基于代码分析，这个模块提供用户认证功能，包括登录、注册、令牌管理。",
      "quick_start": "...",
      "api_reference": [...]
    }
  }
}
```

### 实施计划

**时间估算：** 1-2 周

**文件改动：**
- `src/doc_analyzer.py` - 新建，文档分析模块
- `src/aggregator.py` - 添加文档一致性检查
- `config/prompt.txt` - 添加文档生成指引

---

## Phase 5: Web 界面增强 🌐 (规划中)

**目标：** 提升可视化效果和交互体验

### 5.1 依赖关系图

```javascript
// web/static/dependency-graph.js
function renderDependencyGraph(digests) {
    const nodes = digests.map(d => ({
        id: d.path,
        label: d.name,
        group: d.kind
    }));

    const edges = [];
    digests.forEach(d => {
        (d.dependencies?.internal || []).forEach(dep => {
            edges.push({from: d.path, to: dep});
        });
    });

    // 使用 D3.js 或 Cytoscape.js 渲染
    renderGraph(nodes, edges);
}
```

### 5.2 智能搜索

```javascript
// 全局搜索 + 多维度过滤
function searchCodebase(query) {
    const results = digests.filter(d => {
        return d.summary.includes(query) ||
               d.capabilities.some(c => c.includes(query)) ||
               fuzzyMatch(d.name, query);
    });

    // 按相关性排序
    return results.sort((a, b) =>
        relevanceScore(b, query) - relevanceScore(a, query)
    );
}
```

### 5.3 "快速开始"卡片

在 Web 界面首页显示：

```html
<div class="quick-start-card">
  <h3>🚀 快速开始</h3>
  <ol>
    <li><code>npm install</code></li>
    <li><code>npm start</code></li>
  </ol>
  <div class="requirements">
    <span>需要：Node.js ≥18</span>
  </div>
</div>
```

### 实施计划

**时间估算：** 2-3 周

**文件改动：**
- `web/static/app.js` - 添加搜索、图形渲染
- `web/static/style.css` - 新增样式
- `web/server.py` - 添加搜索 API

---

## 成功指标

### 量化指标

| 指标 | 当前 | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|------|---------|---------|---------|---------|
| 文件覆盖率 | 60% | **85%** | 90% | 90% | 95% |
| 大文件处理（>100KB） | 跳过 | 200KB | **300KB** | 300KB | 300KB |
| 配置文件识别率 | 50% | 50% | 50% | **95%** | 95% |
| "快速开始"生成率 | 0% | 0% | 0% | **80%** | 90% |
| 文档一致性检测 | 无 | 无 | 无 | 无 | **有** |

### 定性效果

**新同事上手时间：**
- 当前：2-3 天摸索
- Phase 1：1-2 天（更多代码覆盖）
- Phase 3：**半天**（有"快速开始"指南）

**文档缺失项目：**
- 当前：需要自己摸索
- Phase 3：**AI 自动生成快速开始指南**
- Phase 4：**检测文档失真，提示潜在问题**

---

## 风险与挑战

### 技术风险

1. **Token 超限风险**
   - 缓解：实施渐进式回退策略
   - 监控：添加 token 使用量日志

2. **AI 幻觉问题**
   - 缓解：结合静态分析校准 AI 输出
   - 验证：增加置信度评分机制

3. **性能下降**
   - 缓解：保持缓存机制，增量更新
   - 优化：并行处理、异步分析

### 实施挑战

1. **多语言支持**
   - 不同语言的配置文件格式各异
   - 需要逐步添加解析器

2. **向后兼容**
   - 新配置项需要有合理默认值
   - 旧版本 digest.json 需要兼容

3. **测试覆盖**
   - 需要收集多种类型项目作为测试用例
   - 真实 AI 调用测试成本较高

---

## 总结

### 核心理念

Digin 的目标不是成为**100% 精准的代码分析工具**，而是成为**让新人快速上手的智能导游**。

**类比说明：**
```
传统方式：给你一个城市，自己慢慢走
Digin方式：给你一张地图 + 导游讲解 + 推荐路线

地图可能不是100%准确（小巷可能画错）
但你能快速知道：
- 市中心在哪（核心模块）
- 主干道怎么走（关键依赖）
- 哪里值得先看（推荐路径）
- 怎么开始探索（快速开始）
```

### 迭代优先级

**短期（1个月）：**
- ✅ **Phase 1** - 已完成
- 🔄 **Phase 2** - 智能采样（提升覆盖率）

**中期（2-3个月）：**
- 📋 **Phase 3** - 配置解析（快速开始指南）
- 📖 **Phase 4** - 文档增强（一致性检查）

**长期（3-6个月）：**
- 🌐 **Phase 5** - Web 界面增强
- 🤖 **未来** - RAG 问答系统、自适应学习路径

### 持续改进

每个 Phase 完成后：
1. 收集用户反馈
2. 测试真实项目效果
3. 调整后续计划

**核心原则：** 保持简单、保持实用、保持迭代 🚀
