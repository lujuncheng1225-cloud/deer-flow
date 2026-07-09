"""Unit tests for the DDGS community web search tool."""

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from deerflow.community.ddg_search import tools


def test_resolve_ddgs_region_maps_worldwide_chinese_query_for_wikipedia() -> None:
    assert tools._resolve_ddgs_region("\u4e16\u754c\u676f\u65b0\u95fb 2026", "wt-wt", "auto") == "cn-zh"


def test_resolve_ddgs_region_uses_english_fallback_for_worldwide_query() -> None:
    assert tools._resolve_ddgs_region("latest world cup news", "wt-wt", "auto") == "us-en"


def test_resolve_ddgs_region_preserves_worldwide_for_non_wikipedia_backend() -> None:
    assert tools._resolve_ddgs_region("latest world cup news", "wt-wt", "duckduckgo") == "wt-wt"


def test_resolve_ddgs_region_maps_common_ddg_locale_aliases() -> None:
    assert tools._resolve_ddgs_region("\u65e5\u672c \u30cb\u30e5\u30fc\u30b9", "jp-jp", "auto") == "jp-ja"
    assert tools._resolve_ddgs_region("\ud55c\uad6d \ub274\uc2a4", "kr-kr", "auto") == "kr-ko"
    assert tools._resolve_ddgs_region("\u53f0\u7063\u65b0\u805e", "tw-tzh", "auto") == "tw-zh"


def test_search_text_passes_wikipedia_safe_region_to_ddgs(monkeypatch) -> None:
    calls = {}

    class FakeDDGS:
        def __init__(self, timeout: int) -> None:
            calls["timeout"] = timeout

        def text(self, query: str, **kwargs):
            calls["query"] = query
            calls.update(kwargs)
            return [{"title": "Result", "href": "https://example.com", "body": "Snippet"}]

    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=FakeDDGS))

    results = tools._search_text("\u4e16\u754c\u676f\u65b0\u95fb 2026", backend="auto")

    assert results == [{"title": "Result", "href": "https://example.com", "body": "Snippet"}]
    assert calls["timeout"] == 30
    assert calls["region"] == "cn-zh"
    assert calls["backend"] == "auto"


def test_web_search_tool_reads_ddgs_options_from_config() -> None:
    with patch("deerflow.community.ddg_search.tools.get_app_config") as mock_config:
        tool_config = MagicMock()
        tool_config.model_extra = {
            "max_results": 3,
            "region": "us-en",
            "safesearch": "off",
            "backend": "auto",
        }
        mock_config.return_value.get_tool_config.return_value = tool_config

        with patch("deerflow.community.ddg_search.tools._search_text") as mock_search:
            mock_search.return_value = [{"title": "Result", "href": "https://example.com", "body": "Snippet"}]

            result = tools.web_search_tool.invoke({"query": "latest news", "max_results": 8})
            parsed = json.loads(result)

    assert parsed["total_results"] == 1
    assert parsed["provider"] == "ddg"
    assert parsed["providers_attempted"] == ["ddg:auto"]
    mock_search.assert_called_once_with(
        query="latest news",
        max_results=3,
        region="us-en",
        safesearch="off",
        backend="auto",
    )


def test_web_search_tool_uses_serper_fallback_when_ddg_returns_empty() -> None:
    with patch("deerflow.community.ddg_search.tools.get_app_config") as mock_config:
        tool_config = MagicMock()
        tool_config.model_extra = {"max_results": 3}
        mock_config.return_value.get_tool_config.return_value = tool_config

        with (
            patch("deerflow.community.ddg_search.tools._search_text", return_value=[]),
            patch("deerflow.community.ddg_search.tools._search_serper_fallback") as mock_fallback,
        ):
            mock_fallback.return_value = [
                {
                    "title": "Manus: Hands On AI",
                    "href": "https://manus.im/",
                    "body": "Manus is the action engine that goes beyond answers.",
                    "provider": "serper_fallback",
                }
            ]

            result = tools.web_search_tool.invoke({"query": "manus.im AI", "max_results": 8})
            parsed = json.loads(result)

    assert parsed["provider"] == "serper_fallback"
    assert parsed["providers_attempted"] == ["ddg:auto", "serper_fallback"]
    assert parsed["total_results"] == 1
    assert parsed["results"][0]["url"] == "https://manus.im/"
    mock_fallback.assert_called_once_with("manus.im AI", 3)


def test_web_search_tool_uses_wikipedia_fallback_without_serper_results() -> None:
    with patch("deerflow.community.ddg_search.tools.get_app_config") as mock_config:
        tool_config = MagicMock()
        tool_config.model_extra = {"max_results": 3}
        mock_config.return_value.get_tool_config.return_value = tool_config

        with (
            patch("deerflow.community.ddg_search.tools._search_text") as mock_search,
            patch("deerflow.community.ddg_search.tools._search_serper_fallback", return_value=[]),
            patch("deerflow.community.ddg_search.tools._search_direct_site_fallback", return_value=[]),
        ):
            mock_search.side_effect = [
                [],
                [
                    {
                        "title": "Manus (AI agent)",
                        "href": "https://en.wikipedia.org/wiki/Manus_(AI_agent)",
                        "body": "Manus is a general AI agent platform.",
                    }
                ],
            ]

            result = tools.web_search_tool.invoke({"query": "Manus AI agent", "max_results": 8})
            parsed = json.loads(result)

    assert parsed["provider"] == "wikipedia_fallback"
    assert parsed["providers_attempted"] == ["ddg:auto", "serper_fallback", "direct_site_fallback", "ddg:wikipedia"]
    assert parsed["total_results"] == 1
    assert parsed["results"][0]["url"] == "https://en.wikipedia.org/wiki/Manus_(AI_agent)"
    assert mock_search.call_count == 2


def test_web_search_tool_uses_direct_site_fallback_before_wikipedia() -> None:
    with patch("deerflow.community.ddg_search.tools.get_app_config") as mock_config:
        tool_config = MagicMock()
        tool_config.model_extra = {"max_results": 3}
        mock_config.return_value.get_tool_config.return_value = tool_config

        with (
            patch("deerflow.community.ddg_search.tools._search_text", return_value=[]),
            patch("deerflow.community.ddg_search.tools._search_serper_fallback", return_value=[]),
            patch("deerflow.community.ddg_search.tools._search_direct_site_fallback") as mock_direct,
            patch("deerflow.community.ddg_search.tools._search_wikipedia_fallback") as mock_wikipedia,
        ):
            mock_direct.return_value = [
                {
                    "title": "Manus: Hands On AI",
                    "href": "https://manus.im/",
                    "body": "Official site candidate for manus.im",
                    "provider": "direct_site_fallback",
                }
            ]

            result = tools.web_search_tool.invoke({"query": "Manus AI agent", "max_results": 8})
            parsed = json.loads(result)

    assert parsed["provider"] == "direct_site_fallback"
    assert parsed["providers_attempted"] == ["ddg:auto", "serper_fallback", "direct_site_fallback"]
    assert parsed["results"][0]["url"] == "https://manus.im/"
    mock_direct.assert_called_once_with("Manus AI agent", 3)
    mock_wikipedia.assert_not_called()


def test_candidate_direct_site_urls_builds_brand_domain_candidates() -> None:
    assert tools._candidate_direct_site_urls("Manus AI agent")[:3] == [
        "https://manus.im/",
        "https://manus.ai/",
        "https://manus.com/",
    ]


def test_web_search_tool_keeps_no_results_when_fallback_is_empty() -> None:
    with patch("deerflow.community.ddg_search.tools.get_app_config") as mock_config:
        tool_config = MagicMock()
        tool_config.model_extra = {}
        mock_config.return_value.get_tool_config.return_value = tool_config

        with (
            patch("deerflow.community.ddg_search.tools._search_text", return_value=[]),
            patch("deerflow.community.ddg_search.tools._search_serper_fallback", return_value=[]),
            patch("deerflow.community.ddg_search.tools._search_direct_site_fallback", return_value=[]),
            patch("deerflow.community.ddg_search.tools._search_wikipedia_fallback", return_value=[]),
        ):
            result = tools.web_search_tool.invoke({"query": "missing thing", "max_results": 5})
            parsed = json.loads(result)

    assert parsed == {
        "error": "No results found",
        "query": "missing thing",
        "providers_attempted": ["ddg:auto", "serper_fallback", "direct_site_fallback", "ddg:wikipedia"],
    }
