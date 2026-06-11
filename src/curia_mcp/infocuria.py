"""Human-facing InfoCuria deep links.

InfoCuria (the Court of Justice's case-law site) has no API, but its legacy
``liste.jsf`` redirect still resolves a *case number* to that case's page, and the
new interface lives under ``/tabs``. We only **build URLs** here — we don't scrape
the JavaScript single-page app (its internal JSON endpoints are undocumented and
were only relaunched in January 2026). Returning a stable link lets a user open the
authoritative page in a browser while Cellar/EUR-Lex supplies the machine-readable
data (see :mod:`curia_mcp.eurlex`).
"""

from __future__ import annotations

from urllib.parse import quote

from .celex import CaseNumber, parse_case_number

INFOCURIA_BASE = "https://infocuria.curia.europa.eu"

# Languages InfoCuria accepts in its ``language`` query parameter (2-letter codes).
_SUPPORTED_LANGS = {"en", "fr", "de", "cs", "es", "it", "pl", "pt", "nl"}


def _lang(language: str) -> str:
    language = (language or "en").strip().lower()
    return language if language in _SUPPORTED_LANGS else "en"


def case_list_url(case_number: str, *, language: str = "en") -> str:
    """Deep link to a case's page on InfoCuria, by case number (e.g. ``C-159/18``).

    Uses the legacy ``liste.jsf`` redirect, which is stable and language-aware.
    """
    case: CaseNumber = parse_case_number(case_number)
    num = quote(case.normalised(), safe="")
    return (
        f"{INFOCURIA_BASE}/tabs/redirect/juris/liste.jsf"
        f"?num={num}&language={_lang(language)}"
    )


def search_url(query: str, *, language: str = "en") -> str:
    """Link that opens the new InfoCuria search UI pre-filled with *query*."""
    return f"{INFOCURIA_BASE}/tabs/tout?text={quote(query, safe='')}&language={_lang(language)}"
