from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import settings
from ..tables import html_to_text

_UA = "Mozilla/5.0 (compatible; JarvisHUD/0.1; +http://localhost)"
_SKIP_LINE = re.compile(
    r"cookie|privacy policy|sign in|subscribe|newsletter|all rights reserved|"
    r"javascript required|enter search text|english edition|skip to |download app|"
    r"benchmarks nifty|precious metal gold|you are being redirected",
    re.I,
)
_JSISH = re.compile(
    r"\b(var |const |let |function |window\.|document\.|dataLayer|gtag\(|boomr|jQuery)\b|[{};]{3,}"
)
_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.S)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_NOSCRIPT = re.compile(r"<noscript\b[^>]*>.*?</noscript>", re.I | re.S)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_PREFIX = re.compile(
    r"^(?:(?:hey|ok|okay|hi|hello)\s+)?(?:jarvis|jarvish)\b[\s,.:]*",
    re.I,
)
_ASK = re.compile(
    r"\b(?:please\s+)?(?:can you|could you|would you)?\s*"
    r"(?:research|look(?:\s+this)?\s+up|look\s+into|"
    r"search(?:\s+the(?:\s+web)?)?(?:\s+for)?(?:\s+current|\s+latest)?|"
    r"google(?:\s+this)?|find(?:\s+out)?(?:\s+about)?(?:\s+online)?|what(?:'s| is) the latest on)\b[:\s]*",
    re.I,
)


def clean_query(raw: str) -> str:
    text = (raw or "").strip()
    text = _PREFIX.sub("", text).strip()
    text = _ASK.sub("", text).strip(" .,:;?-")
    return text or (raw or "").strip()


_OUTLETS = {
    "economictimes.indiatimes.com": "Economic Times",
    "moneycontrol.com": "Moneycontrol",
    "goldpriceindia.com": "Gold Price India",
    "nalcoindia.com": "NALCO",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "livemint.com": "Mint",
    "business-standard.com": "Business Standard",
    "hindustantimes.com": "Hindustan Times",
    "thehindu.com": "The Hindu",
    "indiatimes.com": "Times of India",
    "wikipedia.org": "Wikipedia",
}


def outlet_name(url_or_host: str) -> str:
    host = host_name(url_or_host) if "://" in (url_or_host or "") else (url_or_host or "")
    host = host.lower()
    if host in _OUTLETS:
        return _OUTLETS[host]
    for suffix, name in _OUTLETS.items():
        if host.endswith(suffix):
            return name
    label = host.split(".")[0].replace("-", " ").strip()
    return label.title() if label else "A source"


def notes_for_model(brief: dict[str, Any], limit: int = 5) -> str:
    lines: list[str] = []
    for hit in (brief.get("hits") or [])[:limit]:
        who = outlet_name(hit.get("url") or hit.get("site") or "")
        note = _clip(hit.get("note") or "") or _clip(hit.get("snippet") or "")
        if not note:
            continue
        lines.append(f"{who}: {note}")
    return "\n".join(lines)


def search_web(query: str, limit: int = 5) -> dict[str, Any]:
    query = clean_query(query)
    if not query:
        return {"query": "", "engine": "", "answer": "", "hits": []}
    if settings.google_cse_api_key and settings.google_cse_cx:
        packed = _safe("google", lambda: _google(query, limit))
        if packed:
            return packed
    if settings.tavily_api_key:
        packed = _safe("tavily", lambda: _tavily(query, limit))
        if packed:
            return packed
    if settings.brave_api_key:
        packed = _safe("brave", lambda: _brave(query, limit))
        if packed:
            return packed
    return _safe("duckduckgo", lambda: _duckduckgo(query, limit)) or {
        "query": query,
        "engine": "none",
        "answer": "",
        "hits": [],
    }


def brief_research(query: str, limit: int = 5) -> dict[str, Any]:
    packed = search_web(query, limit)
    hits = list(packed.get("hits") or [])
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(hits)))) as pool:
        futures = {pool.submit(_annotate, hit): hit for hit in hits}
        for future in as_completed(futures):
            hit = futures[future]
            try:
                hit["note"] = future.result()
            except Exception:
                hit["note"] = _clip(hit.get("snippet") or "")
    answer = (packed.get("answer") or "").strip()
    if not answer:
        answer = _takeaway(query, hits)
    return {
        "query": packed.get("query") or query,
        "engine": packed.get("engine") or "",
        "answer": answer,
        "hits": hits,
    }


def _safe(engine: str, fn: Any) -> dict[str, Any] | None:
    try:
        packed = fn()
    except Exception:
        return None
    if not packed.get("hits"):
        return None
    packed["engine"] = engine
    return packed


def _pack(query: str, hits: list[dict[str, Any]], answer: str = "") -> dict[str, Any]:
    return {"query": query, "answer": (answer or "").strip(), "hits": hits}


def _hit(title: str, url: str, snippet: str) -> dict[str, Any]:
    return {
        "title": (title or "").strip() or host_name(url) or "Source",
        "url": (url or "").strip(),
        "snippet": (snippet or "").strip()[:400],
        "site": host_name(url),
        "note": "",
    }


def host_name(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0]


def _google(query: str, limit: int) -> dict[str, Any]:
    response = httpx.get(
        "https://www.googleapis.com/customsearch/v1",
        params={
            "key": settings.google_cse_api_key,
            "cx": settings.google_cse_cx,
            "q": query,
            "num": min(max(limit, 1), 10),
        },
        timeout=20,
    )
    response.raise_for_status()
    items = response.json().get("items") or []
    hits = [_hit(item.get("title", ""), item.get("link", ""), item.get("snippet", "")) for item in items[:limit]]
    return _pack(query, hits)


def _tavily(query: str, limit: int) -> dict[str, Any]:
    response = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": limit,
            "include_answer": True,
            "search_depth": "advanced",
        },
        timeout=25,
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results") or []
    hits = [_hit(item.get("title", ""), item.get("url", ""), item.get("content", "")[:400]) for item in results[:limit]]
    return _pack(query, hits, str(data.get("answer") or ""))


def _brave(query: str, limit: int) -> dict[str, Any]:
    response = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": limit},
        headers={"Accept": "application/json", "X-Subscription-Token": settings.brave_api_key},
        timeout=20,
    )
    response.raise_for_status()
    web = response.json().get("web", {}).get("results", [])
    hits = [_hit(item.get("title", ""), item.get("url", ""), item.get("description", "")) for item in web[:limit]]
    return _pack(query, hits)


def _duckduckgo(query: str, limit: int) -> dict[str, Any]:
    from ddgs import DDGS

    rows = DDGS().text(query, max_results=limit)
    hits = [
        _hit(item.get("title", ""), item.get("href") or item.get("url", ""), item.get("body", ""))
        for item in rows[:limit]
    ]
    return _pack(query, hits)


def _annotate(hit: dict[str, Any]) -> str:
    snippet = _clip(hit.get("snippet") or "")
    page = _clip(_fetch_text(hit.get("url") or ""), 280)
    if _quality(page) >= _quality(snippet) and page:
        return page
    return snippet or page


def _quality(text: str) -> int:
    if not text or _looks_junk(text):
        return -1
    score = 0
    if re.search(r"(rs\.?|₹|usd|%|\bprice\b|\brate\b|\bper\b|\bsaid\b|\breport)", text, re.I):
        score += 2
    if re.search(r"\d", text):
        score += 1
    if ". " in text or text.endswith("."):
        score += 1
    if len(text) > 320:
        score -= 1
    return score


def _fetch_text(url: str) -> str:
    if not url.startswith("http"):
        return ""
    lower = url.lower().split("?", 1)[0]
    if lower.endswith((".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".xlsx", ".docx")):
        return ""
    try:
        response = httpx.get(
            url,
            timeout=8,
            follow_redirects=True,
            headers={"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"},
        )
        response.raise_for_status()
        ctype = (response.headers.get("content-type") or "").lower()
        if "html" not in ctype and "text/plain" not in ctype and "xml" not in ctype:
            return ""
        raw = _SCRIPT.sub(" ", response.text[:80000])
        raw = _STYLE.sub(" ", raw)
        raw = _NOSCRIPT.sub(" ", raw)
        text = html_to_text(raw)
    except Exception:
        return ""
    lines = []
    for line in text.splitlines():
        piece = re.sub(r"\s+", " ", line).strip()
        if len(piece) < 50 or _looks_junk(piece):
            continue
        lines.append(piece)
        if sum(len(item) for item in lines) > 1800:
            break
    return " ".join(lines)


def _looks_junk(piece: str) -> bool:
    text = piece or ""
    if not text:
        return True
    if _SKIP_LINE.search(text) or _JSISH.search(text):
        return True
    if text.count("|") >= 2 and len(text) < 90:
        return True
    if " | " in text and not re.search(r"[.!?]", text):
        return True
    if re.search(r"हिन्दी|ગુજરાતી|मराठी|বাংলা|ಕನ್ನಡ|മലയാളം|தமிழ்|తెలుగు", text):
        return True
    letters = sum(ch.isalpha() for ch in text)
    return letters < max(12, int(len(text) * 0.45))


def _clip(text: str, limit: int = 220) -> str:
    blob = re.sub(r"\s+", " ", text or "").strip()
    if not blob:
        return ""
    cut = _JSISH.search(blob)
    if cut and cut.start() > 40:
        blob = blob[: cut.start()].strip()
    elif cut:
        return ""
    parts = _SENTENCE.split(blob)
    kept: list[str] = []
    for part in parts:
        piece = part.strip()
        if len(piece) < 28 or _looks_junk(piece):
            continue
        kept.append(piece if piece.endswith((".", "!", "?")) else f"{piece}.")
        if len(" ".join(kept)) >= limit:
            break
    out = " ".join(kept)
    if not out or _looks_junk(out):
        return ""
    if len(out) > limit + 40:
        out = out[: limit + 40].rsplit(" ", 1)[0] + "…"
    return out


def _takeaway(query: str, hits: list[dict[str, Any]]) -> str:
    ranked: list[tuple[int, str, str]] = []
    for hit in hits:
        site = hit.get("site") or hit.get("title") or "A source"
        note = _clip(hit.get("note") or "") or _clip(hit.get("snippet") or "")
        score = _quality(note)
        if score < 0 or not note:
            continue
        first = _SENTENCE.split(note)[0].strip().rstrip(".")
        if first and not _looks_junk(first):
            ranked.append((score, site, first))
    ranked.sort(key=lambda item: item[0], reverse=True)
    notes = [f"{site} — {first}." for _, site, first in ranked[:3]]
    if not notes:
        return f"I opened {len(hits)} sources on {query}."
    return " ".join(notes)
