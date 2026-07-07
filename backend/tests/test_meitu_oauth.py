from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.gateway.routers.auth as auth_router
from app.gateway.auth.config import AuthConfig, set_auth_config
from app.gateway.auth.meitu_oauth import (
    MEITU_PROVIDER_ID,
    MeituOAuthConfig,
    MeituOAuthIdentity,
    MeituOAuthService,
    build_meitu_authorization_url,
    get_meitu_oauth_config,
    get_or_provision_meitu_user,
)
from app.gateway.auth.models import User


def _config(**overrides):
    values = {
        "appid": "test-appid",
        "appsecret": "test-secret",
        "redirect_uri": "https://example.com/api/v1/auth/callback/meitu",
        "frontend_base_url": "https://example.com",
        "allowed_email_domains": ("meitu.com",),
    }
    values.update(overrides)
    return MeituOAuthConfig(**values)


def _request(cookie: str | None = None) -> Request:
    headers = [(b"host", b"example.com")]
    if cookie:
        headers.append((b"cookie", cookie.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/api/v1/auth/callback/meitu",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
        }
    )


@pytest.fixture(autouse=True)
def _auth_config():
    set_auth_config(AuthConfig(jwt_secret="test-meitu-oauth-jwt-secret-min-32"))
    yield
    set_auth_config(AuthConfig(jwt_secret="test-meitu-oauth-jwt-secret-min-32"))


def test_meitu_oauth_config_requires_core_env(monkeypatch):
    monkeypatch.delenv("MEITU_OAUTH_APPID", raising=False)
    monkeypatch.delenv("MEITU_OAUTH_APPSECRET", raising=False)
    monkeypatch.delenv("MEITU_OAUTH_REDIRECT_URI", raising=False)

    assert get_meitu_oauth_config() is None

    monkeypatch.setenv("MEITU_OAUTH_APPID", "1291832")
    monkeypatch.setenv("MEITU_OAUTH_APPSECRET", "unit-test-secret")
    monkeypatch.setenv("MEITU_OAUTH_REDIRECT_URI", "https://example.com/api/v1/auth/callback/meitu")

    config = get_meitu_oauth_config()
    assert config is not None
    assert config.allowed_email_domains == ("meitu.com",)


def test_build_meitu_authorization_url_uses_meitu_parameter_names():
    url = build_meitu_authorization_url(_config(), "state-value")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.geturl().startswith("https://oauth.meitu.com/oauth2/authorize_new?")
    assert params["appid"] == ["test-appid"]
    assert params["response_type"] == ["code"]
    assert params["redirect_uri"] == ["https://example.com/api/v1/auth/callback/meitu"]
    assert params["scope"] == ["user_info"]
    assert params["state"] == ["state-value"]
    assert "client_id" not in params


@pytest.mark.asyncio
async def test_meitu_service_fetch_user_info_requires_success_code_and_matching_openid(monkeypatch):
    service = MeituOAuthService()

    async def post(url, data, headers):
        return httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "ok",
                "openid": data["openid"],
                "login_email": "USER@meitu.com",
                "name": "Test User",
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(service._http, "post", post)

    identity = await service.fetch_user_info(_config(), "access-token", "openid-1")

    assert identity.openid == "openid-1"
    assert identity.email == "user@meitu.com"
    assert identity.display_name == "Test User"
    await service.close()


@pytest.mark.asyncio
async def test_meitu_provision_rejects_missing_or_external_email():
    provider = SimpleNamespace()
    provider.get_user_by_oauth = AsyncMock(return_value=None)
    provider.get_user_by_email = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as missing_exc:
        await get_or_provision_meitu_user(
            _config(),
            MeituOAuthIdentity(openid="openid-1", email=None, display_name=None, profile={}),
            provider,
        )
    assert missing_exc.value.status_code == 403

    with pytest.raises(HTTPException) as domain_exc:
        await get_or_provision_meitu_user(
            _config(),
            MeituOAuthIdentity(openid="openid-2", email="user@example.com", display_name=None, profile={}),
            provider,
        )
    assert domain_exc.value.status_code == 403


@pytest.mark.asyncio
async def test_meitu_provision_creates_oauth_user_by_openid():
    created = User(email="user@meitu.com", password_hash=None, oauth_provider=MEITU_PROVIDER_ID, oauth_id="openid-1")
    provider = SimpleNamespace()
    provider.get_user_by_oauth = AsyncMock(return_value=None)
    provider.get_user_by_email = AsyncMock(return_value=None)
    provider.create_oauth_user = AsyncMock(return_value=created)

    result = await get_or_provision_meitu_user(
        _config(),
        MeituOAuthIdentity(openid="openid-1", email="user@meitu.com", display_name=None, profile={}),
        provider,
    )

    assert result == {"user": created, "created": True}
    provider.create_oauth_user.assert_awaited_once_with(
        email="user@meitu.com",
        oauth_provider=MEITU_PROVIDER_ID,
        oauth_id="openid-1",
        system_role="user",
    )


@pytest.mark.asyncio
async def test_meitu_login_and_callback_issue_session_cookie(monkeypatch):
    monkeypatch.setenv("MEITU_OAUTH_APPID", "1291832")
    monkeypatch.setenv("MEITU_OAUTH_APPSECRET", "unit-test-secret")
    monkeypatch.setenv("MEITU_OAUTH_REDIRECT_URI", "https://example.com/api/v1/auth/callback/meitu")
    monkeypatch.setenv("MEITU_OAUTH_FRONTEND_BASE_URL", "https://example.com")
    monkeypatch.setenv("MEITU_OAUTH_ALLOWED_EMAIL_DOMAIN", "meitu.com")

    login_response = await auth_router._meitu_oauth_login(_request(), "/workspace/chats/new")
    location = login_response.headers["location"]
    params = parse_qs(urlparse(location).query)
    state = params["state"][0]
    state_cookie = next(value for key, value in login_response.raw_headers if key == b"set-cookie")
    state_cookie_pair = state_cookie.decode("ascii").split(";", 1)[0]

    fake_service = SimpleNamespace()
    fake_service.authenticate_callback = AsyncMock(
        return_value=MeituOAuthIdentity(
            openid="openid-1",
            email="user@meitu.com",
            display_name="Test User",
            profile={"code": 0, "login_email": "user@meitu.com"},
        )
    )
    monkeypatch.setattr(auth_router, "_get_meitu_oauth_service", lambda: fake_service)

    created = User(
        email="user@meitu.com",
        password_hash=None,
        oauth_provider=MEITU_PROVIDER_ID,
        oauth_id="openid-1",
    )
    fake_provider = SimpleNamespace()
    fake_provider.get_user_by_oauth = AsyncMock(return_value=None)
    fake_provider.get_user_by_email = AsyncMock(return_value=None)
    fake_provider.create_oauth_user = AsyncMock(return_value=created)
    monkeypatch.setattr(auth_router, "get_local_provider", lambda: fake_provider)

    callback_response = await auth_router._meitu_oauth_callback(
        _request(state_cookie_pair),
        code="auth-code",
        state=state,
        error=None,
        error_description=None,
    )

    assert callback_response.status_code == 302
    assert callback_response.headers["location"] == "https://example.com/auth/callback?next=/workspace/chats/new"
    set_cookie_headers = [value.decode("ascii") for key, value in callback_response.raw_headers if key == b"set-cookie"]
    assert any(header.startswith("access_token=") and "HttpOnly" in header for header in set_cookie_headers)
    assert any(header.startswith("csrf_token=") for header in set_cookie_headers)
