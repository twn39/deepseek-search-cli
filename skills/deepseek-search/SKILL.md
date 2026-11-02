---
name: deepseek-search
description: Search the live web and extract clean Markdown content using DeepSeek Search and Fetch APIs. Use when the user asks to search the web (搜索, 网络搜索, 查资料, 检索最新信息), look up real-time news, documentation or benchmarks, or fetch/scrape web page content into structured Markdown.
compatibility: Python 3.11+, deepseek-search CLI
metadata:
  version: 1.0.1
  tags:
    - search
    - web-retrieval
    - deepseek
    - fetch
    - scraping
---

# DeepSeek Search & Fetch Skill

`deepseek-search` (executable: `deepseek-search` or `ds-search`) is a token-efficient CLI tool and Python client for DeepSeek's native Search (`POST /v1/tools/search`) and Fetch (`POST /v1/tools/fetch`) APIs.

It provides real-time web search with rerank scores (`>= 1.5` is high quality) and authority ratings (`0..4`), full webpage extraction into clean Markdown, and Unix pipeline stream composability.

---

## ⚡ Quick Start for AI Agents

Run via CLI directly:

```bash
# 1. Search the web (returns structured Markdown by default)
deepseek-search search "DeepSeek V4 architecture and release date"

# 2. Search AND extract full webpage text in a SINGLE API call (Most token/cost efficient for RAG!)
deepseek-search search "FastAPI lifespan handlers" --count 3 --need-content

# 3. Deep Markdown webpage fetch (URL protocol https:// is auto-completed if omitted)
deepseek-search fetch "https://docs.deepseek.com" --format raw

# 4. Unix Pipeline: Search then concurrently fetch top 3 pages
deepseek-search search "Swift modern concurrency" -c 3 -f urls | deepseek-search fetch - --format raw
```

---

## 🛠️ Key Commands & Best Practices

### 1. `deepseek-search search <query>`

Search web results using DeepSeek's native search engine.

| Option | Flag | Description |
|---|---|---|
| `--count` | `-c` | Number of results (1~50, default: `10`). |
| `--need-content` | `-C` | **Recommended for Agents**: Extracts full web text within the search response without extra API round-trips. |
| `--fetch-top` | `-F` | Automatically performs deep Markdown conversion on top N results concurrently (1~10). |
| `--format` | `-f` | Output format: `markdown` (default), `json` (for programmatic parsing), `urls` (for piping), `table`, `rich`. |
| `--ori-question` | `-q` | Triggering user question (1~128 chars) to refine search intent. |
| `--output` | `-o` | Save output to file. |

#### Advanced Search Syntax & Blacklist Operators
Operators can be written directly in the query or via dedicated flags:
- `site:domain.com`: Restrict to domain (e.g. `--site github.com`).
- `-site:domain.com`: Exclude domain (e.g. `--exclude-site csdn.net`).
- Persistent Blacklist:
  - Apply curated default blacklist: `deepseek-search config blacklist default` (excludes `csdn.net` to minimize operator length footprint)
  - Add domain: `deepseek-search config blacklist add csdn.net` (automatically appended to all future searches)
  - List domains: `deepseek-search config blacklist list`
  - Clear domains: `deepseek-search config blacklist clear`
  - Bypass blacklist for a single query: `deepseek-search search "..." --no-blacklist`
- `lang:zh` or `lang:en,zh`: Restrict language (e.g. `--lang zh`).
- `after:YYYY[-MM-DD]`: Restrict to pages published after date (e.g. `--after 2025`).
- `before:YYYY[-MM-DD]`: Restrict to pages published before date.

```bash
# Example: Restrict to official docs published in 2025 while excluding spam
deepseek-search search "uv package manager" --site docs.astral.sh --after 2025
```

#### ⚠️ Critical Constraint: 128-Character Query Length Limit

DeepSeek Search API strictly enforces a **hard limit of 128 characters** on the total query string. Exceeding this limit will trigger a client-side pre-flight error before making any network request.

- **What counts towards the 128 characters**:
  - The actual search keywords and quoted phrases.
  - Manual operators (e.g. `site:github.com`, `lang:zh`, `after:2025`).
  - **Persistent blacklist operators**: Any configured blacklist domains (e.g. ` -site:csdn.net` takes 15 characters) are automatically concatenated to the final query. With default `csdn.net` excluded, you have **113 characters** for your search terms.

- **Best Practices for AI Agents**:
  1. **Distill, don't dump**: Do NOT paste whole conversational requests, full exception stack traces, or long code snippets into `<query>`. Distill to 3~6 high-signal keywords and exact symbols (e.g. `"AVCaptureDevice" "isAdjustingFocus" KVO`).
  2. **Use `--ori-question` for semantic context**: DeepSeek supports a separate `ori_question` parameter (up to 128 chars) to steer re-ranking. **It does NOT consume the search query's 128-character budget**:
     ```bash
     deepseek-search search "AVCaptureDevice focus KVO" -q "How to observe camera focus state changes in AVFoundation?"
     ```
  3. **Reclaim budget with `--no-blacklist`**: If a query contains long symbol names and approaches the limit, add `--no-blacklist` to temporarily disable blacklist injection:
     ```bash
     deepseek-search search '"AVCaptureDevice" "isAdjustingFocus" "isAdjustingExposure" KVO focus' --no-blacklist
     ```
  4. **Immediate error recovery**: If you receive `错误: 搜索语句总长度为 N 个字符，超过 DeepSeek 128 字符上限！`, immediately trim non-essential keywords, remove redundant quotes, or append `--no-blacklist`.

---

### 2. `deepseek-search fetch <url>`

Fetch and convert any webpage into clean, LLM-optimized Markdown.

- **URL Protocol Normalization**: You can omit `https://` (e.g. `deepseek-search fetch github.com/astral-sh/uv`).
- **Pipeline Streaming (`-`)**: Pass `-` to read URLs from `stdin` line-by-line:
  ```bash
  cat urls.txt | deepseek-search fetch - --format raw
  ```
- **Concurrency**: When fetching multiple URLs, concurrent threads (up to 5 workers) fetch in parallel while strictly preserving output order.

---

### 3. Unix Pipeline Composability

The CLI adheres to strict standard stream separation:
- `stdout`: Pure payload data (Markdown text, JSON, or URL list).
- `stderr`: Status spinners, progress diagnostics, and errors.

This guarantees robust Unix pipeline chaining without data corruption:
```bash
# Extract links, filter with grep/awk, then fetch content
deepseek-search search "Python 3.14 GIL" -c 5 -f urls | grep -v "example" | deepseek-search fetch -
```

---

## 🐍 Python SDK Integration

If you need to query in-process within Python:

```python
from deepseek_search_cli import DeepSeekClient

with DeepSeekClient() as client:
    # 1. Search with content
    res = client.search("DeepSeek API", count=5, need_content=True)
    for r in res.results:
        print(f"[{r.rerank_score:.2f}] {r.title} ({r.url})")
        if r.content:
            print(r.content[:200])

    # 2. Concurrent multi-page fetch
    batch = client.fetch_many(["github.com", "deepseek.com"], max_workers=5)
    for url, page in batch:
        if not isinstance(page, Exception):
            print(f"Fetched {url}: {page.title}")
```

---

## ⚙️ Configuration & Auth

1. Check configuration status: `deepseek-search config status`
2. Login / save API Key: `deepseek-search config login "sk-..."` (or interactive masked input)
3. Precedence hierarchy: CLI `--api-key` > `DEEPSEEK_API_KEY` env > Local `.env` > `~/.config/deepseek-search/config.json`.

