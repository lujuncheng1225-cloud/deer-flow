"""
Web Search Tool - Search the web using DuckDuckGo (no API key required).
"""

import json
import logging

from langchain.tools import tool

from deerflow.config import get_app_config

logger = logging.getLogger(__name__)

DEFAULT_BACKEND = "auto"
DEFAULT_REGION = "wt-wt"
DEFAULT_SAFESEARCH = "moderate"
DEFAULT_WIKIPEDIA_REGION = "us-en"
WIKIPEDIA_FALLBACK_BACKEND = "wikipedia"

WIKIPEDIA_BACKENDS = {"auto", "all", "wikipedia"}
WIKIPEDIA_LANGUAGE_ALIASES = {
    "jp": "ja",
    "kr": "ko",
    "tzh": "zh",
    "wt": "en",
}


def _normalize_backend(backend: str | list[str] | tuple[str, ...] | None) -> str:
    if backend is None:
        return DEFAULT_BACKEND
    if isinstance(backend, (list, tuple)):
        return ",".join(str(part).strip() for part in backend if str(part).strip()) or DEFAULT_BACKEND
    return str(backend).strip() or DEFAULT_BACKEND


def _normalize_setting(value: str | None, default: str) -> str:
    return str(value).strip() if value else default


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

    ddgs = DDGS(timeout=30)

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

    if config is not None:
        # Override tool call defaults from config if set.
        max_results = config.model_extra.get("max_results", max_results)
        region = config.model_extra.get("region", region)
        safesearch = config.model_extra.get("safesearch", safesearch)
        backend = config.model_extra.get("backend", backend)

    providers_attempted = [f"ddg:{_normalize_backend(backend)}"]
    results = _search_text(
        query=query,
        max_results=max_results,
        region=region,
        safesearch=safesearch,
        backend=backend,
    )
    provider = "ddg"
    if not results:
        providers_attempted.append("serper_fallback")
        results = _search_serper_fallback(query, max_results)
        if results:
            provider = "serper_fallback"
    if not results:
        providers_attempted.append("ddg:wikipedia")
        results = _search_wikipedia_fallback(
            query=query,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
            backend=backend,
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
