# Chrome 书签自动整理与健康检查工具

基于 Python、`aiohttp` 异步高并发探活引擎与大语言模型（LLM）的 Chrome 书签自动化健康检查与语义聚类整理工具。

## 核心特性

- **数据安全保障**：执行操作前强制生成时间戳快照备份（`Bookmarks.bak_<timestamp>`），写入持久化严格采用临时文件 `fsync` + 原子 `os.replace`。
- **WebKit 规范遵循**：完整兼容 WebKit 微秒纪元时间戳与 Chrome 目录树自增全局唯一 ID 协议。
- **高并发异步探活**：基于 `aiohttp` 实现 HEAD 优先、遇 405/异常降级流式 GET 的双阶段探活引擎；自动放行 401、403、429 等特权存活状态码；具备瞬时抖动退避重试。
- **终端交互审计**：清晰展示异常状态码与标题链接明细，支持**自动归档**、**直接剔除**或**忽略保留**。
- **LLM 语义分类**：分批提取书签切片，支持 OpenAI、DeepSeek、MiniMax、Ollama 等任意标准兼容接口，输出结构化分类树。

---

## 快速上手

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# OpenAI 接口
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"

# 或使用 MiniMax 接口
# export OPENAI_API_KEY="sk-cp-..."
# export OPENAI_API_BASE="https://api.minimax.chat/v1"
# export MODEL_NAME="MiniMax-M2.7"
```

### 3. 运行整理

> **注意**：Chrome 采用内存常驻机制，运行前请务必完全退出 Chrome 浏览器（macOS: `killall "Google Chrome"`）。

```bash
# 方式一：直接运行脚本
python bookmark_manager.py

# 方式二：使用 CLI 工具高级选项
python -m bookmark_cleaner.cli --action archive -y
```

### 4. 运行单元测试与质量验证

```bash
pytest -v
```
