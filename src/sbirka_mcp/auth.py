"""Optional password-gated OAuth 2.0 authorization server.

When OAuth is enabled, the MCP HTTP endpoint requires a Bearer token. Clients such
as the claude.ai web connector obtain that token through the standard flow:

1. discover metadata (``/.well-known/oauth-authorization-server`` etc.),
2. dynamically register (``POST /register``),
3. send the user's browser to ``/authorize`` — which we redirect to a ``/login``
   page that asks for a single shared **password**,
4. on the correct password we issue an authorization code and redirect back,
5. the client exchanges the code at ``/token`` (PKCE is verified by the SDK).

This is a single-secret gate: anyone who knows the password can connect. It exists so
a public HTTPS endpoint isn't wide open, and so the claude.ai connector (which
mandates OAuth) can attach. It is intentionally simple — state is in-memory, so
tokens do not survive a restart.
"""

from __future__ import annotations

import secrets
import time

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

_CODE_TTL = 600          # authorization code lifetime (seconds)
_TOKEN_TTL = 60 * 60 * 8  # access token lifetime (seconds)


class PasswordOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """In-memory OAuth AS that gates the /authorize step behind one password."""

    def __init__(self, password: str, public_url: str) -> None:
        self.password = password
        self.public_url = public_url.rstrip("/")
        self._clients: dict[str, OAuthClientInformationFull] = {}
        self._codes: dict[str, AuthorizationCode] = {}
        self._tokens: dict[str, AccessToken] = {}
        # rid -> (client, params) for in-flight authorization requests awaiting login
        self._pending: dict[str, tuple[OAuthClientInformationFull, AuthorizationParams]] = {}

    # --- client registration ------------------------------------------------
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._clients[client_info.client_id] = client_info

    # --- authorization ------------------------------------------------------
    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        rid = secrets.token_urlsafe(24)
        self._pending[rid] = (client, params)
        return f"{self.public_url}/login?rid={rid}"

    def pending_exists(self, rid: str) -> bool:
        return rid in self._pending

    def complete_login(self, rid: str) -> str | None:
        """Consume a pending request, mint a code, return the redirect URL."""
        entry = self._pending.pop(rid, None)
        if entry is None:
            return None
        client, params = entry
        code = secrets.token_urlsafe(32)
        self._codes[code] = AuthorizationCode(
            code=code,
            scopes=params.scopes or [],
            expires_at=time.time() + _CODE_TTL,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        return construct_redirect_uri(
            str(params.redirect_uri), code=code, state=params.state
        )

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self._codes.get(authorization_code)
        if code is None or code.client_id != client.client_id:
            return None
        if code.expires_at < time.time():
            self._codes.pop(authorization_code, None)
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self._codes.pop(authorization_code.code, None)
        token = secrets.token_urlsafe(32)
        self._tokens[token] = AccessToken(
            token=token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time() + _TOKEN_TTL),
            resource=authorization_code.resource,
        )
        return OAuthToken(
            access_token=token,
            token_type="Bearer",
            expires_in=_TOKEN_TTL,
            scope=" ".join(authorization_code.scopes) or None,
        )

    # --- tokens -------------------------------------------------------------
    async def load_access_token(self, token: str) -> AccessToken | None:
        access = self._tokens.get(token)
        if access is None:
            return None
        if access.expires_at and access.expires_at < time.time():
            self._tokens.pop(token, None)
            return None
        return access

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        return None  # refresh tokens are not issued

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        raise NotImplementedError("Refresh tokens are not supported.")

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self._tokens.pop(token.token, None)


def build_auth_settings(public_url: str) -> AuthSettings:
    public_url = public_url.rstrip("/")
    return AuthSettings(
        issuer_url=public_url,
        resource_server_url=public_url,
        client_registration_options=ClientRegistrationOptions(enabled=True),
        required_scopes=[],
    )


def login_page(rid: str, error: bool = False) -> str:
    """Minimal login form shown during the OAuth /authorize step."""
    err = (
        '<p style="color:#c0392b;margin:0 0 12px">Nesprávné heslo, zkuste to znovu.</p>'
        if error
        else ""
    )
    return f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<title>e-Sbírka MCP — přihlášení</title></head>
<body style="font-family:system-ui,sans-serif;background:#f4f6f8;margin:0;
display:flex;min-height:100vh;align-items:center;justify-content:center">
<form method="post" action="/login" style="background:#fff;padding:32px 28px;
border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.08);width:320px;text-align:center">
<div style="font:bold 40px Georgia,serif;color:#1f4e79">§</div>
<h1 style="font-size:18px;margin:8px 0 16px">e-Sbírka MCP</h1>
{err}
<input type="hidden" name="rid" value="{rid}">
<input type="password" name="password" placeholder="Heslo" autofocus required
 style="width:100%;box-sizing:border-box;padding:10px;border:1px solid #cdd5de;
 border-radius:8px;margin-bottom:12px">
<button type="submit" style="width:100%;padding:10px;border:0;border-radius:8px;
 background:#1f4e79;color:#fff;font-size:15px;cursor:pointer">Přihlásit a povolit</button>
</form></body></html>"""
