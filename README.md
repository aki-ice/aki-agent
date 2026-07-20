# AKI Agent Workbench

AKI Agent Workbench 是一个基于 PyQt6 的本地 AI Agent 桌面工作台。项目使用 OpenAI-compatible API 调用 DeepSeek 或其它兼容模型，内置聊天、模型/API 管理、Prompt 管理、插件系统、网页搜索、文件读写编辑和多步骤工具调用能力。
同时支持 RAG 检索增强生成、长期记忆、多 Agent 团队协作、每日对话摘要等进阶能力。

## 主要特性

- PyQt6 桌面 GUI 工作台
- 淡白蓝现代化界面主题
- **Dashboard** 页面：每日对话次数、Token 用量、活跃度概览
- **Chat** 页面：流式对话、工具调用状态展示、多会话管理、会话导出
- **Model** 页面：自定义 Provider / Model / Base URL / API Key，SQLite 本地持久化
- **Memory** 页面：每日对话自动摘要，支持按日期浏览和刷新
- **Team** 页面：多 Agent 协作（sequential / parallel / debate），可视化团队配置
- **SkillsTools** 页面：内置/外部 skill 和 tool 的启用、导入、导出管理
- **Tokens** 页面：输入/输出 Token 统计，最近 365 天活跃 Heatmap 热力图
- 左侧 Prompt 提示词管理
  - 内置 Prompt 预设
  - 自定义系统提示词
  - 支持从 `.md` / `.txt` 导入 Prompt
  - 支持保存 Prompt 到本地 `.env`
- Skills & Tools 插件管理
  - 内置 skill / tool 启用禁用
  - ZIP 导入 skill / tool
  - 外部 tool 需信任后执行
- 内置工具调用能力
  - 网页搜索
  - 网页正文抓取
  - 热榜/热搜抓取
  - 文件读取、写入、编辑、删除、复制、移动
  - 目录创建和目录列表
  - 计算器和日期时间
- 支持"搜索网页内容 -> 总结 -> 生成本地 Markdown 文档"等多步骤任务
- **RAG** 检索增强生成：文档摄取、向量存储、语义检索
- **长期记忆**（Long-term Memory）：SQLite + Embedding 自动摘要存储
- **Team / Sub-agent** 多 Agent 团队协作能力
- 内置 Skills：`python_expert`（Python 专家）、`code_reviewer`（代码审查）
- Windows 打包配置（PyInstaller + Inno Setup）

## 内置工具列表

当前内置工具包括：

| 工具名 | 说明 |
| --- | --- |
| `calculator` | 计算数学表达式 |
| `datetime` | 获取当前时间或计算日期偏移 |
| `web_search` | 网页搜索，优先使用 Tavily，未配置时使用公共搜索回退 |
| `web_fetch` | 抓取网页文本内容 |
| `hot_news` | 抓取微博、百度、今日热榜等热搜榜单 |
| `read_file` | 读取文本文件 |
| `list_directory` | 列出目录内容 |
| `write_file` | 创建、覆盖或追加写入文本文件 |
| `edit_file` | 替换、插入、删除、追加、按行范围编辑文本文件 |
| `create_directory` | 创建目录 |
| `delete_path` | 删除文件或目录 |
| `copy_path` | 复制文件或目录 |
| `move_path` | 移动或重命名文件/目录 |
| `sub_agent` | 委派任务给内置或技能驱动的子 Agent |

文件类工具支持相对路径和绝对路径。请谨慎启用 `write_file`、`edit_file`、`delete_path`、`move_path` 等具备修改能力的工具。

## 安装

建议使用虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 配置环境变量

复制示例配置：

```powershell
copy .env.example .env
```

然后编辑 `.env`：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
TAVILY_API_KEY=your_tavily_api_key_here
```

说明：

- `DEEPSEEK_API_KEY`：必填，用于调用 DeepSeek 或兼容服务。
- `DEEPSEEK_BASE_URL`：默认 `https://api.deepseek.com`。
- `DEEPSEEK_MODEL`：默认模型名。
- `TAVILY_API_KEY`：可选。配置后 `web_search` 会优先使用 Tavily。

不要把真实 `.env` 上传到 GitHub。项目 `.gitignore` 已默认忽略 `.env`。

## 运行 GUI 工作台

```bash
python gui_app.py
```

启动后可以在 GUI 中：

1. 进入 `Model` 页面添加或选择模型/API 配置。
2. 在左侧 Prompt 区选择预设或输入自定义系统提示词。
3. 在 `SkillsTools` 页面启用需要的工具。
4. 在 `Chat` 页面进行对话和工具任务。

## 运行命令行 Agent

单次提问：

```bash
python main.py "Hello"
```

多轮对话：

```bash
python main.py --interactive
```

关闭 thinking 参数：

```bash
python main.py --no-thinking "Hello"
```

### CLI 完整参数

| 参数 | 说明 |
| --- | --- |
| `--system` | 自定义系统提示词 |
| `--model` | 指定模型名称 |
| `--no-thinking` | 关闭 reasoning/thinking |
| `--interactive` / `-i` | 交互式多轮对话模式 |
| `--no-tools` | 禁用内置工具调用 |
| `--max-tool-rounds` | 最大工具调用轮数（默认 5） |
| `--workspace` | 文件工具的工作区根目录（默认当前目录） |
| `--rag` | 启用 RAG 检索增强生成 |
| `--rag-ingest PATH` | 预先摄入文件或目录到 RAG 存储 |
| `--rag-top-k` | RAG 检索片段数（默认 5） |
| `--rag-store` | RAG 向量存储路径（默认 rag_store.pkl） |
| `--long-term-memory` | 启用长期记忆 |
| `--memory-db` | 长期记忆数据库路径（默认 memory.db） |
| `--skills-dir` | Skill 文件所在目录 |
| `--team` | 启用团队协作模式 |
| `--team-mode` | 协作模式：sequential / parallel / debate |
| `--team-config` | 团队成员配置 JSON 文件路径 |
| `--team-rounds` | debate 模式辩论轮数（默认 2） |

## 常见任务示例

### 搜索网页并生成 Markdown 文档

```text
请先搜索 LOL 诺手 德莱厄斯 的资料，再整理成 Markdown 文档，并写入 D:\g\darius.md
```

Agent 应按以下流程执行：

```text
web_search / web_fetch -> 整理 Markdown -> write_file
```

### 创建文件

```text
在 D:\g\hello.txt 创建一个文件，内容是 hello world
```

### 编辑文件

```text
把 D:\g\hello.txt 里的 hello 替换成 你好
```

### 复制或移动文件

```text
把 D:\g\hello.txt 复制到 D:\g\backup\hello.txt
```

```text
把 D:\g\hello.txt 重命名为 D:\g\intro.txt
```

## RAG 检索增强生成

RAG 模块支持将本地文档摄入向量存储，在对话时自动检索相关上下文注入提示词。支持 Hash Embedding（零依赖）和 Sentence Transformer Embedding（语义级检索）。

### CLI 启用 RAG

```bash
# 启用 RAG 并预先摄入文件/目录
python main.py --rag --rag-ingest D:\docs "请总结这些文档的内容"

# 指定 RAG 检索数量和存储路径
python main.py --rag --rag-top-k 10 --rag-store my_store.pkl "问题"
```

### Python API 使用

```python
from deepseek_agent import DeepSeekAgent

agent = DeepSeekAgent(enable_rag=True)
agent.rag_ingest_file("doc.txt")             # 摄入单个文件
agent.rag_ingest_directory("docs/")          # 摄入目录
agent.rag_ingest_text("内容...", title="标题")  # 摄入文本
results = agent.rag_search("关键词", top_k=5)  # 语义搜索
```

## 长期记忆（Long-term Memory）

基于 SQLite 和可选的 Embedding 向量检索，自动在对话中摘要并存储重要信息。

```bash
# 启用长期记忆
python main.py --long-term-memory --interactive

# 自定义记忆数据库路径
python main.py --long-term-memory --memory-db my_memory.db --interactive
```

在 GUI 的 **Memory** 页面中，系统会根据每日对话自动生成摘要，可按日期浏览和管理。

## Skills & Tools 插件

GUI 中的 `SkillsTools` 页面支持：

- 启用/禁用内置 skills
- 启用/禁用内置 tools
- 从 ZIP 导入新的 skill 或 tool
- 查看插件详情
- 导出插件配置
- 外部 tool 需要手动点击"信任"后才能启用执行

### 内置 Skills

| 名称 | 说明 |
| --- | --- |
| `python_expert` | Python 专家，精通 Python 3.10+ 特性、类型提示、设计模式和性能优化 |
| `code_reviewer` | 代码审查专家，发现 Bug、安全问题和性能瓶颈，提供改进建议 |

### Skill ZIP 结构

```text
my_skill.zip
└── my_skill/
    ├── manifest.json
    └── skill.yaml
```

`manifest.json` 示例：

```json
{
  "id": "my_skill",
  "type": "skill",
  "name": "My Skill",
  "version": "1.0.0",
  "description": "自定义技能",
  "entry": "skill.yaml"
}
```

### Tool ZIP 结构

```text
my_tool.zip
└── my_tool/
    ├── manifest.json
    └── tool.py
```

`manifest.json` 示例：

```json
{
  "id": "my_tool",
  "type": "tool",
  "name": "My Tool",
  "version": "1.0.0",
  "description": "自定义工具",
  "entry": "tool.py"
}
```

`tool.py` 需要定义 `Tool` 类或 `create_tool()` 函数，并返回 `BaseTool` 实例：

```python
from typing import Any
from deepseek_agent.tools import BaseTool, ToolDefinition, ToolParameter


class Tool(BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="hello_tool",
            description="Return a greeting.",
            parameters=[ToolParameter("name", "string", "Name to greet")],
        )

    def execute(self, name: str = "World", **_: Any) -> str:
        return f"Hello, {name}!"
```

## Team 团队协作

支持多个 AI Agent 以 **sequential**（顺序执行）、**parallel**（并行执行）或 **debate**（辩论）模式协作完成任务。

### CLI 团队模式

```bash
# 使用默认团队（researcher + coder + reviewer）
python main.py --team "设计一个 RESTful API 用户认证系统"

# 指定团队配置文件和协作模式
python main.py --team --team-config team_config.json --team-mode parallel "任务"

# debate 模式（可设置辩论轮数）
python main.py --team --team-mode debate --team-rounds 3 "Python vs Go for web backend"
```

### 团队配置文件 (`team_config.json`)

```json
{
  "name": "dev_team",
  "members": [
    {
      "name": "architect",
      "role": "architect",
      "system_prompt": "You are a software architect. Design clean, scalable architectures."
    },
    {
      "name": "coder",
      "role": "coder",
      "system_prompt": "You are an expert Python engineer."
    },
    {
      "name": "reviewer",
      "role": "reviewer",
      "system_prompt": "You are a senior code reviewer."
    },
    {
      "name": "tester",
      "role": "tester",
      "system_prompt": "You are a QA engineer. Write comprehensive test cases."
    }
  ]
}
```

在 GUI 的 **Team** 页面中可以可视化配置团队成员、选择协作模式和辩论轮数。

## Windows 打包

安装依赖：

```bash
pip install -r requirements.txt
```

使用 PyInstaller：

```powershell
pyinstaller packaging\pyinstaller.spec --noconfirm
```

生成目录：

```text
dist\DeepSeek Agent Workbench\DeepSeek Agent Workbench.exe
```

如果需要制作安装包，可以安装 Inno Setup，然后打开：

```text
packaging\installer.iss
```

编译后会生成安装程序。

## 项目结构

```text
.
├── gui_app.py              # GUI 启动入口
├── main.py                 # CLI 启动入口
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── team_config.json        # 默认团队配置
├── memory.db               # 长期记忆数据库（本地）
├── skills/                 # 内置 Skill 定义
│   ├── python_expert.yaml
│   └── code_reviewer.json
├── data/plugins/           # 插件数据
├── packaging/              # 打包配置
│   ├── pyinstaller.spec
│   └── installer.iss
└── src/deepseek_agent/     # 核心源码
    ├── agent.py            # Agent 主类（LLM + 工具 + RAG + 记忆）
    ├── cli.py              # 命令行接口
    ├── gui/                # PyQt6 桌面界面
    │   ├── main_window.py  # 主窗口
    │   ├── dashboard_page.py
    │   ├── chat_page.py
    │   ├── model_page.py
    │   ├── memory_page.py
    │   ├── team_page.py
    │   ├── skills_tools_page.py
    │   ├── tokens_page.py
    │   ├── sidebar.py
    │   ├── chat_store.py
    │   ├── plugin_store.py
    │   ├── stats_store.py
    │   ├── daily_memory_store.py
    │   └── theme.py
    ├── memory/             # 记忆模块
    │   ├── base.py         # 抽象基类
    │   ├── conversation.py # 对话记忆
    │   └── long_term.py    # 长期记忆（SQLite）
    ├── rag/                # RAG 检索增强生成
    │   ├── embeddings.py   # Embedding 引擎
    │   ├── loader.py       # 文档加载
    │   ├── retriever.py    # 检索器
    │   ├── splitter.py     # 文本分割
    │   └── store.py        # 向量存储
    ├── skill/              # 技能系统
    │   ├── base.py         # Skill 基类
    │   ├── loader.py       # Skill 加载器
    │   └── registry.py     # Skill 注册中心
    ├── team/               # 团队协作
    │   ├── team.py         # Agent 团队
    │   ├── sub_agent.py    # 子 Agent 和 SubAgentTool
    │   └── patterns.py     # 协作模式
    └── tools/              # 工具系统
        ├── base.py         # Tool 基类
        ├── builtin.py      # 13 个内置工具
        ├── executor.py     # 工具执行器
        └── external_loader.py  # 外部工具加载
```

## 安全说明

本项目会在本地保存运行数据，例如模型配置、聊天统计、插件状态等。默认忽略以下本地文件：

```text
.env
data/
*.db
*.sqlite
*.sqlite3
*.pkl
.venv/
.idea/
__pycache__/
```

请不要提交真实 API Key、Token、本地数据库、聊天记录或工作区私有文件。
