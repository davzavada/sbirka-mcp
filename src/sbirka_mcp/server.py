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

from typing import Any

from mcp.server.fastmcp import FastMCP

from .citations import citace_to_stale_url, encode_stale_url
from .client import elegislativa_client, esbirka_client

mcp = FastMCP("sbirka-mcp")


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
    """Console-script entry point — runs the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
