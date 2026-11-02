"""DeepSeek Search and Fetch CLI tool based on httpx and typer."""

__version__ = "1.0.1"

from deepseek_search_cli.client import (
    DeepSeekAPIError,
    DeepSeekClient,
    normalize_url,
)
from deepseek_search_cli.models import FetchResponse, SearchResponse, SearchResult
from deepseek_search_cli.query import build_search_query

__all__ = [
    "DeepSeekAPIError",
    "DeepSeekClient",
    "FetchResponse",
    "SearchResponse",
    "SearchResult",
    "__version__",
    "build_search_query",
    "normalize_url",
]
