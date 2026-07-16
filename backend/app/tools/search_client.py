import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class SearchItem:
    title: str
    url: str
    snippet: str
    published_date: str = ""
    source: str = ""
    query: str = ""
    rank: int = 0


@dataclass
class SearchResult:
    success: bool
    items: list[SearchItem]
    duration_ms: int
    error_message: str = ""


class SearchClient:
    """Optional external search provider.

    Default web search is handled by Bailian built-in Chat Completions search.
    This client is only used when SEARCH_PROVIDER is explicitly set to tavily or serper.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, query: str, limit: int = 5, language: str = "zh-CN") -> SearchResult:
        provider = self.settings.search_provider.lower()
        if provider == "tavily" and self.settings.tavily_api_key:
            return await self._search_tavily(query, limit)
        if provider == "serper" and self.settings.serper_api_key:
            return await self._search_serper(query, limit, language)
        return self._mock_search(query, limit, provider)

    async def _search_tavily(self, query: str, limit: int) -> SearchResult:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": self.settings.tavily_api_key, "query": query, "max_results": limit},
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            return SearchResult(False, [], int((time.perf_counter() - started) * 1000), str(exc))
        items = [
            SearchItem(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source="tavily",
                query=query,
                rank=index + 1,
            )
            for index, item in enumerate(data.get("results", []))
        ]
        return SearchResult(True, items, int((time.perf_counter() - started) * 1000))

    async def _search_serper(self, query: str, limit: int, language: str) -> SearchResult:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": self.settings.serper_api_key},
                    json={"q": query, "num": limit, "hl": language},
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            return SearchResult(False, [], int((time.perf_counter() - started) * 1000), str(exc))
        items = [
            SearchItem(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                published_date=item.get("date", ""),
                source="serper",
                query=query,
                rank=index + 1,
            )
            for index, item in enumerate(data.get("organic", [])[:limit])
        ]
        return SearchResult(True, items, int((time.perf_counter() - started) * 1000))

    def _mock_search(self, query: str, limit: int, provider: str) -> SearchResult:
        started = time.perf_counter()
        items = [
            SearchItem(
                title=f"演示外部搜索结果 {index + 1}",
                url=f"https://example.com/search-result-{index + 1}",
                snippet=f"这是针对 `{query}` 的演示摘要。当前外部搜索供应商 `{provider}` 未配置可用 API Key。",
                published_date="",
                source="mock_external_search",
                query=query,
                rank=index + 1,
            )
            for index in range(max(1, min(limit, 5)))
        ]
        return SearchResult(True, items, int((time.perf_counter() - started) * 1000))
