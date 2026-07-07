# DeepSeek Agent Workbench

一个基于 PyQt6 的 DeepSeek Agent 桌面工作台，使用 OpenAI Python SDK 调用 DeepSeek API。

当前包含：

- 命令行 Agent
- PyQt6 GUI 工作台
- 浅色国风仪表盘主题
- Dashboard / Chat / Model / Skills & Tools / Tokens 页面
- Skills 可视化启用/禁用和 ZIP 导入
- Tools 可视化启用/禁用，内置支持 `web_search` 搜索和 `web_fetch` 网页抓取，外部 Tool 支持信任确认后动态加载执行
- 插件详情查看和插件配置导出
- DeepSeek API Key 与 Base URL 配置
- Windows 打包配置模板

## 安装

```bash
pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env`，并填入你的 DeepSeek API Key：

```bash
copy .env.example .env
```

`.env` 示例：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

也可以在 GUI 左侧配置区导入、保存和应用 `.env`。

## 运行 GUI 工作台

```bash
python gui_app.py
```

## Skills & Tools 插件

GUI 中的 `Skills & Tools` 页面支持：

- 启用/禁用内置 skills
- 启用/禁用内置 tools
- 从 ZIP 导入新的 skill 或 tool
- 查看插件详情
- 导出插件配置
- 外部 tool 需要手动点击“信任”后才能启用执行

### Skill ZIP

```text
my_skill.zip
└── my_skill/
    ├── manifest.json
    └── skill.yaml
```

`manifest.json`：

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

### Tool ZIP

```text
my_tool.zip
└── my_tool/
    ├── manifest.json
    └── tool.py
```

`manifest.json`：

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

`tool.py` 需要定义 `Tool` 类或 `create_tool()` 函数，并返回 `BaseTool` 实例。

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


## 运行命令行

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

## Windows 打包

先安装依赖：

```bash
pip install -r requirements.txt
```

使用 PyInstaller 生成桌面程序：

```bash
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

编译后会生成：

```text
dist-installer\DeepSeekAgentWorkbenchSetup.exe
```

## 项目结构

```text
.
├── gui_app.py
├── main.py
├── requirements.txt
├── .env.example
├── packaging/
│   ├── pyinstaller.spec
│   └── installer.iss
└── src/
    └── deepseek_agent/
        ├── agent.py
        ├── cli.py
        └── gui/
            ├── app.py
            ├── main_window.py
            ├── theme.py
            ├── dashboard_page.py
            ├── sidebar.py
            ├── chat_page.py
            ├── model_page.py
            └── tokens_page.py
```
