from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_BLACKLIST: list[str] = [
    "csdn.net",
]


def get_config_dir() -> Path:
    """Get configuration directory conforming to XDG standards."""
    xdg_config = os.getenv("XDG_CONFIG_HOME")
    if xdg_config:
        base = Path(xdg_config)
    else:
        base = Path.home() / ".config"
    return base / "deepseek-search"


def get_config_file() -> Path:
    return get_config_dir() / "config.json"


def load_file_config() -> dict[str, Any]:
    config_file = get_config_file()
    if config_file.is_file():
        try:
            return json.loads(config_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_file_config(data: dict[str, Any]) -> None:
    config_file = get_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    existing = load_file_config()
    existing.update(data)
    config_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(config_file, 0o600)
    except OSError:
        pass


def find_dotenv_path() -> Path | None:
    """Find .env file in current or parent directories."""
    curr = Path.cwd().resolve()
    for directory in [curr, *curr.parents]:
        env_file = directory / ".env"
        if env_file.is_file():
            return env_file
    return None


def save_local_env(api_key: str, base_url: str | None = None) -> Path:
    """Save or update DEEPSEEK_API_KEY (and optional DEEPSEEK_BASE_URL) in local .env."""
    env_file = Path.cwd() / ".env"
    existing_lines = []
    if env_file.is_file():
        existing_lines = env_file.read_text(encoding="utf-8").splitlines()

    new_lines = []
    key_written = False
    url_written = False

    for line in existing_lines:
        trimmed = line.strip()
        if trimmed.startswith("DEEPSEEK_API_KEY="):
            new_lines.append(f"DEEPSEEK_API_KEY={api_key}")
            key_written = True
        elif base_url and trimmed.startswith("DEEPSEEK_BASE_URL="):
            new_lines.append(f"DEEPSEEK_BASE_URL={base_url}")
            url_written = True
        else:
            new_lines.append(line)

    if not key_written:
        new_lines.append(f"DEEPSEEK_API_KEY={api_key}")
    if base_url and not url_written:
        new_lines.append(f"DEEPSEEK_BASE_URL={base_url}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    try:
        os.chmod(env_file, 0o600)
    except OSError:
        pass
    return env_file


def load_dotenv_if_exists() -> Path | None:
    """Search for .env in current and parent directories and load variables if not already set."""
    env_file = find_dotenv_path()
    if env_file:
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key not in os.environ and val:
                    os.environ[key] = val
            return env_file
        except OSError:
            pass
    return None


def resolve_api_key(cli_key: str | None = None) -> str:
    """Resolve API key following priority: CLI arg -> env var -> .env -> config.json."""
    if cli_key and cli_key.strip():
        return cli_key.strip()

    load_dotenv_if_exists()

    env_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if env_key:
        return env_key

    file_cfg = load_file_config()
    cfg_key = str(file_cfg.get("api_key", "")).strip()
    if cfg_key:
        return cfg_key

    return ""


def get_api_key_source(cli_key: str | None = None) -> tuple[str, str]:
    """Return tuple of (api_key, source_description)."""
    if cli_key and cli_key.strip():
        return cli_key.strip(), "CLI 参数 (--api-key)"

    if "DEEPSEEK_API_KEY" in os.environ and os.environ["DEEPSEEK_API_KEY"].strip():
        return os.environ["DEEPSEEK_API_KEY"].strip(), "系统环境变量 (DEEPSEEK_API_KEY)"

    env_file = load_dotenv_if_exists()
    if env_file and "DEEPSEEK_API_KEY" in os.environ and os.environ["DEEPSEEK_API_KEY"].strip():
        return os.environ["DEEPSEEK_API_KEY"].strip(), f"本地 .env 文件 ({env_file})"

    file_cfg = load_file_config()
    cfg_key = str(file_cfg.get("api_key", "")).strip()
    if cfg_key:
        return cfg_key, f"全局配置文件 ({get_config_file()})"

    return "", "未配置"


def resolve_base_url(cli_url: str | None = None) -> str:
    """Resolve base URL following priority: CLI arg -> env var -> .env -> config.json -> default."""
    if cli_url and cli_url.strip():
        return cli_url.strip().rstrip("/")

    load_dotenv_if_exists()

    env_url = os.getenv("DEEPSEEK_BASE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")

    file_cfg = load_file_config()
    cfg_url = str(file_cfg.get("base_url", "")).strip()
    if cfg_url:
        return cfg_url.rstrip("/")

    return DEFAULT_BASE_URL


def clean_domain_name(domain: str) -> str:
    """Clean and extract host domain from user input (e.g. 'https://csdn.net/foo' -> 'csdn.net')."""
    d = domain.strip().lower()
    if d.startswith(("http://", "https://")):
        d = d.split("://", 1)[1]
    return d.split("/")[0].split(":")[0]


def resolve_blacklist() -> list[str]:
    """Resolve persistent blacklist of excluded sites.

    Precedence:
    1. DEEPSEEK_EXCLUDE_SITES env var (comma-separated)
    2. Global config file (key: 'exclude_sites', list of strings)
    """
    load_dotenv_if_exists()
    env_blacklist = os.getenv("DEEPSEEK_EXCLUDE_SITES", "").strip()
    if env_blacklist:
        return [clean_domain_name(s) for s in env_blacklist.split(",") if s.strip()]

    file_cfg = load_file_config()
    cfg_blacklist = file_cfg.get("exclude_sites")
    if isinstance(cfg_blacklist, list):
        return [clean_domain_name(str(s)) for s in cfg_blacklist if str(s).strip()]
    elif isinstance(cfg_blacklist, str) and cfg_blacklist.strip():
        return [clean_domain_name(s) for s in cfg_blacklist.split(",") if s.strip()]

    return []


def add_to_blacklist(domain: str) -> list[str]:
    """Add a domain to global blacklist in config.json."""
    clean_d = clean_domain_name(domain)
    if not clean_d:
        raise ValueError("域名不能为空。")
    current = resolve_blacklist()
    if clean_d not in current:
        current.append(clean_d)
        save_file_config({"exclude_sites": current})
    return current


def remove_from_blacklist(domain: str) -> list[str]:
    """Remove a domain from global blacklist in config.json."""
    clean_d = clean_domain_name(domain)
    current = resolve_blacklist()
    if clean_d in current:
        current.remove(clean_d)
        save_file_config({"exclude_sites": current})
    return current


def clear_blacklist() -> None:
    """Clear all domains in global blacklist."""
    cfg = load_file_config()
    if "exclude_sites" in cfg:
        del cfg["exclude_sites"]
        config_file = get_config_file()
        config_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def set_default_blacklist() -> list[str]:
    """Set the global blacklist to the recommended default list."""
    save_file_config({"exclude_sites": list(DEFAULT_BLACKLIST)})
    return list(DEFAULT_BLACKLIST)
