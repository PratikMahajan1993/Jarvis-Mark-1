from __future__ import annotations

from typing import Any

import httpx

from ..config import settings


def search_web(query: str, limit: int = 5) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    if settings.tavily_api_key:
        return _tavily(query, limit)
    if settings.brave_api_key:
        return _brave(query, limit)
    return _duckduckgo(query, limit)


def _tavily(query: str, limit: int) -> list[dict[str, Any]]:
    response = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": settings.tavily_api_key, "query": query, "max_results": limit},
        timeout=20,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:400],
        }
        for item in results[:limit]
    ]


def _brave(query: str, limit: int) -> list[dict[str, Any]]:
    response = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": limit},
        headers={"Accept": "application/json", "X-Subscription-Token": settings.brave_api_key},
        timeout=20,
    )
    response.raise_for_status()
    web = response.json().get("web", {}).get("results", [])
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("description", "")[:400],
        }
        for item in web[:limit]
    ]


def _duckduckgo(query: str, limit: int) -> list[dict[str, Any]]:
    try:
        from ddgs import DDGS

        rows = DDGS().text(query, max_results=limit)
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("href") or item.get("url", ""),
                "snippet": item.get("body", "")[:400],
            }
            for item in rows[:limit]
        ]
    except Exception as exc:
        return [
            {
                "title": "Search unavailable",
                "url": "",
                "snippet": f"DuckDuckGo fallback failed: {exc}. Add TAVILY_API_KEY or BRAVE_API_KEY.",
            }
        ]
