# Digin - AI 驱动的代码考古工具

> 🔍 深入挖掘代码库，理解项目全貌

## 简介

Digin 是一个利用 AI 能力自动分析代码库结构和功能的工具。它采用"分而治之"的策略，从叶子目录开始，逐层向上构建对整个项目的理解，最终生成结构化的项目摘要。

## 特性

- 🎯 **自底向上分析** - 从最小单元开始，逐层构建理解
- 🤖 **AI 驱动** - 利用 Claude/Gemini 理解代码意图
- 📊 **结构化输出** - 统一的 JSON 格式（digest.json）
- 💾 **智能缓存** - 避免重复分析，节省 API 成本
- 🚀 **简单易用** - 一行命令完成分析
- 🌐 **Web 可视化** - 现代化的图形界面展示分析结果

## 快速开始

### 安装

```bash
# 使用 uv 安装
uv pip install digin

# 或从源码安装
git clone https://github.com/yourusername/digin.git
cd digin
uv pip install -e .

# 安装 Web 界面依赖（可选）
uv sync --extra web
```

### 基本使用

```bash
# 分析当前目录
digin

# 分析指定目录
digin /path/to/project

# 使用 Claude（默认 Gemini）
digin /path/to/project --provider claude

# 强制刷新（忽略缓存）
digin /path/to/project --force
```

### Web 可视化界面

除了命令行输出，Digin 还提供了现代化的 Web 界面来展示分析结果：

```bash
# 1. 先分析项目
uv run python -m src /path/to/project

# 2. 启动 Web 界面
uv run python -m web /path/to/project

# 3. 打开浏览器访问
open http://localhost:8000
```

Web 界面特性：
- 📊 **现代卡片式设计** - 美观直观的信息展示
- 🔍 **交互式浏览** - 点击探索项目结构
- 📱 **响应式布局** - 支持桌面和移动设备
- 🎨 **可视化展示** - 项目摘要、功能、依赖关系一览无余

### 输出示例

每个目录生成 `digest.json`：

```json
{
  "name": "auth-service",
  "path": "services/auth",
  "kind": "service",
  "summary": "用户认证和授权服务，提供登录、注册、令牌管理功能",
  "capabilities": [
    "用户注册和登录",
    "JWT 令牌生成和验证",
    "权限管理"
  ],
  "public_interfaces": {
    "http": [
      {
        "method": "POST",
        "path": "/api/auth/login",
        "handler": "LoginHandler",
        "evidence": ["auth/handlers.py:45"]
      }
    ]
  },
  "dependencies": {
    "external": ["flask", "jwt", "bcrypt"],
    "internal": ["utils.crypto", "models.user"]
  },
  "confidence": 85
}
```

## 工作原理

1. **扫描目录** - 识别项目结构，找出叶子节点
2. **叶子分析** - 对每个叶子目录调用 AI 分析
3. **逐层聚合** - 父目录整合子目录摘要
4. **生成全景** - 根目录得到完整项目理解

```
project/
├── services/
│   ├── auth/           <- 叶子目录，生成 digest.json
│   │   ├── handlers.py
│   │   └── models.py
│   └── digest.json     <- 聚合子目录摘要
├── utils/
│   ├── crypto.py       <- 叶子目录，生成 digest.json
│   └── digest.json
└── digest.json         <- 根目录全景摘要
```

## 配置

默认配置在 `config/default.json` 中定义。可通过 CLI 参数临时调整设置：

```bash
# 使用 Claude 提供商
digin . --provider claude

# 强制重新分析（忽略缓存）
digin . --force

# 详细输出
digin . --verbose
```

## 系统要求

- Python 3.8+
- Claude CLI 或 Gemini CLI
- uv (Python 包管理器)

## 项目结构

```
digin/
├── README.md
├── CLAUDE.md           # 开发指南
├── pyproject.toml
├── src/                # 核心分析器
│   ├── __init__.py
│   ├── __main__.py     # CLI 入口
│   ├── analyzer.py     # 核心分析逻辑
│   ├── traverser.py    # 目录遍历
│   ├── ai_client.py    # AI API 封装
│   ├── cache.py        # 缓存管理
│   └── aggregator.py   # 摘要聚合
├── web/                # Web 可视化模块
│   ├── __init__.py
│   ├── __main__.py     # Web 服务器入口
│   ├── server.py       # FastAPI 服务器
│   └── static/         # 前端资源
│       ├── index.html  # 主页面
│       ├── style.css   # 样式文件
│       └── app.js      # 交互逻辑
├── config/
│   ├── default.json    # 默认配置
│   └── prompt.txt      # 提示词模板
├── tests/              # 测试代码
├── docs/               # 文档
└── scripts/            # 脚本工具
```

## 开发

```bash
# 克隆仓库
git clone https://github.com/yourusername/digin.git
cd digin

# 安装核心依赖
uv sync

# 安装 Web 依赖（如果需要开发 Web 界面）
uv sync --extra web

# 运行测试
uv run pytest

# 开发模式安装
uv pip install -e .

# 运行分析器
python -m src /path/to/analyze

# 启动 Web 界面（可选）
python -m web /path/to/analyze
```

## 使用场景

### 1. 新项目上手
快速理解陌生项目的架构和功能

### 2. 代码审查
生成项目摘要，便于 Code Review

### 3. 技术债务评估
识别项目中的风险点和改进机会

### 4. 文档生成
自动生成项目文档的基础材料

## 路线图

- [x] MVP - 基础分析功能
- [x] Web 界面 - 现代化可视化展示
- [ ] 目录树导航 - 交互式项目结构浏览
- [ ] 增量更新 - 只分析变更部分
- [ ] 多语言支持 - 更好的代码理解
- [ ] 团队协作 - 共享分析结果
- [ ] 主题切换 - 暗色/亮色模式

## 贡献

欢迎提交 Issue 和 Pull Request！

### 开发指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可

MIT License - 详见 [LICENSE](LICENSE) 文件

## 致谢

- [Claude](https://claude.ai) - 提供强大的代码理解能力
- [Gemini](https://gemini.google.com) - 备选 AI 分析引擎
- [uv](https://github.com/astral-sh/uv) - 现代 Python 包管理器