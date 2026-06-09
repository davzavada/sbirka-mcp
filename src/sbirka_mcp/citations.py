"""Helpers for turning Czech legal citations into e-Sbírka stálé URL / ELI paths.

e-Sbírka identifies a document in the collection ("Sbírka zákonů") by a *stálé URL*
such as ``/sb/2012/89`` (collection ``sb``, year ``2012``, number ``89``). The
``/dokumenty-sbirky`` endpoint takes that stálé URL as a single, URL-encoded path
segment, e.g. ``/dokumenty-sbirky/%2Fsb%2F2012%2F89``.
"""

from __future__ import annotations

import re
from urllib.parse import quote

# "89/2012 Sb.", "č. 89/2012 Sb.", "Zákon č. 89/2012 Sb." -> number=89, year=2012
_CITACE_RE = re.compile(
    r"(?:č\.?\s*)?(?P<cislo>\d+)\s*/\s*(?P<rok>\d{4})\s*Sb\.?",
    re.IGNORECASE,
)

# An ELI such as "/eli/cz/sb/2012/89/2024-04-01" -> collection sb, year, number.
_ELI_RE = re.compile(r"/eli/[^/]+/(?P<sbirka>[^/]+)/(?P<rok>\d{4})/(?P<cislo>\d+)")

# A bare stálé URL such as "/sb/2012/89" (optionally with a date version suffix).
_STALE_RE = re.compile(r"^/(?P<sbirka>[a-z]+)/(?P<rok>\d{4})/(?P<cislo>\d+)(?:/.*)?$")


def citace_to_stale_url(citace: str) -> str:
    """Normalise a citation or identifier to a stálé URL like ``/sb/2012/89``.

    Accepts a plain citation (``"89/2012 Sb."``), an ELI
    (``"/eli/cz/sb/2012/89/..."``) or an already-formed stálé URL (``"/sb/2012/89"``).

    Raises ``ValueError`` if nothing recognisable is found.
    """
    value = (citace or "").strip()
    if not value:
        raise ValueError("Prázdná citace.")

    m = _STALE_RE.match(value)
    if m:
        return f"/{m['sbirka']}/{m['rok']}/{m['cislo']}"

    m = _ELI_RE.search(value)
    if m:
        return f"/{m['sbirka']}/{m['rok']}/{m['cislo']}"

    m = _CITACE_RE.search(value)
    if m:
        return f"/sb/{m['rok']}/{m['cislo']}"

    raise ValueError(
        f"Nerozpoznaná citace či identifikátor: {citace!r}. "
        "Použijte např. '89/2012 Sb.', '/sb/2012/89' nebo ELI."
    )


def encode_stale_url(stale_url: str) -> str:
    """URL-encode a stálé URL into a single path segment (``/`` -> ``%2F``)."""
    return quote(stale_url, safe="")
