from __future__ import annotations

import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from deepseek_search_cli import __version__
from deepseek_search_cli.client import (
    DEFAULT_BASE_URL,
    DeepSeekAPIError,
    DeepSeekClient,
)
from deepseek_search_cli.config import (
    DEFAULT_BLACKLIST,
    add_to_blacklist,
    clean_domain_name,
    clear_blacklist,
    get_api_key_source,
    get_config_file,
    load_file_config,
    remove_from_blacklist,
    resolve_api_key,
    resolve_base_url,
    resolve_blacklist,
    save_file_config,
    save_local_env,
    set_default_blacklist,
)
from deepseek_search_cli.formatters import (
    console,
    err_console,
    format_fetch_result_json,
    format_fetch_result_rich,
    format_search_results_json,
    format_search_results_markdown,
    format_search_results_rich,
    format_search_results_table,
    format_search_results_urls,
    status_spinner,
)
from deepseek_search_cli.installer import install_skills, skills_app
from deepseek_search_cli.models import FetchResponse
from deepseek_search_cli.query import build_search_query

_build_augmented_query = build_search_query

app = typer.Typer(
    name="deepseek-search",
    help="基于 DeepSeek Search 和 Fetch API 的命令行搜索与网页抓取工具",
    no_args_is_help=True,
    add_completion=False,
)


class SearchFormat(StrEnum):
    RICH = "rich"
    TABLE = "table"
    MARKDOWN = "markdown"
    JSON = "json"
    URLS = "urls"


class FetchFormat(StrEnum):
    MARKDOWN = "markdown"
    RAW = "raw"
    JSON = "json"


def version_callback(value: bool) -> None:
    if value:
        console.print(
            f"[bold cyan]deepseek-search-cli[/bold cyan] version [bold green]{__version__}[/bold green]"
        )
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="显示当前版本号并退出",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """DeepSeek Search CLI 客户端 - 网页搜索与抓取工具"""


@app.command("search", help="使用 DeepSeek 自研搜索引擎搜索网页 (POST /v1/tools/search)")
def search_command(
    query: Annotated[
        str,
        typer.Argument(help="搜索关键词 (1～128 字符，支持 site:、-site:、lang: 等搜索语法)"),
    ],
    count: Annotated[
        int,
        typer.Option(
            "--count",
            "-c",
            min=1,
            max=50,
            help="返回结果条数 (1～50)",
        ),
    ] = 10,
    need_content: Annotated[
        bool,
        typer.Option(
            "--need-content",
            "-C",
            help="是否在返回结果中提取并包含网页正文",
        ),
    ] = False,
    fetch_top: Annotated[
        int,
        typer.Option(
            "--fetch-top",
            "-F",
            min=0,
            max=10,
            help="搜索后自动对前 N 个结果深度抓取全文 Markdown (1~10，0 表示不抓取)",
        ),
    ] = 0,
    ori_question: Annotated[
        str | None,
        typer.Option(
            "--ori-question",
            "-q",
            help="触发搜索的用户原始问题 (1～128 字符，有助于理解搜索意图)",
        ),
    ] = None,
    localization: Annotated[
        str | None,
        typer.Option(
            "--localization",
            "-l",
            help="用于优先返回本地化搜索结果的 IP 地址",
        ),
    ] = None,
    site: Annotated[
        list[str] | None,
        typer.Option(
            "--site",
            help="限定站点 (例如 github.com，可多次指定)",
        ),
    ] = None,
    exclude_site: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude-site",
            help="排除站点 (例如 csdn.net，可多次指定)",
        ),
    ] = None,
    no_blacklist: Annotated[
        bool,
        typer.Option(
            "--no-blacklist",
            help="本次搜索忽略已配置的持久化站点黑名单",
        ),
    ] = False,
    lang: Annotated[
        str | None,
        typer.Option(
            "--lang",
            help="限定语言 (例如 zh 或 zh,en)",
        ),
    ] = None,
    after: Annotated[
        str | None,
        typer.Option(
            "--after",
            help="限定在此日期之后发布的网页 (例如 2025 或 2025-01-01)",
        ),
    ] = None,
    before: Annotated[
        str | None,
        typer.Option(
            "--before",
            help="限定在此日期之前发布的网页 (例如 2026 或 2026-06-01)",
        ),
    ] = None,
    format_: Annotated[
        SearchFormat,
        typer.Option(
            "--format",
            "-f",
            help="输出展示格式",
            case_sensitive=False,
        ),
    ] = SearchFormat.MARKDOWN,
    show_summary: Annotated[
        bool,
        typer.Option(
            "--summary/--snippet",
            help="在卡片和 Markdown 输出中优先展示 600~800 字模型长摘要还是短摘要",
        ),
    ] = True,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="将搜索结果保存到指定文件",
        ),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            envvar="DEEPSEEK_API_KEY",
            help="DeepSeek API Key (也可通过环境变量 DEEPSEEK_API_KEY 配置)",
        ),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            envvar="DEEPSEEK_BASE_URL",
            help=f"DeepSeek API 基础地址 (默认: {DEFAULT_BASE_URL})",
        ),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="请求超时时间 (秒)",
        ),
    ] = 30.0,
) -> None:
    merged_exclude = list(exclude_site or [])
    if not no_blacklist:
        persisted = resolve_blacklist()
        for d in persisted:
            if d not in merged_exclude:
                merged_exclude.append(d)

    final_query = _build_augmented_query(
        query=query,
        site=site,
        exclude_site=merged_exclude or None,
        lang=lang,
        after=after,
        before=before,
    )

    if len(final_query) > 128:
        base_len = len(query.strip())
        ops_len = len(final_query) - base_len
        err_console.print(
            f"[bold red]错误:[/bold red] 搜索语句总长度为 {len(final_query)} 个字符，超过 DeepSeek 128 字符上限！\n"
            f"  • 原始关键词: {base_len} 字符 ('{query.strip()}')\n"
            f"  • 过滤操作符: {ops_len} 字符\n"
            f"[yellow]建议:[/yellow] 请精简关键词或减少 --site / --exclude-site 等过滤参数。"
        )
        raise typer.Exit(code=1)

    try:
        client = DeepSeekClient(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
    except ValueError as e:
        err_console.print(f"[bold red]配置错误:[/bold red] {e}")
        raise typer.Exit(code=1)

    with client as active_client:
        try:
            with status_spinner(f"[cyan]正在使用 DeepSeek 搜索: '{final_query}'...[/cyan]"):
                response = active_client.search(
                    query=final_query,
                    count=count,
                    need_content=need_content,
                    ori_question=ori_question,
                    localization=localization,
                )

            # Auto-fetch top N results if requested
            if fetch_top > 0 and response.results:
                top_targets = response.results[:fetch_top]
                with status_spinner(
                    f"[cyan]正在深度抓取前 {len(top_targets)} 个网页正文...[/cyan]"
                ):
                    if len(top_targets) == 1:
                        target = top_targets[0]
                        try:
                            fetch_res = active_client.fetch(target.url)
                            if fetch_res.content.strip():
                                target.content = fetch_res.content
                        except Exception as e:  # noqa: BLE001
                            target.content = f"(网页抓取失败: {e})"
                    else:
                        target_urls = [r.url for r in top_targets]
                        fetch_results = active_client.fetch_many(target_urls, max_workers=5)
                        for r, (_, res) in zip(top_targets, fetch_results, strict=False):
                            if isinstance(res, FetchResponse):
                                if res.content.strip():
                                    r.content = res.content
                            elif isinstance(res, Exception):
                                r.content = f"(网页抓取失败: {res})"
        except DeepSeekAPIError as e:
            err_console.print(
                f"[bold red]API 请求失败 (HTTP {e.status_code}):[/bold red] {e.message}"
            )
            if e.error_code:
                err_console.print(f"[dim]错误代码: {e.error_code}[/dim]")
            raise typer.Exit(code=1)
        except Exception as e:  # noqa: BLE001
            err_console.print(f"[bold red]请求出错:[/bold red] {e}")
            raise typer.Exit(code=1)

    # Render format
    show_full_content = need_content or (fetch_top > 0)
    save_content: str | None = None
    if format_ == SearchFormat.RICH:
        format_search_results_rich(
            response=response,
            show_summary=show_summary,
            show_content=show_full_content,
        )
    elif format_ == SearchFormat.TABLE:
        format_search_results_table(response=response)
    elif format_ == SearchFormat.MARKDOWN:
        save_content = format_search_results_markdown(
            response=response,
            show_summary=show_summary,
            show_content=show_full_content,
        )
        console.print(save_content, highlight=False)
    elif format_ == SearchFormat.JSON:
        save_content = format_search_results_json(response)
        console.print(save_content)
    elif format_ == SearchFormat.URLS:
        save_content = format_search_results_urls(response)
        console.print(save_content, highlight=False)

    # Save to file if requested
    if output:
        try:
            if save_content is None:
                if format_ == SearchFormat.JSON:
                    save_content = format_search_results_json(response)
                elif format_ == SearchFormat.URLS:
                    save_content = format_search_results_urls(response)
                else:
                    save_content = format_search_results_markdown(
                        response=response,
                        show_summary=show_summary,
                        show_content=show_full_content,
                    )
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(save_content, encoding="utf-8")
            err_console.print(f"\n[bold green]✓ 结果已保存至:[/bold green] {output.resolve()}")
        except OSError as e:
            err_console.print(f"[bold red]写入文件失败:[/bold red] {e}")
            raise typer.Exit(code=1)


@app.command(
    "fetch",
    help="使用 DeepSeek Fetch API 抓取指定网页并解析为 Markdown (POST /v1/tools/fetch)",
)
def fetch_command(
    url: Annotated[
        str | None,
        typer.Argument(
            help="要抓取的网页 URL (必须以 http:// 或 https:// 开头)；传入 '-' 或管道输入时将从标准输入逐行读取 URL",
        ),
    ] = None,
    format_: Annotated[
        FetchFormat,
        typer.Option(
            "--format",
            "-f",
            help="输出格式 (markdown: 富文本终端渲染, raw: 原始 Markdown 文本, json: JSON 数据)",
            case_sensitive=False,
        ),
    ] = FetchFormat.MARKDOWN,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="将抓取的 Markdown 内容保存到指定文件",
        ),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            envvar="DEEPSEEK_API_KEY",
            help="DeepSeek API Key (也可通过环境变量 DEEPSEEK_API_KEY 配置)",
        ),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            envvar="DEEPSEEK_BASE_URL",
            help=f"DeepSeek API 基础地址 (默认: {DEFAULT_BASE_URL})",
        ),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="请求超时时间 (秒)",
        ),
    ] = 30.0,
) -> None:
    # Collect target URLs (argument or stdin)
    target_urls: list[str] = []
    if url and url.strip() != "-":
        target_urls.append(url.strip())
    else:
        if sys.stdin.isatty():
            err_console.print(
                "[bold red]错误:[/bold red] 请提供要抓取的网页 URL，或通过管道传入 URL。"
            )
            raise typer.Exit(code=1)
        for line in sys.stdin:
            line_str = line.strip()
            if line_str and not line_str.startswith("#"):
                target_urls.append(line_str)

    if not target_urls:
        err_console.print("[bold yellow]未读取到有效的网页 URL。[/bold yellow]")
        raise typer.Exit(code=1)

    try:
        client = DeepSeekClient(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
    except ValueError as e:
        err_console.print(f"[bold red]配置错误:[/bold red] {e}")
        raise typer.Exit(code=1)

    results: list[tuple[str, FetchResponse]] = []
    with client as active_client:
        if len(target_urls) == 1:
            u = target_urls[0]
            try:
                with status_spinner(f"[cyan]正在抓取网页: {u}...[/cyan]"):
                    fetch_res = active_client.fetch(url=u)
                    results.append((u, fetch_res))
            except DeepSeekAPIError as e:
                err_console.print(
                    f"[bold red]API 请求失败 ({u} - HTTP {e.status_code}):[/bold red] {e.message}"
                )
                raise typer.Exit(code=1)
            except Exception as e:  # noqa: BLE001
                err_console.print(f"[bold red]抓取出错 ({u}):[/bold red] {e}")
                raise typer.Exit(code=1)
        else:
            with status_spinner(
                f"[cyan]正在并发抓取 {len(target_urls)} 个网页 (最多 5 并发)...[/cyan]"
            ):
                batch_res = active_client.fetch_many(target_urls, max_workers=5)
            for orig_u, res in batch_res:
                if isinstance(res, FetchResponse):
                    results.append((orig_u, res))
                elif isinstance(res, DeepSeekAPIError):
                    err_console.print(
                        f"[bold red]API 请求失败 ({orig_u} - HTTP {res.status_code}):[/bold red] {res.message}"
                    )
                elif isinstance(res, Exception):
                    err_console.print(f"[bold red]抓取出错 ({orig_u}):[/bold red] {res}")

    if not results:
        err_console.print("[bold red]所有网页抓取均失败。[/bold red]")
        raise typer.Exit(code=1)

    # Render results
    rendered_parts: list[str] = []
    for u, res in results:
        if format_ == FetchFormat.MARKDOWN:
            format_fetch_result_rich(fetch=res, url=u)
            rendered_parts.append(f"# {res.title or '无标题'}\n\n来源: {u}\n\n{res.content}")
        elif format_ == FetchFormat.RAW:
            console.print(res.content)
            rendered_parts.append(res.content)
        elif format_ == FetchFormat.JSON:
            json_text = format_fetch_result_json(res, url=u)
            console.print(json_text)
            rendered_parts.append(json_text)

    if output:
        try:
            save_content = "\n\n---\n\n".join(rendered_parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(save_content, encoding="utf-8")
            err_console.print(f"\n[bold green]✓ 抓取内容已保存至:[/bold green] {output.resolve()}")
        except OSError as e:
            err_console.print(f"[bold red]写入文件失败:[/bold red] {e}")
            raise typer.Exit(code=1)


config_app = typer.Typer(
    help="管理 DeepSeek API 认证凭据与配置参数",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")
app.add_typer(skills_app, name="skills")


@app.command("install-skill", help="快捷命令：将 deepseek-search 技能安装至 AI Agent 平台")
def install_skill_alias(
    target: Annotated[
        str,
        typer.Option(
            "--target",
            "-t",
            help="目标 AI Agent 平台，支持: all, antigravity, claude, cursor, codex, crush",
        ),
    ] = "all",
    global_install: Annotated[
        bool,
        typer.Option(
            "--global/--local",
            help="安装到用户全局配置 (默认) 还是当前项目本地",
        ),
    ] = True,
) -> None:
    install_skills(target=target, global_install=global_install)


def _save_key_action(
    key: str | None,
    local: bool = False,
    base_url: str | None = None,
    check: bool = True,
) -> None:
    """Core logic to prompt, validate, and save API key."""
    if not key:
        key = typer.prompt("请输入 DeepSeek API Key", hide_input=True)

    clean_key = key.strip()
    if not clean_key:
        err_console.print("[bold red]错误:[/bold red] API Key 不能为空。")
        raise typer.Exit(code=1)

    effective_base = resolve_base_url(base_url)

    if check:
        with status_spinner("[cyan]正在向 DeepSeek API 校验 Key 有效性...[/cyan]"):
            is_valid, msg = DeepSeekClient.verify(clean_key, effective_base)
        if not is_valid:
            err_console.print(f"[bold red]✗ 校验失败:[/bold red] {msg}")
            if not typer.confirm("是否仍要强行保存此 Key？", default=False):
                raise typer.Exit(code=1)
        else:
            console.print(f"[bold green]✓[/bold green] {msg}")

    if local:
        env_path = save_local_env(api_key=clean_key, base_url=base_url)
        console.print(f"[bold green]✓ API Key 已保存至本地项目:[/bold green] {env_path.resolve()}")
    else:
        updates: dict[str, str] = {"api_key": clean_key}
        if base_url:
            updates["base_url"] = base_url.strip()
        save_file_config(updates)
        cfg_path = get_config_file()
        console.print(f"[bold green]✓ API Key 已保存至全局配置:[/bold green] {cfg_path.resolve()}")


@config_app.command("login", help="配置并保存 DeepSeek API Key (可省略参数以安全交互输入)")
def config_login(
    key: Annotated[
        str | None,
        typer.Argument(
            help="DeepSeek API Key (如不传将以密码掩码方式交互式输入)",
        ),
    ] = None,
    local: Annotated[
        bool,
        typer.Option(
            "--local",
            "-l",
            help="保存到当前工作目录的 .env 文件（默认保存到全局配置）",
        ),
    ] = False,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help="同步设置 Base URL (可选)",
        ),
    ] = None,
    check: Annotated[
        bool,
        typer.Option(
            "--check/--no-check",
            help="保存前是否在线向 DeepSeek API 校验 Key 的有效性",
        ),
    ] = True,
) -> None:
    _save_key_action(key=key, local=local, base_url=base_url, check=check)


@config_app.command("status", help="检查当前生效的 API Key 凭证、来源与连通性")
def config_status() -> None:
    current_key, source = get_api_key_source()
    current_base = resolve_base_url()

    console.print("[bold cyan]DeepSeek 认证与配置状态：[/bold cyan]")
    console.print(f"  • [bold]配置来源:[/bold] {source}")
    console.print(f"  • [bold]Base URL:[/bold] {current_base}")

    if not current_key:
        console.print("  • [bold]API Key 状态:[/bold] [red]未配置[/red]")
        console.print(
            "\n[yellow]提示: 请运行 'deepseek-search config login' 设置 API Key。[/yellow]"
        )
        return

    masked_key = current_key[:7] + "..." + current_key[-4:] if len(current_key) > 12 else "***"
    console.print(f"  • [bold]当前 API Key:[/bold] {masked_key}")

    with status_spinner("[cyan]正在测试与 DeepSeek API 的连通性与鉴权状态...[/cyan]"):
        is_valid, msg = DeepSeekClient.verify(current_key, current_base)

    if is_valid:
        console.print(f"  • [bold]鉴权状态:[/bold] [bold green]✓ 有效 ({msg})[/bold green]")
    else:
        console.print(f"  • [bold]鉴权状态:[/bold] [bold red]✗ 异常 ({msg})[/bold red]")


@config_app.command("logout", help="清除已保存的全局 API Key 配置")
def config_logout() -> None:
    cfg = load_file_config()
    if "api_key" in cfg:
        del cfg["api_key"]
        get_config_file().write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        console.print("[bold green]✓ 全局配置文件中的 API Key 已清除。[/bold green]")
    else:
        console.print("[yellow]全局配置文件中未保存 API Key。[/yellow]")


@config_app.command("set", help="设置并保存 API Key 或 Base URL 到用户配置文件")
def config_set(
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help="要保存的 DeepSeek API Key"),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option("--base-url", help="要保存的 DeepSeek Base URL"),
    ] = None,
    local: Annotated[
        bool,
        typer.Option(
            "--local",
            "-l",
            help="保存到当前工作目录的 .env 文件（默认保存到全局配置）",
        ),
    ] = False,
) -> None:
    if api_key is None and base_url is None:
        console.print("[yellow]未指定任何配置项，请提供 --api-key 或 --base-url。[/yellow]")
        return

    if local:
        if api_key:
            env_file = save_local_env(api_key=api_key, base_url=base_url)
            console.print(f"[bold green]✓ 本地 .env 已更新:[/bold green] {env_file.resolve()}")
        elif base_url:
            env_file = save_local_env(api_key=resolve_api_key(), base_url=base_url)
            console.print(
                f"[bold green]✓ 本地 .env 已更新 Base URL:[/bold green] {env_file.resolve()}"
            )
    else:
        updates: dict[str, str] = {}
        if api_key is not None:
            updates["api_key"] = api_key.strip()
        if base_url is not None:
            updates["base_url"] = base_url.strip()
        save_file_config(updates)
        cfg_file = get_config_file()
        console.print(f"[bold green]✓ 全局配置已更新并保存至:[/bold green] {cfg_file.resolve()}")


@config_app.command("show", help="查看当前生效的配置与配置文件路径")
def config_show() -> None:
    cfg_file = get_config_file()
    current_key, source = get_api_key_source()
    current_base = resolve_base_url()

    if current_key:
        masked_key = current_key[:7] + "..." + current_key[-4:] if len(current_key) > 12 else "***"
    else:
        masked_key = "[red](未配置)[/red]"

    console.print("[bold cyan]DeepSeek Search CLI 配置信息：[/bold cyan]")
    console.print(f"  • [bold]全局配置文件路径:[/bold] {cfg_file.resolve()}")
    console.print(
        f"  • [bold]全局配置是否存在:[/bold] {'[green]是[/green]' if cfg_file.is_file() else '[yellow]否[/yellow]'}"
    )
    console.print(f"  • [bold]当前生效 Base URL:[/bold] {current_base}")
    console.print(f"  • [bold]当前生效 API Key:[/bold] {masked_key}")
    console.print(f"  • [bold]生效配置来源:[/bold] {source}")
    blacklist = resolve_blacklist()
    if blacklist:
        console.print(f"  • [bold]排除站点黑名单:[/bold] {', '.join(blacklist)}")
    else:
        console.print("  • [bold]排除站点黑名单:[/bold] [dim](未配置)[/dim]")


@config_app.command("path", help="显示配置文件的绝对路径")
def config_path() -> None:
    console.print(str(get_config_file().resolve()))


blacklist_app = typer.Typer(
    help="管理默认排除的站点黑名单 (例如排除 csdn.net)",
    no_args_is_help=False,
)
config_app.add_typer(blacklist_app, name="blacklist")


@blacklist_app.callback(invoke_without_command=True)
def blacklist_main(ctx: typer.Context) -> None:
    """查看当前生效的搜索站点黑名单。"""
    if ctx.invoked_subcommand is None:
        blacklist = resolve_blacklist()
        if not blacklist:
            console.print("[yellow]当前未配置任何排除站点黑名单。[/yellow]")
            console.print(
                "[dim]提示: 可运行 'deepseek-search config blacklist default' 一键应用推荐黑名单。[/dim]"
            )
            return

        console.print(f"[bold cyan]当前搜索站点黑名单 ({len(blacklist)} 个)：[/bold cyan]")
        for d in blacklist:
            console.print(f"  • [red]-site:{d}[/red]")


@blacklist_app.command("list", help="查看所有已配置的黑名单站点")
def blacklist_list() -> None:
    blacklist = resolve_blacklist()
    if not blacklist:
        console.print("[yellow]当前未配置任何排除站点黑名单。[/yellow]")
        return
    console.print(f"[bold cyan]当前搜索站点黑名单 ({len(blacklist)} 个)：[/bold cyan]")
    for d in blacklist:
        console.print(f"  • [red]-site:{d}[/red]")


@blacklist_app.command("add", help="添加一个或多个站点域名至黑名单 (例如 csdn.net)")
def blacklist_add(
    domains: Annotated[
        list[str],
        typer.Argument(help="要排除的站点域名 (例如 csdn.net，支持传入多个)"),
    ],
) -> None:
    added: list[str] = []
    for d in domains:
        try:
            add_to_blacklist(d)
            added.append(clean_domain_name(d))
        except ValueError as e:
            err_console.print(f"[bold red]错误:[/bold red] {e}")

    if added:
        console.print(f"[bold green]✓ 成功将以下站点添加至黑名单:[/bold green] {', '.join(added)}")
        console.print(
            f"[dim]已保存至 {get_config_file()}，未来所有搜索将默认附加 -site 自动排除。[/dim]"
        )


@blacklist_app.command("remove", help="从黑名单中移除指定的站点域名")
def blacklist_remove(
    domains: Annotated[
        list[str],
        typer.Argument(help="要移除的站点域名 (例如 csdn.net)"),
    ],
) -> None:
    removed: list[str] = []
    for d in domains:
        remove_from_blacklist(d)
        removed.append(clean_domain_name(d))
    console.print(f"[bold green]✓ 已从黑名单中移除:[/bold green] {', '.join(removed)}")


@blacklist_app.command("clear", help="清空所有的站点黑名单")
def blacklist_clear() -> None:
    clear_blacklist()
    console.print("[bold green]✓ 站点黑名单已清空。[/bold green]")


@blacklist_app.command(
    "default",
    help=f"一键应用推荐默认黑名单 ({', '.join(DEFAULT_BLACKLIST)})",
)
def blacklist_default() -> None:
    sites = set_default_blacklist()
    console.print(f"[bold green]✓ 成功应用推荐默认黑名单 ({len(sites)} 个)：[/bold green]")
    for s in sites:
        console.print(f"  • [red]-site:{s}[/red]")
    console.print(
        f"[dim]已保存至 {get_config_file()}，后续搜索将默认自动排除上述站点。[/dim]"
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
