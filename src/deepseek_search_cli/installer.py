from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from deepseek_search_cli.formatters import console, err_console

skills_app = typer.Typer(
    name="skills",
    help="管理并安装 AI Coding Agent 技能 (Skills)",
    no_args_is_help=True,
)

SUPPORTED_TARGETS = ("antigravity", "claude", "cursor", "codex", "crush")


def _get_skill_source_path() -> Path:
    """Retrieve the path to the bundled SKILL.md."""
    # 1. Package resources directory
    pkg_res = Path(__file__).parent / "resources" / "skills" / "deepseek-search" / "SKILL.md"
    if pkg_res.is_file():
        return pkg_res.resolve()

    # 2. Workspace root fallback (relative to src/deepseek_search_cli/installer.py)
    ws_fallback = (
        Path(__file__).parent.parent.parent / "skills" / "deepseek-search" / "SKILL.md"
    ).resolve()
    if ws_fallback.is_file():
        return ws_fallback

    # 3. Current working directory fallback
    cwd_fallback = (Path.cwd() / "skills" / "deepseek-search" / "SKILL.md").resolve()
    if cwd_fallback.is_file():
        return cwd_fallback

    raise FileNotFoundError("未找到 deepseek-search 的技能源文件 (SKILL.md)。")


def get_target_destinations(
    target_names: list[str],
    global_install: bool = True,
    home_dir: Path | None = None,
    cwd_dir: Path | None = None,
) -> list[tuple[str, Path]]:
    """Resolve installation paths for specified agent platforms."""
    home = (home_dir or Path.home()).resolve()
    cwd = (cwd_dir or Path.cwd()).resolve()

    dests: list[tuple[str, Path]] = []
    skill_subpath = Path("deepseek-search") / "SKILL.md"

    for t in target_names:
        if t in ("antigravity", "gemini"):
            base = (
                home / ".gemini" / "config" / "skills"
                if global_install
                else cwd / ".agents" / "skills"
            )
            dests.append(("Antigravity / Gemini", base / skill_subpath))
        elif t == "claude":
            base = home / ".claude" / "skills" if global_install else cwd / ".claude" / "skills"
            dests.append(("Claude Code", base / skill_subpath))
        elif t == "cursor":
            base = home / ".cursor" / "skills" if global_install else cwd / ".cursor" / "skills"
            dests.append(("Cursor", base / skill_subpath))
        elif t == "codex":
            base = home / ".codex" / "skills" if global_install else cwd / ".codex" / "skills"
            dests.append(("Codex", base / skill_subpath))
        elif t == "crush":
            base = (
                home / ".config" / "crush" / "skills"
                if global_install
                else cwd / ".crush" / "skills"
            )
            dests.append(("Crush", base / skill_subpath))

    return dests


@skills_app.command("install", help="将 deepseek-search 技能安装至指定的 AI Agent 平台")
def install_skills(
    target: Annotated[
        str,
        typer.Option(
            "--target",
            "-t",
            help="目标 AI Agent 平台，支持: all, antigravity, claude, cursor, codex, crush (支持逗号分隔)",
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
    """Install deepseek-search agent skills for supported AI agent platforms."""
    try:
        skill_src = _get_skill_source_path()
        skill_content = skill_src.read_text(encoding="utf-8")
    except Exception as e:
        err_console.print(f"[bold red]读取技能模板失败:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Resolve target list
    req = [x.strip().lower() for x in target.split(",") if x.strip()]
    if "all" in req:
        targets = list(SUPPORTED_TARGETS)
    else:
        targets = [t for t in SUPPORTED_TARGETS if t in req]

    if not targets:
        err_console.print(
            f"[bold red]错误:[/bold red] 无效的平台目标 '{target}'。支持选项: all, {', '.join(SUPPORTED_TARGETS)}"
        )
        raise typer.Exit(code=1)

    destinations = get_target_destinations(targets, global_install=global_install)
    installed_count = 0

    mode_str = "全局 (User-level)" if global_install else "本地项目 (Project-level)"
    console.print(f"[bold cyan]正在安装 deepseek-search 技能 ({mode_str})...[/bold cyan]\n")

    for platform_name, dest_file in destinations:
        try:
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            dest_file.write_text(skill_content, encoding="utf-8")
            console.print(f"  [bold green]✓[/bold green] [bold]{platform_name}[/bold]: {dest_file}")
            installed_count += 1
        except OSError as e:
            err_console.print(
                f"  [bold red]✗[/bold red] [bold]{platform_name}[/bold] 安装失败: {e}"
            )

    if installed_count > 0:
        console.print(
            f"\n[bold green]成功为 {installed_count} 个 AI Agent 平台安装 deepseek-search 技能！[/bold green]"
        )
        console.print("[dim]在对应 Agent 中，AI 将自动发现并调用该技能进行网络搜索与抓取。[/dim]")
    else:
        err_console.print("\n[bold red]未成功安装任何技能配置。[/bold red]")
        raise typer.Exit(code=1)
