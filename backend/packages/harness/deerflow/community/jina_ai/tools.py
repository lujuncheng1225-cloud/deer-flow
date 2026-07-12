import asyncio
from ipaddress import ip_address
from urllib.parse import urlparse

import httpx
from langchain.tools import tool

from deerflow.community.jina_ai.jina_client import JinaClient
from deerflow.config import get_app_config
from deerflow.utils.readability import ReadabilityExtractor

readability_extractor = ReadabilityExtractor()


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_timeout(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _coerce_proxy(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    proxy = value.strip()
    return proxy or None


def _direct_fetch_url_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        return ip_address(host).is_global
    except ValueError:
        return True


async def _direct_fetch_html(url: str, timeout: int, proxy: str | None, trust_env: bool) -> str | None:
    if not _direct_fetch_url_allowed(url):
        return None
    client_kwargs: dict[str, object] = {
        "follow_redirects": True,
        "headers": {"User-Agent": "DeerFlow web_fetch direct fallback"},
        "timeout": timeout,
        "trust_env": trust_env,
    }
    if proxy:
        client_kwargs["proxy"] = proxy
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.get(url)
        response.raise_for_status()
        return response.text if response.text.strip() else None
    except Exception:
        return None


async def _extract_markdown(html_content: str, *, use_readability_js: bool = True) -> str:
    extractor = readability_extractor if use_readability_js else ReadabilityExtractor(use_readability_js=False)
    article = await asyncio.to_thread(extractor.extract_article, html_content)
    return article.to_markdown()[:4096]


@tool("web_fetch", parse_docstring=True)
async def web_fetch_tool(url: str) -> str:
    """Fetch the contents of a web page at a given URL.
    Only fetch EXACT URLs that have been provided directly by the user or have been returned in results from the web_search and web_fetch tools.
    This tool can NOT access content that requires authentication, such as private Google Docs or pages behind login walls.
    Do NOT add www. to URLs that do NOT have them.
    URLs must include the schema: https://example.com is a valid URL while example.com is an invalid URL.

    Args:
        url: The URL to fetch the contents of.
    """
    jina_client = JinaClient()
    timeout = 10
    proxy = None
    trust_env = True
    direct_first = False
    direct_min_characters = 200
    use_readability_js = True
    config = get_app_config().get_tool_config("web_fetch")
    if config is not None:
        timeout = _coerce_timeout(config.model_extra.get("timeout"), timeout)
        proxy = _coerce_proxy(config.model_extra.get("proxy"))
        trust_env = _coerce_bool(config.model_extra.get("trust_env"), trust_env)
        direct_first = _coerce_bool(config.model_extra.get("direct_first"), direct_first)
        direct_min_characters = _coerce_timeout(config.model_extra.get("direct_min_characters"), direct_min_characters)
        use_readability_js = _coerce_bool(config.model_extra.get("use_readability_js"), use_readability_js)

    direct_html = None
    direct_markdown = None
    if direct_first:
        direct_html = await _direct_fetch_html(url, timeout=timeout, proxy=proxy, trust_env=trust_env)
        if direct_html is not None:
            try:
                direct_markdown = await _extract_markdown(direct_html, use_readability_js=use_readability_js)
            except Exception:
                direct_markdown = None
            if direct_markdown is not None and len(direct_markdown.strip()) >= max(0, direct_min_characters):
                return direct_markdown

    html_content = await jina_client.crawl(url, return_format="html", timeout=timeout, proxy=proxy, trust_env=trust_env)
    if isinstance(html_content, str) and html_content.startswith("Error:"):
        if direct_html is None:
            direct_html = await _direct_fetch_html(url, timeout=timeout, proxy=proxy, trust_env=trust_env)
        if direct_html is None:
            return html_content
        return direct_markdown if direct_markdown is not None else await _extract_markdown(direct_html, use_readability_js=use_readability_js)
    return await _extract_markdown(html_content, use_readability_js=use_readability_js)
