# DeepSeek Search CLI (`deepseek-search-cli`)

基于 **httpx** 和 **typer** 构建的 DeepSeek 网页搜索与抓取命令行工具，严格对齐 DeepSeek 官方 API 规范。

参考官方文档：
- [网页搜索与抓取使用指南](https://api-docs.deepseek.com/zh-cn/guides/search)
- [Search API Reference](https://api-docs.deepseek.com/zh-cn/api/search)
- [Fetch API Reference](https://api-docs.deepseek.com/zh-cn/api/fetch)

---

## 🌟 特性

- 🔍 **Search 接口完全支持**：调用 DeepSeek 自研搜索引擎（`POST /v1/tools/search`），返回高质量结构化结果（标题、URL、长摘要、短摘要、正文、发布时间、权威度与相关性评分）。
- 📄 **Fetch 接口完全支持**：调用 DeepSeek 抓取服务（`POST /v1/tools/fetch`），抓取网页并提取为干净规范的 Markdown 文本。
- ⚙️ **搜索语法辅助**：内置对 `site:`、`-site:`、`lang:`、`after:`、`before:`、精准短语排除等高级语法的参数化构建与原生支持。
- 🎨 **丰富多样的展现格式**：
  - `rich`：美观的终端卡片，带有评分高亮（≥ 1.5 优质结果、≥ 3 极权威）、网站图标与超链接。
  - `table`：简洁清晰的表格视图。
  - `markdown`：适合投喂给 LLM、RAG 或保存归档的 Markdown。
  - `json`：机器可读的原始/格式化 JSON。
- 💾 **直接保存到文件**：支持通过 `--output / -o` 将搜索结果或抓取内容直接保存到磁盘。
- 🛡️ **生产级异常与限速处理**：映射官方 HTTP 400、401、402、403、404、429、500 等状态码，提供准确的中文指引。
- 🐍 **可作为 Python 库使用**：导出 `DeepSeekClient` 与数据类（`SearchResult`、`SearchResponse`、`FetchResponse`），方便在自己的代码中快速集成。

---

## 📦 安装与配置

### 1. 安装

在工作目录下使用 `uv` 或 `pip` 安装：

```bash
# 使用 uv
uv pip install -e .

# 或者使用 pip
pip install -e .
```

安装完成后，系统将提供 `deepseek-search` 及简写别名 `ds-search` 命令。

### 2. 配置 API Key 与认证凭据

程序支持四种配置途径（优先级从高到低）：
1. 命令行选项 `--api-key`
2. 环境变量 `DEEPSEEK_API_KEY`
3. 本地 `.env` 文件（当前目录或祖先目录）
4. 用户全局配置文件 `~/.config/deepseek-search/config.json`

#### ① 使用 `config` 命令统一管理

```bash
# 1. 交互式安全配置 API Key（自动隐藏输入防止留在终端历史，并自动在线校验凭证）
deepseek-search config login

# 2. 直接传入 Key 配置（默认保存到全局 ~/.config/deepseek-search/config.json）
deepseek-search config login "sk-your-deepseek-api-key"

# 3. 仅保存到当前工作目录的本地 .env（实现项目间隔离）
deepseek-search config login "sk-your-deepseek-api-key" --local

# 4. 检查当前凭证来源、生效 Base URL 与在线探活状态
deepseek-search config status

# 5. 查看全局配置文件路径与完整状态信息
deepseek-search config show

# 6. 设置其他参数（如 Base URL）
deepseek-search config set --base-url "https://api.deepseek.com"

# 7. 清除已保存的全局 API Key
deepseek-search config logout
```

#### ② 通过环境变量配置
```bash
export DEEPSEEK_API_KEY="sk-your-deepseek-api-key"
```

---

## 🚀 命令行用法

### 1. 网页搜索 (`search`)

```bash
# 基础搜索 (默认以 Markdown 格式输出)
deepseek-search search "DeepSeek V4 模型"

# 搜索并自动深度抓取前 3 个结果的网页全文 (联动 Fetch 接口一步到位，适合 RAG/Agent)
deepseek-search search "DeepSeek RAG" --count 5 --fetch-top 3

# 指定返回数量 (1~50，默认 10)
deepseek-search search "DeepSeek 价格" --count 5

# 传递原始用户问题有助于更精准理解搜索意图
deepseek-search search "DeepSeek 价格" --ori-question "DeepSeek 现在的 API 调用价格是多少？"
```

#### 高级搜索语法与辅助参数

你可以直接在 query 中书写搜索语法，也可以使用 CLI 提供的快捷选项：

| 快捷选项 | 示例 | 对应语法 | 说明 |
| :--- | :--- | :--- | :--- |
| `--site` | `--site github.com` | `site:github.com` | 将结果限制在指定站点，支持多个 |
| `--exclude-site` | `--exclude-site example.com` | `-site:example.com` | 排除指定站点 |
| `--lang` | `--lang zh,en` | `lang:zh,en` | 将结果限制在指定语言 |
| `--after` | `--after 2025-01-01` | `after:2025-01-01` | 限制指定日期之后发布的网页 |
| `--before` | `--before 2026-06-01` | `before:2026-06-01` | 限制指定日期之前发布的网页 |

**示例**：
```bash
# 限定在 github.com 和 huggingface.co 搜索 2025 年以后的中文结果
deepseek-search search "DeepSeek" --site github.com --site huggingface.co --lang zh --after 2025
```

#### 切换输出格式与保存文件

搜索命令默认直接输出规范结构化的 **Markdown** 文本，非常便于终端阅读、管道重定向或投喂给大模型；同时也支持切换其他格式：

```bash
# 默认即为 Markdown 输出
deepseek-search search "DeepSeek V4"

# 切换为彩色终端卡片视图 (rich)
deepseek-search search "DeepSeek V4" --format rich

# 切换为表格视图 (table)
deepseek-search search "量子计算" --format table

# 输出纯 URL 列表 (urls) - 极度适合与管道协同
deepseek-search search "DeepSeek" --format urls

# 优雅的 Unix 管道：搜索并直接并发抓取前 3 个网页全文
deepseek-search search "DeepSeek V4" -c 3 -f urls | deepseek-search fetch -

# 输出 JSON 格式供脚本处理
deepseek-search search "DeepSeek" --format json

# 保存搜索结果到本地文件
deepseek-search search "AI Agent" --output agent_search.md
```

---

### 2. 网页抓取与解析 (`fetch`)

Fetch 接口抓取目标网页，并以清洁的 Markdown 格式返回。

```bash
# 抓取单个网页（支持自动补齐 https://，可省略前缀）
deepseek-search fetch "deepseek.com"

# 管道支持：通过 stdin 按行接收 URL 进行并发批量抓取（多 URL 默认最多 5 并发）
cat urls.txt | deepseek-search fetch - --format raw

# 输出原始 Markdown 纯文本
deepseek-search fetch "https://example.com/article" --format raw

# 抓取并直接保存为本地 Markdown 文件
deepseek-search fetch "https://api-docs.deepseek.com/zh-cn/guides/search" -o docs_search.md

# 以 JSON 格式输出包含标题和正文的数据
deepseek-search fetch "https://example.com/article" --format json
```

---

## 🐍 作为 Python SDK 调用

```python
from deepseek_search_cli import DeepSeekClient, normalize_url

with DeepSeekClient(api_key="sk-your-key") as client:
    # 1. 网页搜索 (如需一步获取全文正文，可传 need_content=True)
    search_res = client.search(
        query="DeepSeek V4 site:github.com",
        count=5,
        need_content=True,
    )
    for item in search_res.results:
        print(f"[{item.rerank_score}] {item.title}: {item.url}")

    # 2. 单个网页抓取
    fetch_res = client.fetch("deepseek.com")
    print(fetch_res.title, len(fetch_res.content))

    # 3. 并发批量抓取 (多线程并发并保序，默认 max_workers=5)
    urls = ["https://example.com/1", "https://example.com/2"]
    batch_results = client.fetch_many(urls, max_workers=5)
    for url, res in batch_results:
        if not isinstance(res, Exception):
            print(f"抓取成功: {url} -> {res.title}")
        print(f"摘要: {item.summary}\n")

    # 2. 抓取网页 Markdown
    fetch_res = client.fetch("https://api-docs.deepseek.com/zh-cn/guides/search")
    print(f"标题: {fetch_res.title}")
    print(fetch_res.content[:300])
```

---

## 🧪 运行测试

```bash
uv run python -m unittest discover tests
```

---

## 📋 错误码说明 (对齐官方文档)

| HTTP 状态码 | 含义 | 处理建议 |
| :--- | :--- | :--- |
| **400** | 请求头或请求体不合法 | 检查 query 是否在 1~128 字符内、count 是否在 1~50 范围 |
| **401** | API Key 缺失或无效 | 检查 `DEEPSEEK_API_KEY` 是否正确配置 |
| **402** | 账号余额不足 | 前往 DeepSeek 控制台充值后重试 |
| **403** | Fetch 请求被安全策略拒绝 | 目标站点或安全策略限制访问 |
| **404** | Fetch 未能获取可用网页内容 | 页面可能不存在、目标站点拦截或无 Markdown 正文 |
| **408 / 504** | 读取超时 / 下游超时 | 网络问题，请稍后重试 |
| **429** | 超过 QPS 限制 | Search 限制 100 QPS，Fetch 限制 25 QPS，请降低并发后重试 |
| **500** | 服务器内部错误 | DeepSeek 服务端错误，请稍后重试 |
