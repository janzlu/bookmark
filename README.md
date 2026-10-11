# Chrome 书签智能管理工具 (Bookmark Studio)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests: 38 Passed](https://img.shields.io/badge/tests-38%20passed-success.svg)](tests/)

基于 Python 异步并发探活引擎与大语言模型（LLM）的 Chrome 书签健康检查、死链清洗与语义聚类整理工具。提供沉浸式现代化 Web UI 控制台与全能 CLI 命令行双模式。

---

## ✨ 核心特性

- **🛡️ 极致数据安全**：
  - 执行修改前强制生成时间戳快照备份（`Bookmarks.bak_<timestamp>`），支持 10 份历史配额与**一秒无损回滚**。
  - 写入持久化采用同目录临时文件 `flush()` + `fsync` 强制刷盘 + `os.replace` 原子覆写，杜绝断电或异常截断损坏。
  - **物理删除双重安全门禁**：对不可逆物理删除实施逐项人工核验、外链即时验证（↗）与免责复选框校验，并生成 `Bookmarks.deleted_<timestamp>.json` 专有审计日志以供溯源。
- **⚡ 双阶段异步高并发探活**：
  - 基于 `aiohttp` 实现 HEAD 优先、遇 405/异常降级流式 GET 的智能探活引擎；
  - 自动放行 `401 Unauthorized`、`403 Forbidden`、`429 Too Many Requests` 等特权存活状态码；
  - 具备指数退避抗网络抖动重试，支持严格/自适应 SSL 校验。
- **🤖 LLM 语义聚类分类**：
  - 批量提取书签切片，支持 OpenAI、DeepSeek、MiniMax、Ollama 等任意标准兼容接口；
  - 智能构建多级目录树，兼容 WebKit 微秒纪元时间戳与 Chrome 目录自增全局唯一 ID 协议。
- **🎨 现代化沉浸式 Web UI 与 CLI**：
  - **Web UI**：玻璃拟态（Glassmorphism）设计、SSE 实时流式进度推送、死链多维度筛选/批量处置、重构树状折叠预览与快照恢复中心。
  - **CLI**：支持无人值守流水线（`--action archive -y`）与终端高亮交互决策。
- **🔒 隐私与敏感信息保护**：
  - 严格本地运行，书签数据绝不上传第三方服务器（仅在语义分类时将标题和 URL 提交给用户配置的 LLM）；
  - 密钥仅通过环境变量或内存加载，项目 `.gitignore` 完备屏蔽任何本地书签、备份快照、密钥文件及系统缓存。

---

## 🚀 快速上手

### 1. 克隆代码与安装依赖

```bash
git clone https://github.com/janzlu/bookmark.git
cd bookmark

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows 用户: .venv\Scripts\activate

# 安装核心依赖
pip install -r requirements.txt
```

### 2. 配置环境变量 (可选，亦可在 Web UI 中配置)

```bash
# 选项 A: OpenAI 官方接口
export OPENAI_API_KEY="sk-your-openai-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"

# 选项 B: MiniMax 接口 (推荐)
# export OPENAI_API_KEY="sk-cp-your-minimax-key"
# export OPENAI_BASE_URL="https://api.minimax.chat/v1"
# export MODEL_NAME="MiniMax-M2.7"

# 选项 C: DeepSeek 接口
# export OPENAI_API_KEY="sk-your-deepseek-key"
# export OPENAI_BASE_URL="https://api.deepseek.com"
# export MODEL_NAME="deepseek-chat"

# 选项 D: 本地 Ollama 接口 (无需真实 API Key)
# export OPENAI_API_BASE="http://localhost:11434/v1"
# export OPENAI_API_KEY="ollama"
# export MODEL_NAME="qwen2.5:7b"
```

> 💡 **提示**：未配置 API Key 时，工具会自动降级将书签归入「其他/待整理」分类，链接探活与清洗功能仍可完全正常使用。

---

## 💻 使用方式

> [!IMPORTANT]
> **重要前置操作**：Chrome 采用内存常驻机制，关闭浏览器时会覆写磁盘书签文件。**在执行覆写保存前，请务必完全退出 Chrome 浏览器**（macOS: `killall "Google Chrome"`）。

### 方式一：启动 Web UI 现代化管理控制台 (推荐)

```bash
python bookmark_manager.py --ui
# 或自定义端口
python -m bookmark_cleaner.cli --ui --port 8080
```

启动后在浏览器打开 `http://127.0.0.1:8080`：
1. **实时指标看板**：展示书签总数、去重后保留数、重复数与历史快照数；
2. **环境安全雷达**：实时探测 Chrome 进程状态，防止内存覆写；
3. **死链交互审计卡片**：支持按 404/超时/SSL 异常过滤、单项/批量选择自动归档、彻底删除或忽略保留；
4. **AI 分类与目录树重构预览**：多级目录树折叠可视化，确认无误后一键覆写保存；
5. **一秒快照恢复中心**：可视化历史快照列表，支持随时一键回滚。

### 方式二：终端 CLI 交互式运行

```bash
python bookmark_manager.py
```

### 方式三：CLI 高级命令行选项（适合自动化脚本）

```bash
# 全自动无人值守：跳过确认并将失效书签自动归档
python -m bookmark_cleaner.cli --action archive -y

# 指定自定义书签路径与模型
python -m bookmark_cleaner.cli --path "/path/to/Bookmarks" --model "deepseek-chat"
```

**CLI 参数说明**：
| 参数 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `--path` | 指定 Chrome 书签文件路径 | 自动适配当前系统默认路径 |
| `--action` | 失效书签处置策略 (`archive` / `delete` / `keep`) | 交互式询问 |
| `-y, --yes` | 跳过执行前的退出 Chrome 确认交互 | `False` |
| `--ui` | 启动 Web UI 智能管理工作台 | `False` |
| `--port` | Web UI 服务端口 | `8080` |
| `--concurrency` | 最大异步网络并发数 | `30` |
| `--batch-size` | LLM 批处理切片大小 | `25` |
| `--model` | 大模型名称 | 智能判定 / `gpt-4o-mini` |
| `--base-url` | OpenAI 兼容接口 Base URL | `https://api.openai.com/v1` |
| `--ssl-verify` | 开启严格 SSL 证书校验 | `False` (放行自签名/内网证书) |

---

## 🔒 敏感信息与数据安全保障

1. **隐私安全**：
   - 本工具不搜集任何遥测数据；
   - 所有的书签扫描、健康检查与文件覆写均在本地计算机完成；
   - 本项目通过 `.gitignore` 严格屏蔽了所有本地书签源文件（`Bookmarks`）、备份快照（`Bookmarks.bak_*`）、删除日志（`Bookmarks.deleted_*`）以及 `.env` 凭据文件。
2. **一秒无损回滚**：
   若对整理结果不满意，可通过 Web UI 的「快照恢复」面板一键回滚，或在终端手工将最新的 `Bookmarks.bak_<timestamp>` 复制回 `Bookmarks`。

---

## 🧪 自动化测试

项目具备完备的单元测试与端到端集成测试套件：

```bash
pytest -v
```

覆盖备份持久化、ID 自增单调性、URL 规范化、双阶段探活、LLM 容错解析、SSE 流式接口、物理删除安全拦截（HTTP 400）等关键机制（**38 项测试用例全部通过**）。

---

## 📖 深入了解

关于系统的六阶段流水线架构、WebKit 时间戳算法细节、模块 API 说明与异常排查指南，请参阅：
👉 [技术架构与完整使用指南 (docs/README.md)](docs/README.md)
