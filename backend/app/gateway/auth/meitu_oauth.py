"""Meitu OAuth 2.0 login support.

Meitu OAuth is a plain authorization-code provider, not OIDC. The user
identity is resolved by exchanging ``code`` for ``access_token`` + ``openid``
and then calling the Meitu user-info endpoint.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.gateway.auth.local_provider import LocalAuthProvider

logger = logging.getLogger(__name__)

MEITU_PROVIDER_ID = "meitu"
MEITU_AUTHORIZATION_URL = "https://oauth.meitu.com/oauth2/authorize_new"
MEITU_TOKEN_URL = "https://oauth.meitu.com/oauth2/token"
MEITU_USER_INFO_URL = "https://oauth.meitu.com/user/get_user_info"


@dataclass(frozen=True)
class MeituOAuthConfig:
    appid: str
    appsecret: str
    redirect_uri: str
    frontend_base_url: str | None
    allowed_email_domains: tuple[str, ...]
    authorization_url: str = MEITU_AUTHORIZATION_URL
    token_url: str = MEITU_TOKEN_URL
    user_info_url: str = MEITU_USER_INFO_URL


@dataclass(frozen=True)
class MeituOAuthIdentity:
    openid: str
    email: str | None
    display_name: str | None
    profile: dict[str, Any]


class MeituOAuthError(Exception):
    """Safe error for Meitu OAuth operations."""


def _split_domains(raw: str) -> tuple[str, ...]:
    domains = []
    for item in raw.split(","):
        domain = item.strip().lower().lstrip("@")
        if domain:
            domains.append(domain)
    return tuple(domains)


def _env_or_default(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def get_meitu_oauth_config() -> MeituOAuthConfig | None:
    """Read Meitu OAuth settings from env.

    The provider is enabled only when appid, appsecret, and redirect URI are all
    present. The email domain allowlist defaults to ``meitu.com`` to keep this
    integration internal-only unless explicitly changed.
    """
    appid = os.getenv("MEITU_OAUTH_APPID", "").strip()
    appsecret = os.getenv("MEITU_OAUTH_APPSECRET", "").strip()
    redirect_uri = os.getenv("MEITU_OAUTH_REDIRECT_URI", "").strip()
    if not appid or not appsecret or not redirect_uri:
        return None

    return MeituOAuthConfig(
        appid=appid,
        appsecret=appsecret,
        redirect_uri=redirect_uri,
        frontend_base_url=os.getenv("MEITU_OAUTH_FRONTEND_BASE_URL", "").strip() or None,
        allowed_email_domains=_split_domains(os.getenv("MEITU_OAUTH_ALLOWED_EMAIL_DOMAIN", "meitu.com")),
        authorization_url=_env_or_default("MEITU_OAUTH_AUTHORIZATION_URL", MEITU_AUTHORIZATION_URL),
        token_url=_env_or_default("MEITU_OAUTH_TOKEN_URL", MEITU_TOKEN_URL),
        user_info_url=_env_or_default("MEITU_OAUTH_USER_INFO_URL", MEITU_USER_INFO_URL),
    )


def is_meitu_oauth_enabled() -> bool:
    return get_meitu_oauth_config() is not None


def build_meitu_authorization_url(config: MeituOAuthConfig, state: str) -> str:
    params = {
        "appid": config.appid,
        "response_type": "code",
        "redirect_uri": config.redirect_uri,
        "scope": "user_info",
        "state": state,
    }
    return f"{config.authorization_url}?{urlencode(params)}"


def _safe_provider_message(data: dict[str, Any]) -> str:
    for key in ("error_description", "error", "msg", "message"):
        value = data.get(key)
        if value:
            return str(value)
    return "unknown provider error"


def _extract_email(profile: dict[str, Any]) -> str | None:
    raw = profile.get("login_email") or profile.get("email")
    if not isinstance(raw, str):
        return None
    email = raw.strip().lower()
    if "@" not in email:
        return None
    return email


def _extract_display_name(profile: dict[str, Any]) -> str | None:
    for key in ("name", "display_name", "name_en", "first_name"):
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class MeituOAuthService:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(15.0))

    async def close(self) -> None:
        await self._http.aclose()

    async def authenticate_callback(self, config: MeituOAuthConfig, code: str) -> MeituOAuthIdentity:
        token = await self.exchange_code(config, code)
        return await self.fetch_user_info(config, token["access_token"], token["openid"])

    async def exchange_code(self, config: MeituOAuthConfig, code: str) -> dict[str, str]:
        payload = {
            "appid": config.appid,
            "appsecret": config.appsecret,
            "code": code,
            "redirect_uri": config.redirect_uri,
            "grant_type": "auth_code",
        }
        try:
            response = await self._http.post(
                config.token_url,
                data=payload,
                headers={"Accept": "application/json"},
            )
            data = self._parse_response(response, "token exchange")
        except httpx.RequestError as exc:
            raise MeituOAuthError("Token exchange failed") from exc

        access_token = data.get("access_token")
        openid = data.get("openid")
        if not isinstance(access_token, str) or not access_token:
            raise MeituOAuthError(f"Token exchange failed: {_safe_provider_message(data)}")
        if not isinstance(openid, str) or not openid:
            raise MeituOAuthError("Token exchange failed: missing openid")
        return {"access_token": access_token, "openid": openid}

    async def fetch_user_info(
        self,
        config: MeituOAuthConfig,
        access_token: str,
        openid: str,
    ) -> MeituOAuthIdentity:
        payload = {
            "appid": config.appid,
            "access_token": access_token,
            "openid": openid,
        }
        try:
            response = await self._http.post(
                config.user_info_url,
                data=payload,
                headers={"Accept": "application/json"},
            )
            profile = self._parse_response(response, "user info")
        except httpx.RequestError as exc:
            raise MeituOAuthError("User info request failed") from exc

        code = profile.get("code")
        if code not in (0, "0"):
            raise MeituOAuthError(f"User info request failed: {_safe_provider_message(profile)}")

        profile_openid = profile.get("openid")
        if isinstance(profile_openid, str) and profile_openid and profile_openid != openid:
            raise MeituOAuthError("User info openid mismatch")

        return MeituOAuthIdentity(
            openid=openid,
            email=_extract_email(profile),
            display_name=_extract_display_name(profile),
            profile=profile,
        )

    @staticmethod
    def _parse_response(response: httpx.Response, operation: str) -> dict[str, Any]:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MeituOAuthError(f"{operation} failed: HTTP {exc.response.status_code}") from exc

        try:
            data = response.json()
        except ValueError:
            text = response.text.strip()
            try:
                data = json.loads(text)
            except ValueError as exc:
                raise MeituOAuthError(f"{operation} failed: non-JSON response") from exc

        if not isinstance(data, dict):
            raise MeituOAuthError(f"{operation} failed: invalid response shape")
        return data


async def get_or_provision_meitu_user(
    config: MeituOAuthConfig,
    identity: MeituOAuthIdentity,
    local_provider: LocalAuthProvider,
) -> dict[str, Any]:
    existing = await local_provider.get_user_by_oauth(MEITU_PROVIDER_ID, identity.openid)
    if existing:
        return {"user": existing, "created": False}

    if not identity.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Meitu OAuth did not provide a login email.",
        )

    domain = identity.email.rsplit("@", 1)[-1]
    allowed_domains = {d.lower().lstrip("@") for d in config.allowed_email_domains}
    if allowed_domains and domain not in allowed_domains:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your email domain is not allowed. Please use an approved Meitu email address.",
        )

    local_user = await local_provider.get_user_by_email(identity.email)
    if local_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("An account with this email already exists. Contact your administrator to link it to your OA account."),
        )

    try:
        user = await local_provider.create_oauth_user(
            email=identity.email,
            oauth_provider=MEITU_PROVIDER_ID,
            oauth_id=identity.openid,
            system_role="user",
        )
    except ValueError:
        existing = await local_provider.get_user_by_oauth(MEITU_PROVIDER_ID, identity.openid)
        if existing:
            return {"user": existing, "created": False}
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("An account with this email already exists. Contact your administrator to link it to your OA account."),
        ) from None

    logger.info("Auto-created Meitu OAuth user %s", identity.email)
    return {"user": user, "created": True}
