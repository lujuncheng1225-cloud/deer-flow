"""
Web Search Tool - Search the web using DuckDuckGo (no API key required).
"""

import json
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from langchain.tools import tool

from deerflow.config import get_app_config

logger = logging.getLogger(__name__)

DEFAULT_BACKEND = "auto"
DEFAULT_REGION = "wt-wt"
DEFAULT_SAFESEARCH = "moderate"
DEFAULT_SEARCH_TIMEOUT = 30
DEFAULT_DIRECT_SITE_TIMEOUT = 8
DEFAULT_WIKIPEDIA_REGION = "us-en"
WIKIPEDIA_FALLBACK_BACKEND = "wikipedia"
DIRECT_SITE_TLDS = ("com", "app", "io", "ai", "im")
DIRECT_SITE_AI_TLDS = ("ai", "com", "app", "io", "im")
DIRECT_SITE_INTENT_TERMS = (
    "official",
    "website",
    "price",
    "pricing",
    "plan",
    "plans",
    "subscription",
    "subscribe",
    "官网",
    "价格",
    "定价",
    "套餐",
    "订阅",
)
DIRECT_SITE_STOPWORDS = {
    "agent",
    "analysis",
    "api",
    "app",
    "apps",
    "company",
    "docs",
    "feature",
    "features",
    "official",
    "plan",
    "plans",
    "price",
    "pricing",
    "subscription",
    "tool",
    "website",
}

WIKIPEDIA_BACKENDS = {"auto", "all", "wikipedia"}
WIKIPEDIA_LANGUAGE_ALIASES = {
    "jp": "ja",
    "kr": "ko",
    "tzh": "zh",
    "wt": "en",
}


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.parts.append(data)


def _normalize_backend(backend: str | list[str] | tuple[str, ...] | None) -> str:
    if backend is None:
        return DEFAULT_BACKEND
    if isinstance(backend, (list, tuple)):
        return ",".join(str(part).strip() for part in backend if str(part).strip()) or DEFAULT_BACKEND
    return str(backend).strip() or DEFAULT_BACKEND


def _normalize_setting(value: str | None, default: str) -> str:
    return str(value).strip() if value else default


def _coerce_positive_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _backend_includes_wikipedia(backend: str | list[str] | tuple[str, ...] | None) -> bool:
    backend = _normalize_backend(backend)
    return any(part.strip().lower() in WIKIPEDIA_BACKENDS for part in backend.split(","))


def _contains_codepoint(query: str, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= ord(char) <= end for char in query for start, end in ranges)


def _infer_wikipedia_region(query: str) -> str:
    """Pick a valid Wikipedia language region when DDGS' worldwide region is used."""
    if _contains_codepoint(query, ((0x3040, 0x30FF), (0x31F0, 0x31FF))):
        return "jp-ja"
    if _contains_codepoint(query, ((0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F))):
        return "kr-ko"
    if _contains_codepoint(query, ((0x3400, 0x9FFF),)):
        return "cn-zh"
    if _contains_codepoint(query, ((0x0400, 0x04FF),)):
        return "ru-ru"
    if _contains_codepoint(query, ((0x0370, 0x03FF),)):
        return "gr-el"
    if _contains_codepoint(query, ((0x0590, 0x05FF),)):
        return "il-he"
    if _contains_codepoint(query, ((0x0600, 0x06FF),)):
        return "xa-ar"
    return DEFAULT_WIKIPEDIA_REGION


def _resolve_ddgs_region(query: str, region: str | None, backend: str | list[str] | tuple[str, ...] | None) -> str:
    """
    DDGS' wikipedia engine treats the second part of region as a Wikipedia
    subdomain. Its default worldwide region, wt-wt, becomes wt.wikipedia.org.
    """
    normalized_region = _normalize_setting(region, DEFAULT_REGION).lower()
    if not _backend_includes_wikipedia(backend):
        return normalized_region

    if normalized_region == DEFAULT_REGION:
        return _infer_wikipedia_region(query)

    if "-" not in normalized_region:
        return DEFAULT_WIKIPEDIA_REGION

    country, language = normalized_region.split("-", 1)
    return f"{country}-{WIKIPEDIA_LANGUAGE_ALIASES.get(language, language)}"


def _search_text(
    query: str,
    max_results: int = 5,
    region: str | None = DEFAULT_REGION,
    safesearch: str | None = DEFAULT_SAFESEARCH,
    backend: str | list[str] | tuple[str, ...] | None = DEFAULT_BACKEND,
    timeout: int = DEFAULT_SEARCH_TIMEOUT,
) -> list[dict]:
    """
    Execute text search using DuckDuckGo.

    Args:
        query: Search keywords
        max_results: Maximum number of results
        region: Search region
        safesearch: Safe search level
        backend: DDGS backend(s), e.g. "auto", "duckduckgo", or "duckduckgo,brave"

    Returns:
        List of search results
    """
    try:
        from ddgs import DDGS
    except ImportError:
        logger.error("ddgs library not installed. Run: pip install ddgs")
        return []

    ddgs = DDGS(timeout=timeout)

    try:
        backend = _normalize_backend(backend)
        safesearch = _normalize_setting(safesearch, DEFAULT_SAFESEARCH)
        effective_region = _resolve_ddgs_region(query, region, backend)
        results = ddgs.text(
            query,
            region=effective_region,
            safesearch=safesearch,
            max_results=max_results,
            backend=backend,
        )
        return list(results) if results else []

    except Exception as e:
        logger.error(f"Failed to search web: {e}")
    return []


def _extract_title(html: str) -> str:
    parser = _TitleParser()
    parser.feed(html[:20000])
    return " ".join(" ".join(parser.parts).split())


def _extract_meta_description(html: str) -> str:
    match = re.search(
        r'<meta\s+[^>]*(?:name|property)=["\'](?:description|og:description)["\'][^>]*content=["\']([^"\']+)["\']',
        html[:50000],
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*(?:name|property)=["\'](?:description|og:description)["\']',
            html[:50000],
            flags=re.IGNORECASE,
        )
    return " ".join(match.group(1).split()) if match else ""


def _candidate_direct_site_urls(query: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add_host(host: str) -> None:
        host = host.lower().strip(".")
        if host in seen:
            return
        seen.add(host)
        candidates.append(f"https://{host}/")

    for match in re.finditer(r"\b([a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+)\b", query):
        host = match.group(1).lower()
        if "." in host and not host.startswith("-") and not host.endswith("-"):
            add_host(host)

    brand_tokens = []
    for match in re.finditer(r"\b[a-zA-Z][a-zA-Z0-9-]{2,31}\b", query):
        token = match.group(0).lower().strip("-")
        if token and token not in DIRECT_SITE_STOPWORDS and token not in brand_tokens:
            brand_tokens.append(token)
        if len(brand_tokens) >= 2:
            break

    tlds = DIRECT_SITE_AI_TLDS if re.search(r"\bai\b", query, flags=re.IGNORECASE) else DIRECT_SITE_TLDS
    for token in brand_tokens:
        for tld in tlds:
            add_host(f"{token}.{tld}")

    return candidates[:10]


def _fetch_direct_site_result(url: str, timeout: int = DEFAULT_DIRECT_SITE_TIMEOUT) -> dict | None:
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "DeerFlow web_search direct-site fallback"},
        )
        response.raise_for_status()
    except Exception as e:
        logger.debug("Direct site fallback failed for %s: %s", url, e)
        return None

    final_url = str(response.url)
    parsed = urlparse(final_url)
    title = _extract_title(response.text) or parsed.netloc
    snippet = _extract_meta_description(response.text)
    return {
        "title": title,
        "href": final_url,
        "body": snippet or f"Official site candidate for {parsed.netloc}",
        "provider": "direct_site_fallback",
    }


def _search_direct_site_fallback(query: str, max_results: int, timeout: int = DEFAULT_DIRECT_SITE_TIMEOUT) -> list[dict]:
    results: list[dict] = []
    for url in _candidate_direct_site_urls(query):
        result = _fetch_direct_site_result(url, timeout=timeout)
        if result is None:
            continue
        results.append(result)
        if len(results) >= max_results:
            break
    return results


def _should_try_direct_site_first(query: str) -> bool:
    normalized = query.lower()
    has_explicit_domain = re.search(r"\b[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+\b", query) is not None
    has_commercial_intent = any(term in normalized for term in DIRECT_SITE_INTENT_TERMS)
    return has_explicit_domain or (has_commercial_intent and bool(_candidate_direct_site_urls(query)))


def _search_serper_fallback(query: str, max_results: int) -> list[dict]:
    try:
        from deerflow.community.serper.tools import (
            _SERPER_SEARCH_ENDPOINT,
            _clean_query,
            _coerce_max_results,
            _get_api_key,
            _response_items,
            _serper_post,
        )
    except Exception as e:  # pragma: no cover - defensive optional provider import
        logger.warning("Serper fallback unavailable: %s", e)
        return []

    api_key = _get_api_key("web_search")
    if not api_key:
        return []

    cleaned_query = _clean_query(query)
    bounded_max_results = _coerce_max_results(max_results)
    data, error_json = _serper_post(
        _SERPER_SEARCH_ENDPOINT,
        api_key,
        cleaned_query,
        bounded_max_results,
    )
    if error_json is not None or data is None:
        return []

    organic, error_json = _response_items(data, "organic", cleaned_query)
    if error_json is not None or not organic:
        return []

    return [
        {
            "title": item.get("title", ""),
            "href": item.get("link", ""),
            "body": item.get("snippet", ""),
            "provider": "serper_fallback",
        }
        for item in organic[:bounded_max_results]
    ]


def _search_wikipedia_fallback(
    query: str,
    max_results: int,
    region: str | None,
    safesearch: str | None,
    backend: str | list[str] | tuple[str, ...] | None,
    timeout: int,
) -> list[dict]:
    backend_parts = {part.strip().lower() for part in _normalize_backend(backend).split(",")}
    if WIKIPEDIA_FALLBACK_BACKEND in backend_parts or "all" in backend_parts:
        return []

    results = _search_text(
        query=query,
        max_results=max_results,
        region=region,
        safesearch=safesearch,
        backend=WIKIPEDIA_FALLBACK_BACKEND,
        timeout=timeout,
    )
    return [
        {
            "title": item.get("title", ""),
            "href": item.get("href", item.get("link", "")),
            "body": item.get("body", item.get("snippet", "")),
            "provider": "wikipedia_fallback",
        }
        for item in results
    ]


@tool("web_search", parse_docstring=True)
def web_search_tool(
    query: str,
    max_results: int = 5,
) -> str:
    """Search the web for information. Use this tool to find current information, news, articles, and facts from the internet.

    Args:
        query: Search keywords describing what you want to find. Be specific for better results.
        max_results: Maximum number of results to return. Default is 5.
    """
    config = get_app_config().get_tool_config("web_search")
    region = DEFAULT_REGION
    safesearch = DEFAULT_SAFESEARCH
    backend = DEFAULT_BACKEND
    timeout = DEFAULT_SEARCH_TIMEOUT
    direct_site_first = False
    direct_site_timeout = DEFAULT_DIRECT_SITE_TIMEOUT
    direct_site_max_results = 1

    if config is not None:
        # Override tool call defaults from config if set.
        max_results = config.model_extra.get("max_results", max_results)
        region = config.model_extra.get("region", region)
        safesearch = config.model_extra.get("safesearch", safesearch)
        backend = config.model_extra.get("backend", backend)
        timeout = _coerce_positive_int(config.model_extra.get("timeout"), timeout)
        direct_site_first = _coerce_bool(config.model_extra.get("direct_site_first"), direct_site_first)
        direct_site_timeout = _coerce_positive_int(config.model_extra.get("direct_site_timeout"), direct_site_timeout)
        direct_site_max_results = _coerce_positive_int(config.model_extra.get("direct_site_max_results"), direct_site_max_results)

    providers_attempted: list[str] = []
    results: list[dict] = []
    provider = "ddg"
    if direct_site_first and _should_try_direct_site_first(query):
        providers_attempted.append("direct_site_fallback")
        results = _search_direct_site_fallback(query, min(max_results, direct_site_max_results), timeout=direct_site_timeout)
        if results:
            provider = "direct_site_fallback"
    if not results:
        providers_attempted.append(f"ddg:{_normalize_backend(backend)}")
        results = _search_text(
            query=query,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
            backend=backend,
            timeout=timeout,
        )
    if not results:
        providers_attempted.append("serper_fallback")
        results = _search_serper_fallback(query, max_results)
        if results:
            provider = "serper_fallback"
    if not results:
        providers_attempted.append("direct_site_fallback")
        results = _search_direct_site_fallback(query, min(max_results, direct_site_max_results), timeout=direct_site_timeout)
        if results:
            provider = "direct_site_fallback"
    if not results:
        providers_attempted.append("ddg:wikipedia")
        results = _search_wikipedia_fallback(
            query=query,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
            backend=backend,
            timeout=timeout,
        )
        if results:
            provider = "wikipedia_fallback"

    if not results:
        return json.dumps(
            {
                "error": "No results found",
                "query": query,
                "providers_attempted": providers_attempted,
            },
            ensure_ascii=False,
        )

    normalized_results = [
        {
            "title": r.get("title", ""),
            "url": r.get("href", r.get("link", "")),
            "content": r.get("body", r.get("snippet", "")),
        }
        for r in results
    ]

    output = {
        "query": query,
        "provider": provider,
        "providers_attempted": providers_attempted,
        "total_results": len(normalized_results),
        "results": normalized_results,
    }

    return json.dumps(output, indent=2, ensure_ascii=False)
