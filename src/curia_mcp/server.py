"""FastMCP server bridging EU case-law via Cellar (EUR-Lex) + InfoCuria links.

InfoCuria itself exposes no API, so the machine-readable data comes from the public
**Cellar** repository (:mod:`curia_mcp.eurlex`): SPARQL for metadata search and REST
content negotiation for full text by CELEX number. InfoCuria is used for stable,
human-facing deep links by case number (:mod:`curia_mcp.infocuria`).

Transport mirrors the sibling ``sbirka-mcp`` server: stdio by default, or a network
service via ``MCP_TRANSPORT=streamable-http`` / ``sse`` on ``MCP_HOST``:``MCP_PORT``.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .celex import is_celex, parse_case_number, parse_celex, parse_ecli
from .eurlex import CellarError, cellar_client, metadata_query, search_query
from .infocuria import case_list_url, search_url


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


mcp = FastMCP(
    "curia-mcp",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8098")),
    log_level=os.environ.get("MCP_LOG_LEVEL", "INFO").upper(),
    streamable_http_path=os.environ.get("MCP_HTTP_PATH", "/mcp"),
    stateless_http=_truthy(os.environ.get("MCP_STATELESS_HTTP", "false")),
)


@mcp.tool()
def search_case_law(
    query: str = "",
    court: str = "",
    year_from: int = 0,
    year_to: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    """Search EU case-law metadata via the EUR-Lex/Cellar SPARQL endpoint.

    This matches on document **title and metadata** (court, year), not the full body
    text — Cellar's SPARQL graph does not index judgment bodies. For full-text search
    open the returned ``infocuria_search`` link in a browser.

    Args:
        query: Case-insensitive substring matched against the document title.
        court: Optional court filter — ``C`` (Court of Justice), ``T`` (General
            Court) or ``F`` (Civil Service Tribunal).
        year_from: Optional earliest document year (inclusive), e.g. ``2015``.
        year_to: Optional latest document year (inclusive).
        limit: Maximum number of rows (default 20).

    Returns:
        ``{"results": [...], "count": n, "infocuria_search": url}`` where each result
        has ``celex``, ``title``, ``date`` and the Cellar ``work`` URI. Pass a
        ``celex`` to ``fetch_case_text`` / ``fetch_case_metadata`` for the document.
    """
    q = search_query(
        title_contains=query or None,
        court_letter=court or None,
        year_from=year_from or None,
        year_to=year_to or None,
        limit=max(1, min(limit, 100)),
    )
    client = cellar_client()
    try:
        rows = client.sparql(q)
    except CellarError as exc:
        return {"error": str(exc), "results": [], "count": 0}
    finally:
        client.close()
    return {
        "results": rows,
        "count": len(rows),
        "infocuria_search": search_url(query) if query else None,
    }


@mcp.tool()
def fetch_case_metadata(celex: str) -> dict[str, Any]:
    """Fetch core metadata (title, ECLI, date) for a case by CELEX number.

    Args:
        celex: A case-law CELEX number, e.g. ``"62018CJ0159"``.
    """
    try:
        parsed = parse_celex(celex)
    except ValueError as exc:
        return {"error": str(exc)}
    client = cellar_client()
    try:
        rows = client.sparql(metadata_query(parsed["celex"]))
    except CellarError as exc:
        return {"error": str(exc), "celex": parsed["celex"]}
    finally:
        client.close()
    return {"celex": parsed["celex"], "parsed": parsed, "metadata": rows}


@mcp.tool()
def fetch_case_text(celex: str, language: str = "eng") -> dict[str, Any]:
    """Fetch a case document's full text from Cellar by CELEX number.

    Args:
        celex: A case-law CELEX number, e.g. ``"62018CJ0159"``.
        language: 3-letter ISO 639-2 language code (``eng``, ``fra``, ``deu``,
            ``ces`` …). Falls back with an error if that language is unavailable.

    Returns:
        ``{"celex": ..., "language": ..., "content": "<html…>"}`` — the content is
        the document body as served by Cellar (HTML).
    """
    if not is_celex(celex):
        return {"error": f"Not a case-law CELEX number: {celex!r}."}
    client = cellar_client()
    try:
        content = client.fetch_celex_content(celex.strip().upper(), language=language)
    except CellarError as exc:
        return {"error": str(exc), "celex": celex}
    finally:
        client.close()
    return {"celex": celex.strip().upper(), "language": language, "content": content}


@mcp.tool()
def lookup_case_number(case_number: str, language: str = "en") -> dict[str, Any]:
    """Resolve a CJEU case number (e.g. ``C-159/18``) to an InfoCuria deep link.

    A case number alone cannot be turned into a CELEX (the trailing year is when the
    case was *brought*, not the judgment year), so this returns the authoritative
    InfoCuria page to open in a browser, plus the parsed court/sequence/year.
    """
    try:
        case = parse_case_number(case_number)
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "case_number": case.normalised(),
        "court": case.court,
        "sequence": case.sequence,
        "year_brought": case.year,
        "infocuria_url": case_list_url(case.normalised(), language=language),
    }


@mcp.tool()
def identify_reference(value: str) -> dict[str, Any]:
    """Detect whether *value* is a CELEX number, an ECLI, or a CJEU case number.

    Useful to route a citation to the right tool: CELEX/ECLI -> ``fetch_case_*``,
    case number -> ``lookup_case_number``.
    """
    value = (value or "").strip()
    if is_celex(value):
        return {"kind": "celex", **parse_celex(value)}
    try:
        return {"kind": "ecli", **parse_ecli(value)}
    except ValueError:
        pass
    try:
        case = parse_case_number(value)
    except ValueError:
        return {"kind": "unknown", "value": value}
    return {
        "kind": "case_number",
        "case_number": case.normalised(),
        "court": case.court,
        "year_brought": case.year,
    }


def main() -> None:
    """Console-script entry point. Transport via ``MCP_TRANSPORT`` (stdio default)."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport in ("sse", "streamable-http"):
        mcp.run(transport=transport)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
