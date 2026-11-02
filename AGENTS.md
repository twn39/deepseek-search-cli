# AGENTS.md

> Machine-readable operating guidelines and technical context for AI coding agents (Antigravity, Claude Code, Cursor, Codex, etc.).

## 1. Tech Stack & Environment

- **Language & Runtime**: Python `>=3.11, <3.15` (tested on 3.11, 3.12, 3.13, 3.14).
- **Package & Env Manager**: `uv` (build backend: `uv_build`).
- **Core Dependencies**: `httpx>=0.28.1`, `typer>=0.27.3`, `rich>=13.0.0`.
- **Dev Tooling**: `ruff>=0.17.3` (linter & formatter), `ty>=0.0.95` (type checker).

---

## 2. Essential Commands

```bash
# Setup & Dependency Sync
uv sync

# Run Test Suite (25 unit tests)
uv run python -m unittest discover tests -v

# Code Quality & Format Checks
uv run ruff check .
uv run ruff format --check .
uv run ty check

# Auto-format Code
uv run ruff format .

# Build Artifacts (sdist & wheel)
uv build

# Rebuild Knowledge Graph
codegraph build . -e .venv -e dist
```

---

## 3. Project Layout & Architecture

```
deepseek-search/
├── src/deepseek_search_cli/
│   ├── __init__.py      # Public exports: DeepSeekClient, SearchResult, etc.
│   ├── client.py        # Network client: connection pooling, Bearer auth, retry backoff
│   ├── models.py        # Dataclasses: SearchResult, SearchResponse, FetchResponse
│   ├── query.py         # Pure function query builder: build_search_query()
│   ├── formatters.py    # UI/Output: Markdown, Rich, Table, JSON + status_spinner (stderr)
│   ├── config.py        # 4-tier config resolution: CLI > ENV > .env > config.json (0o600)
│   └── cli.py           # Typer CLI commands: search, fetch, config (login/status/logout/set)
├── tests/
│   ├── test_client.py   # Unit tests for network client, retries, and models
│   └── test_cli.py      # Unit tests for CLI commands, stdin piping, and auth
├── .codegraph/          # Auto-generated knowledge graph vault
├── pyproject.toml       # PEP 621 metadata & tool configs (Ruff py311, 100 line length)
└── AGENTS.md            # Agent instructions & boundary definitions
```

---

## 4. Operational Boundaries

### Always
- **Clean Stream Separation**: Data/payloads (Markdown, JSON, Table) MUST be printed to `stdout`. All logs, interactive prompts, spinners, and diagnostics MUST be routed to `stderr` (`err_console`) to guarantee Unix pipeline composability (e.g., `ds-search search "foo" | grep ...`).
- **Run Verification**: Ensure `uv run python -m unittest discover tests -v`, `uv run ruff check .`, and `uv run ty check` pass with zero errors before concluding any task.
- **Maintain Test Isolation**: Mock network requests via `httpx.MockTransport` and patch `resolve_api_key` in CLI tests to avoid reading local `.env` keys.
- **File Permissions**: Always enforce `0o600` on credentials files created or modified by `config.py`.

### Ask First
- Before introducing new runtime dependencies or updating major framework versions.
- Before modifying public CLI command signatures or argument contracts.

### Never
- **Never commit `.env` or hardcode secrets**: Do not log raw API keys; always mask keys (e.g., `sk-1234...abcd`).
- **Never bypass linter/type checks**: Do not introduce `# noqa` or `# type: ignore` without explicit justification.

---

## 5. Code Style & Design Patterns

- **Pragmatic Modern Architecture**: Follow Apple modern engineering principles — shallow hierarchy, minimal cognitive overhead, pure business logic decoupled from CLI I/O.
- **Python 3.11+ Idioms**:
  - Always include `from __future__ import annotations`.
  - Use `enum.StrEnum` for string-based enums.
  - Use `X | None` instead of `Optional[X]`, and builtin generics (`list[str]`, `dict[str, Any]`).
  - Use `collections.abc.Generator[None, None, None]` for `@contextmanager` return annotations.

---

## 6. Definition of Done (DoD)

Before declaring a task completed:
1. [ ] Code changes adhere to Python 3.11 ~ 3.14 compatibility.
2. [ ] `uv run python -m unittest discover tests -v` passes (all 25 tests pass).
3. [ ] `uv run ruff check .` reports 0 errors.
4. [ ] `uv run ruff format --check .` passes cleanly.
5. [ ] `uv run ty check` reports "All checks passed!".
6. [ ] Knowledge graph is updated via `codegraph build . -e .venv -e dist`.

## codegraph-gen

This project maintains a codebase knowledge graph at `.codegraph/`.

### Guidelines for AI Agents (Antigravity, Claude Code, Cursor, Roo Code, etc.)

You MUST follow these rules when working in this codebase:

1. **Prioritize the Knowledge Graph**:
   - Before answering architecture, design, or codebase structure questions, you **MUST** read [.codegraph/README.md](.codegraph/README.md) to understand the system overview, god nodes, and logical community structure.
   - Use [.codegraph/components/](.codegraph/components/) and [.codegraph/nodes/](.codegraph/nodes/) to navigate component boundaries, file relationships, and symbol definitions. This is much faster and more token-efficient than reading raw source files directly.

2. **AI Architectural Insights**:
   - Check [.codegraph/README.md](.codegraph/README.md) for a section titled `AI Architectural Insights`.
   - If this section is missing, incomplete, or contains placeholders, read [.codegraph/AGENT_PROMPT.md](.codegraph/AGENT_PROMPT.md), perform a deep architectural analysis of the project, and write your report into that section. Do not overwrite other sections.

3. **Keep Graph Sync'd**:
   - Whenever you create, delete, or modify code files, you **SHOULD** remind the user to run `codegraph build .` to rebuild the knowledge graph and keep it current.
   - When running the build command, exclude irrelevant or generated directories (e.g., third-party dependencies, build folders, or documentation) using the `-e`/`--exclude` flag to keep the graph focused and clean (e.g., `codegraph build . -e third_party/`).
