# AKI Agent Workbench

AKI Agent Workbench 是一个基于 PyQt6 的本地 AI Agent 桌面工作台。项目使用 OpenAI-compatible API 调用 DeepSeek 或其它兼容模型，内置聊天、模型/API 管理、Prompt 管理、插件系统、网页搜索、文件读写编辑和多步骤工具调用能力。

## 主要特性

- PyQt6 桌面 GUI 工作台
- 淡白蓝现代化界面主题
- Dashboard / Chat / Model / Memory / Team / SkillsTools / Tokens 页面
- 多会话聊天记录和会话统计
- 左侧 Prompt 提示词管理
  - 内置 Prompt 预设
  - 自定义系统提示词
  - 支持从 `.md` / `.txt` 导入 Prompt
  - 支持保存 Prompt 到本地 `.env`
- Model 页面支持自定义模型和 API 配置
  - Provider
  - Model Name
  - Base URL
  - API Key
  - 本地 SQLite 持久化保存
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
- 支持“搜索网页内容 -> 总结 -> 生成本地 Markdown 文档”等多步骤任务
- Team / Sub-agent 基础协作能力
- Token 用量和会话统计页面
- Windows 打包配置

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

## Skills & Tools 插件

GUI 中的 `SkillsTools` 页面支持：

- 启用/禁用内置 skills
- 启用/禁用内置 tools
- 从 ZIP 导入新的 skill 或 tool
- 查看插件详情
- 导出插件配置
- 外部 tool 需要手动点击“信任”后才能启用执行

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
├── gui_app.py
├── main.py
├── requirements.txt
├── .env.example
├── team_config.json
├── skills/
├── packaging/
│   ├── pyinstaller.spec
│   └── installer.iss
└── src/
    └── deepseek_agent/
        ├── agent.py
        ├── cli.py
        ├── gui/
        ├── memory/
        ├── rag/
        ├── skill/
        ├── team/
        └── tools/
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
