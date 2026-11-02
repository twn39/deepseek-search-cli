from __future__ import annotations

import contextlib
import json
from collections.abc import Generator

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from deepseek_search_cli.models import FetchResponse, SearchResponse

console = Console()
err_console = Console(stderr=True)


@contextlib.contextmanager
def status_spinner(message: str) -> Generator[None, None, None]:
    """Display animated status spinner on stderr only when running in an interactive terminal."""
    if err_console.is_terminal:
        with err_console.status(message):
            yield
    else:
        yield


def format_search_results_rich(
    response: SearchResponse,
    show_summary: bool = True,
    show_content: bool = False,
    console_out: Console = console,
) -> None:
    """Render search results as rich terminal cards/panels."""
    if not response.results:
        console_out.print("[yellow]未找到匹配的搜索结果。[/yellow]")
        return

    console_out.print(f"[bold blue]🔍 共检索到 {len(response.results)} 条结果[/bold blue]\n")

    for idx, item in enumerate(response.results, 1):
        # Build badges
        badges = []

        # Rerank score badge (>= 1.5 is high quality)
        if item.is_high_quality:
            badges.append(f"[bold green]得分: {item.rerank_score:.2f} (优质)[/bold green]")
        else:
            badges.append(f"[dim]得分: {item.rerank_score:.2f}[/dim]")

        # Authority badge (>= 3 is extremely authoritative, -1 unknown)
        if item.authority >= 3:
            badges.append(f"[bold cyan]权威度: {item.authority}/4 (极权威)[/bold cyan]")
        elif item.authority >= 0:
            badges.append(f"[dim]权威度: {item.authority}/4[/dim]")

        if item.site_name:
            badges.append(f"[magenta]站点: {item.site_name}[/magenta]")

        if item.date:
            clean_date = item.date.split("T")[0]
            badges.append(f"[dim]发布日期: {clean_date}[/dim]")

        badge_line = " | ".join(badges)

        # Body text: summary or snippet
        text_content = []
        if badge_line:
            text_content.append(badge_line + "\n")

        if show_summary and item.summary:
            text_content.append(f"[bold]摘要：[/bold]\n{item.summary}")
        elif item.snippet:
            text_content.append(f"[bold]短摘要：[/bold]\n{item.snippet}")

        if show_content and item.content:
            text_content.append(
                f"\n[bold green]正文摘录：[/bold green]\n{item.content[:500]}..."
                if len(item.content) > 500
                else f"\n[bold green]正文：[/bold green]\n{item.content}"
            )

        title_text = f"#{idx} [link={item.url}]{item.title or '无标题'}[/link]"

        panel = Panel(
            "\n".join(text_content),
            title=title_text,
            title_align="left",
            subtitle=f"[dim underline]{item.url}[/dim underline]",
            subtitle_align="left",
            border_style="cyan" if item.is_high_quality else "dim",
            padding=(1, 2),
        )
        console_out.print(panel)


def format_search_results_table(
    response: SearchResponse,
    console_out: Console = console,
) -> None:
    """Render search results in a concise table."""
    if not response.results:
        console_out.print("[yellow]未找到匹配的搜索结果。[/yellow]")
        return

    table = Table(title="搜索结果", show_lines=True)
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("评分", justify="center", style="green", no_wrap=True)
    table.add_column("标题", style="bold")
    table.add_column("站点", style="magenta")
    table.add_column("发布日期", style="dim", no_wrap=True)
    table.add_column("链接", style="blue underline")

    for idx, item in enumerate(response.results, 1):
        score_str = f"{item.rerank_score:.2f}"
        if item.is_high_quality:
            score_str += " ★"
        date_str = item.date.split("T")[0] if item.date else "-"
        site_str = item.site_name or "-"
        table.add_row(
            str(idx),
            score_str,
            item.title or "无标题",
            site_str,
            date_str,
            item.url,
        )

    console_out.print(table)


def format_search_results_markdown(
    response: SearchResponse,
    show_summary: bool = True,
    show_content: bool = False,
) -> str:
    """Format search results as Markdown string."""
    lines = [f"# 搜索结果 (共 {len(response.results)} 条)\n"]
    for idx, item in enumerate(response.results, 1):
        lines.append(f"## {idx}. [{item.title or '无标题'}]({item.url})")
        meta = []
        meta.append(f"**得分**: {item.rerank_score:.2f}")
        if item.authority >= 0:
            meta.append(f"**权威度**: {item.authority}/4")
        if item.site_name:
            meta.append(f"**站点**: {item.site_name}")
        if item.date:
            meta.append(f"**日期**: {item.date}")
        lines.append(" - " + " | ".join(meta))
        lines.append("")

        if show_summary and item.summary:
            lines.append(f"> {item.summary}\n")
        elif item.snippet:
            lines.append(f"> {item.snippet}\n")

        if show_content and item.content:
            lines.append(f"### 正文内容\n\n{item.content}\n")

        lines.append("---")

    return "\n".join(lines)


def format_search_results_json(response: SearchResponse) -> str:
    """Format search results as pretty JSON."""
    return json.dumps(response.to_dict(), indent=2, ensure_ascii=False)


def format_fetch_result_rich(
    fetch: FetchResponse,
    url: str,
    console_out: Console = console,
) -> None:
    """Render fetched webpage markdown in rich terminal."""
    header = Panel(
        f"[bold green]网页抓取成功[/bold green]\n"
        f"[bold]标题：[/bold]{fetch.title or '无标题'}\n"
        f"[bold]来源：[/bold][underline]{url}[/underline]",
        border_style="green",
    )
    console_out.print(header)
    console_out.print("\n")
    if fetch.content.strip():
        console_out.print(Markdown(fetch.content))
    else:
        console_out.print("[dim]（网页正文为空）[/dim]")


def format_fetch_result_json(fetch: FetchResponse, url: str) -> str:
    """Format fetched webpage as JSON."""
    data = fetch.to_dict()
    data["url"] = url
    return json.dumps(data, indent=2, ensure_ascii=False)
