"""FastMCP server exposing the Czech e-Sbírka / e-Legislativa public REST API.

Tools fall into two groups:

* **e-Sbírka** (published, in-force collection of laws) — fetch a regulation's
  metadata by its citation / ELI.
* **e-Legislativa** (the legislative process) — full-text search over legal acts,
  intents (věcný / legislativní záměr), draft detail, and code lists.

Authentication uses the shared ``esel-api-access-key`` header, read from the
``ESEL_API_ACCESS_KEY`` environment variable. See :mod:`sbirka_mcp.client`.
"""

from __future__ import annotations

import os
import secrets
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from .auth import PasswordOAuthProvider, build_auth_settings, login_page
from .citations import citace_to_stale_url, encode_stale_url
from .client import elegislativa_client, esbirka_client

def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


# --- optional OAuth -------------------------------------------------------
# Enabled via MCP_OAUTH_ENABLED + MCP_OAUTH_PASSWORD + MCP_PUBLIC_URL. When on,
# the HTTP endpoint requires a Bearer token obtained through a password login.
_oauth_provider: PasswordOAuthProvider | None = None
_oauth_kwargs: dict[str, Any] = {}
if (
    _truthy(os.environ.get("MCP_OAUTH_ENABLED", "false"))
    and os.environ.get("MCP_OAUTH_PASSWORD")
    and os.environ.get("MCP_PUBLIC_URL")
):
    _public_url = os.environ["MCP_PUBLIC_URL"]
    _oauth_provider = PasswordOAuthProvider(
        password=os.environ["MCP_OAUTH_PASSWORD"], public_url=_public_url
    )
    _oauth_kwargs = {
        "auth_server_provider": _oauth_provider,
        "auth": build_auth_settings(_public_url),
    }


mcp = FastMCP(
    "sbirka-mcp",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8099")),
    log_level=os.environ.get("MCP_LOG_LEVEL", "INFO").upper(),
    streamable_http_path=os.environ.get("MCP_HTTP_PATH", "/mcp"),
    stateless_http=_truthy(os.environ.get("MCP_STATELESS_HTTP", "false")),
    **_oauth_kwargs,
)


if _oauth_provider is not None:

    @mcp.custom_route("/login", methods=["GET"])
    async def login_get(request: Request) -> Response:
        rid = request.query_params.get("rid", "")
        if not _oauth_provider.pending_exists(rid):
            return HTMLResponse("Neplatný nebo vypršelý požadavek.", status_code=400)
        return HTMLResponse(login_page(rid))

    @mcp.custom_route("/login", methods=["POST"])
    async def login_post(request: Request) -> Response:
        form = await request.form()
        rid = str(form.get("rid", ""))
        password = str(form.get("password", ""))
        if not _oauth_provider.pending_exists(rid):
            return HTMLResponse("Neplatný nebo vypršelý požadavek.", status_code=400)
        if not secrets.compare_digest(password, _oauth_provider.password):
            return HTMLResponse(login_page(rid, error=True), status_code=401)
        redirect_url = _oauth_provider.complete_login(rid)
        if redirect_url is None:
            return HTMLResponse("Neplatný nebo vypršelý požadavek.", status_code=400)
        return RedirectResponse(redirect_url, status_code=302)

# A "§" favicon, served when the public HTTP endpoint is opened in a browser.
_FAVICON_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    b'<rect width="64" height="64" rx="12" fill="#1f4e79"/>'
    b'<text x="32" y="34" font-family="Georgia,\'Times New Roman\',serif"'
    b' font-size="46" font-weight="bold" fill="#ffffff" text-anchor="middle"'
    b' dominant-baseline="central">\xc2\xa7</text></svg>'
)


@mcp.custom_route("/favicon.svg", methods=["GET"])
async def favicon_svg(request: Request) -> Response:
    return Response(content=_FAVICON_SVG, media_type="image/svg+xml")


@mcp.custom_route("/favicon.ico", methods=["GET"])
async def favicon_ico(request: Request) -> Response:
    # Modern browsers render an SVG served here fine; avoids shipping a binary .ico.
    return Response(content=_FAVICON_SVG, media_type="image/svg+xml")


def _search_body(
    *,
    dotaz: str | None,
    fraze: str | None,
    start: int,
    pocet: int,
    prohledavat_text: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a request body shared by the rozšířené (extended) search endpoints."""
    body: dict[str, Any] = {"start": start, "pocet": pocet}
    if dotaz:
        body["fulltextVsechnaSlova"] = dotaz
    if fraze:
        body["fulltextUvedenaFraze"] = fraze
    body["kriteriaVyhledavani"] = {
        "prohledavatVlastnosti": True,
        "prohledavatText": prohledavat_text,
    }
    if extra:
        body.update(extra)
    return body


@mcp.tool()
def vyhledat_predpisy(
    dotaz: str = "",
    fraze: str = "",
    typ_aktu: list[str] | None = None,
    pravni_oblast: list[int] | None = None,
    prohledavat_text: bool = False,
    start: int = 0,
    pocet: int = 20,
) -> dict[str, Any]:
    """Vyhledá právní akty (zákony, vyhlášky, nařízení …) v systému e-Legislativa.

    Args:
        dotaz: Slova, která musí výsledek obsahovat (fulltext, všechna slova / AND).
        fraze: Přesná fráze, kterou musí výsledek obsahovat.
        typ_aktu: Volitelné kódy typu právního aktu (viz vypis_ciselnik("DruhAktu")).
        pravni_oblast: Volitelné kódy právních oblastí (číselné).
        prohledavat_text: Prohledávat i strukturovaný text aktů (ne jen metadata).
        start: Offset stránkování (první vrácený prvek).
        pocet: Počet vrácených prvků (max. dle limitů API).

    Returns:
        Kolekce nalezených právních aktů s celkovým počtem (pole ``kolekce``,
        ``pocetCelkem``). Každá položka obsahuje mj. ``identifikator``,
        ``pravniAktNazev``, ``navrhCislo`` a ``stavKod``.
    """
    extra: dict[str, Any] = {}
    if typ_aktu:
        extra["typPravniAktKod"] = typ_aktu
    if pravni_oblast:
        extra["pravniOblastiKod"] = pravni_oblast
    body = _search_body(
        dotaz=dotaz or None,
        fraze=fraze or None,
        start=start,
        pocet=pocet,
        prohledavat_text=prohledavat_text,
        extra=extra,
    )
    client = elegislativa_client()
    try:
        return client.post("/vyhledavani/pravni-akt-rozsirene", json=body)
    finally:
        client.close()


@mcp.tool()
def vyhledat_vecny_zamer(
    dotaz: str = "",
    fraze: str = "",
    prohledavat_text: bool = False,
    start: int = 0,
    pocet: int = 20,
) -> dict[str, Any]:
    """Vyhledá věcné záměry (rané fáze legislativního procesu) v e-Legislativě."""
    body = _search_body(
        dotaz=dotaz or None,
        fraze=fraze or None,
        start=start,
        pocet=pocet,
        prohledavat_text=prohledavat_text,
    )
    client = elegislativa_client()
    try:
        return client.post("/vyhledavani/vecny-zamer-rozsirene", json=body)
    finally:
        client.close()


@mcp.tool()
def vyhledat_legislativni_zamer(
    dotaz: str = "",
    fraze: str = "",
    prohledavat_text: bool = False,
    start: int = 0,
    pocet: int = 20,
) -> dict[str, Any]:
    """Vyhledá legislativní záměry v systému e-Legislativa."""
    body = _search_body(
        dotaz=dotaz or None,
        fraze=fraze or None,
        start=start,
        pocet=pocet,
        prohledavat_text=prohledavat_text,
    )
    client = elegislativa_client()
    try:
        return client.post("/vyhledavani/legislativni-zamer-rozsirene", json=body)
    finally:
        client.close()


@mcp.tool()
def ziskat_navrh(navrh_id: int) -> dict[str, Any]:
    """Vrátí detail návrhu (legislativního procesu) podle jeho identifikátoru.

    ``navrh_id`` získáte z pole ``identifikator`` výsledků vyhledávání.
    """
    client = elegislativa_client()
    try:
        return client.get(f"/navrhy/{int(navrh_id)}")
    finally:
        client.close()


@mcp.tool()
def vypis_ciselnik(kod_ciselniku: str) -> dict[str, Any]:
    """Vypíše číselník e-Legislativy (povolené hodnoty pro filtry vyhledávání).

    Užitečné kódy: ``DruhAktu``, ``PodtypAktu``, ``TypDokumentu``,
    ``DefiniceStavu``, ``Instituce``, ``AutorAktu``. Hodnoty z číselníku lze
    použít jako ``typ_aktu`` ve ``vyhledat_predpisy``.
    """
    client = elegislativa_client()
    try:
        return client.get(f"/ciselniky/{kod_ciselniku}")
    finally:
        client.close()


@mcp.tool()
def ziskat_dokument_sbirky(citace: str) -> dict[str, Any]:
    """Vrátí metadata vyhlášeného předpisu ze Sbírky zákonů (e-Sbírka).

    Args:
        citace: Citace nebo identifikátor předpisu — např. ``"89/2012 Sb."``,
            stálé URL ``"/sb/2012/89"`` nebo ELI.

    Returns:
        Metadata dokumentu (název, úplná i zkrácená citace, ELI, účinnost,
        seznam novel ``novely`` apod.).
    """
    stale_url = citace_to_stale_url(citace)
    path = f"/dokumenty-sbirky/{encode_stale_url(stale_url)}"
    client = esbirka_client()
    try:
        return client.get(path)
    finally:
        client.close()


def main() -> None:
    """Console-script entry point.

    Transport is selected by the ``MCP_TRANSPORT`` environment variable:

    * ``stdio`` (default) — for desktop MCP clients that launch the server as a
      subprocess (Claude Desktop / Claude Code).
    * ``sse`` — run as a network service exposing ``/sse`` on ``MCP_HOST``:``MCP_PORT``
      (used by the Home Assistant add-on / HA MCP Client integration).
    """
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport in ("sse", "streamable-http"):
        mcp.run(transport=transport)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
