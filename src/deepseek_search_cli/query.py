from __future__ import annotations


def build_search_query(
    query: str,
    site: list[str] | None = None,
    exclude_site: list[str] | None = None,
    lang: str | None = None,
    after: str | None = None,
    before: str | None = None,
) -> str:
    """Build an augmented search query string incorporating DeepSeek search operators.

    Operators supported according to DeepSeek documentation:
    - site:domain.com (multiple separated by space and OR)
    - -site:domain.com
    - lang:zh,en
    - after:YYYY or after:YYYY-MM-DD
    - before:YYYY or before:YYYY-MM-DD
    """
    parts = [query.strip()]

    if site:
        site_filters = [f"site:{s.strip()}" for s in site if s.strip()]
        if site_filters:
            parts.append(" OR ".join(site_filters))

    if exclude_site:
        for s in exclude_site:
            if s.strip():
                parts.append(f"-site:{s.strip()}")

    if lang and lang.strip():
        parts.append(f"lang:{lang.strip()}")

    if after and after.strip():
        parts.append(f"after:{after.strip()}")

    if before and before.strip():
        parts.append(f"before:{before.strip()}")

    return " ".join(parts).strip()
