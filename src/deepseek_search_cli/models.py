from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SearchResult:
    """Represents a single search result from DeepSeek Search API."""

    rerank_score: float
    title: str
    url: str
    snippet: str
    summary: str
    content: str = ""
    site_name: str | None = None
    site_icon: str | None = None
    date: str | None = None
    authority: int = -1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchResult:
        return cls(
            rerank_score=float(data.get("rerank_score", 0.0)),
            title=str(data.get("title", "")),
            url=str(data.get("url", "")),
            snippet=str(data.get("snippet", "")),
            summary=str(data.get("summary", "")),
            content=str(data.get("content", "") or ""),
            site_name=data.get("site_name"),
            site_icon=data.get("site_icon"),
            date=data.get("date"),
            authority=int(data.get("authority", -1)),
        )

    @property
    def is_high_quality(self) -> bool:
        """Score >= 1.5 indicates a high-quality result according to DeepSeek documentation."""
        return self.rerank_score >= 1.5

    @property
    def is_highly_authoritative(self) -> bool:
        """Authority >= 3 indicates an extremely authoritative source."""
        return self.authority >= 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResponse:
    """Represents the response from DeepSeek Search API."""

    results: list[SearchResult]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchResponse:
        raw_results = data.get("results", [])
        return cls(results=[SearchResult.from_dict(item) for item in raw_results])

    def to_dict(self) -> dict[str, Any]:
        return {"results": [r.to_dict() for r in self.results]}


@dataclass
class FetchResponse:
    """Represents the response from DeepSeek Fetch API."""

    title: str
    content: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FetchResponse:
        return cls(
            title=str(data.get("title", "")),
            content=str(data.get("content", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
