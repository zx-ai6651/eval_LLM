import re
from typing import Any


URL_RE = re.compile(r"^https?://", flags=re.I)


def normalize_source(source: dict[str, Any], index: int = 1, default_source: str = "other") -> dict[str, Any]:
    source_id = str(source.get("source_id") or source.get("id") or f"S{index}")
    return {
        "source_id": source_id,
        "title": str(source.get("title") or source.get("name") or source.get("url") or ""),
        "url": str(source.get("url") or source.get("link") or source.get("href") or ""),
        "snippet": str(source.get("snippet") or source.get("content") or source.get("text") or ""),
        "published_date": str(source.get("published_date") or source.get("date") or ""),
        "source_type": str(source.get("source_type") or _infer_source_type(source) or default_source),
        "source": str(source.get("source") or default_source),
        "query": str(source.get("query") or ""),
        "rank": int(source.get("rank") or index),
    }


def normalize_sources(
    sources: list[dict[str, Any]] | None,
    default_source: str = "other",
    preserve_source_ids: bool = False,
) -> list[dict[str, Any]]:
    normalized = []
    for index, source in enumerate(sources or [], start=1):
        if not isinstance(source, dict):
            continue
        normalized.append(normalize_source(source, index=index, default_source=default_source))
    deduped = dedupe_sources(normalized)
    return deduped if preserve_source_ids else reassign_source_ids(deduped)


def dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        key = (str(source.get("url") or "").strip(), str(source.get("title") or "").strip())
        if key == ("", "") or key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def reassign_source_ids(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index, source in enumerate(sources, start=1):
        source["source_id"] = f"S{index}"
    return sources


def valid_url_count(sources: list[dict[str, Any]]) -> int:
    return sum(1 for source in sources if URL_RE.match(str(source.get("url") or "")))


def _infer_source_type(source: dict[str, Any]) -> str:
    url = str(source.get("url") or "").lower()
    if any(domain in url for domain in [".gov", "gov.cn", "samr.gov.cn", "court.gov.cn", "chinatax.gov.cn"]):
        return "official"
    if any(domain in url for domain in ["qcc.com", "tianyancha.com", "cninfo.com.cn", "neeq.com.cn"]):
        return "database"
    if any(domain in url for domain in ["news", "finance", "sina.com", "163.com", "qq.com", "thepaper.cn"]):
        return "media"
    return ""
