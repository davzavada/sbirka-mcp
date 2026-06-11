"""Identifiers for EU case-law: CELEX numbers, ECLI, and CJEU case numbers.

These are pure, offline helpers (no network) so they can be unit-tested without
reaching Cellar / EUR-Lex / InfoCuria.

**CELEX** is the EUR-Lex document key. Case-law lives in *sector 6* and is shaped
``6`` + ``YYYY`` (document year) + a 1–2 letter *document descriptor* + a 4-digit
sequence, e.g. ``62018CJ0159`` = a 2018 **C**ourt of **J**ustice judgment, no. 0159.

**ECLI** (European Case Law Identifier) looks like ``ECLI:EU:C:2019:933`` —
``EU`` country code, a court code (``C`` Court of Justice, ``T`` General Court,
``F`` Civil Service Tribunal), the year, and an ordinal.

**Case numbers** are how humans cite a case on InfoCuria, e.g. ``C-159/18`` (Court
of Justice), ``T-79/16`` (General Court), ``F-1/05`` (Civil Service Tribunal). The
trailing two digits are the year the case was *brought*, which is **not** generally
the same as the CELEX/judgment year — so a case number alone cannot be turned into
a CELEX. Use it for an InfoCuria lookup (:mod:`curia_mcp.infocuria`) instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Common sector-6 (case-law) CELEX document descriptors. Not exhaustive, but covers
# the documents people usually want. Source: EUR-Lex "How to use CELEX numbers".
CELEX_CASELAW_DESCRIPTORS: dict[str, str] = {
    "CJ": "Judgment of the Court of Justice",
    "CO": "Order of the Court of Justice",
    "CC": "Opinion of the Advocate General",
    "CP": "View of the Advocate General",
    "CV": "Opinion of the Court",
    "CN": "Notice (new case, OJ C)",
    "CB": "Information communicated by the Court",
    "CD": "Decision of the Court",
    "CA": "Judgment of the Court (additional / interpretation)",
    "TJ": "Judgment of the General Court",
    "TO": "Order of the General Court",
    "TC": "Opinion / view (General Court)",
    "TN": "Notice (new case, General Court)",
    "FJ": "Judgment of the Civil Service Tribunal",
    "FO": "Order of the Civil Service Tribunal",
}

# Map an InfoCuria case-number prefix letter to the court it belongs to.
CASE_NUMBER_COURTS: dict[str, str] = {
    "C": "Court of Justice",
    "T": "General Court",
    "F": "Civil Service Tribunal",
}

_CELEX_RE = re.compile(
    r"^(?P<sector>6)(?P<year>\d{4})(?P<descriptor>[A-Z]{1,2})(?P<number>\d{4})"
    r"(?P<suffix>\([0-9]{2}\))?$"
)

_ECLI_RE = re.compile(
    r"^ECLI:EU:(?P<court>[A-Z]):(?P<year>\d{4}):(?P<ordinal>\d+)$",
    re.IGNORECASE,
)

# "C-159/18", "C-159/18 P" (appeal suffix), "Joined cases C-403/08 ..." -> first num.
_CASE_NUMBER_RE = re.compile(
    r"(?P<court>[CTF])[-‑\s]?(?P<seq>\d{1,4})\s*/\s*(?P<year>\d{4}|\d{2})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CaseNumber:
    """A parsed CJEU case number such as ``C-159/18``."""

    court_letter: str  # "C", "T" or "F"
    sequence: int  # e.g. 159
    year: int  # full 4-digit year the case was brought, e.g. 2018

    @property
    def court(self) -> str:
        return CASE_NUMBER_COURTS.get(self.court_letter, "Unknown court")

    def normalised(self) -> str:
        """Canonical form, e.g. ``C-159/18`` (two-digit year as InfoCuria expects)."""
        return f"{self.court_letter}-{self.sequence}/{self.year % 100:02d}"


def is_celex(value: str) -> bool:
    """True if *value* looks like a case-law (sector 6) CELEX number."""
    return bool(_CELEX_RE.match((value or "").strip().upper()))


def parse_celex(value: str) -> dict[str, str]:
    """Break a case-law CELEX number into its parts.

    Raises ``ValueError`` if *value* is not a sector-6 CELEX number.
    """
    m = _CELEX_RE.match((value or "").strip().upper())
    if not m:
        raise ValueError(
            f"Not a case-law CELEX number: {value!r}. Expected e.g. '62018CJ0159'."
        )
    descriptor = m["descriptor"]
    return {
        "celex": m.group(0),
        "sector": m["sector"],
        "year": m["year"],
        "descriptor": descriptor,
        "number": m["number"],
        "document_type": CELEX_CASELAW_DESCRIPTORS.get(descriptor, "Unknown document type"),
    }


def parse_ecli(value: str) -> dict[str, str]:
    """Validate and split an ECLI such as ``ECLI:EU:C:2019:933``."""
    m = _ECLI_RE.match((value or "").strip())
    if not m:
        raise ValueError(
            f"Not an EU ECLI: {value!r}. Expected e.g. 'ECLI:EU:C:2019:933'."
        )
    court = m["court"].upper()
    return {
        "ecli": f"ECLI:EU:{court}:{m['year']}:{m['ordinal']}",
        "court_letter": court,
        "court": CASE_NUMBER_COURTS.get(court, "Unknown court"),
        "year": m["year"],
        "ordinal": m["ordinal"],
    }


def parse_case_number(value: str) -> CaseNumber:
    """Parse a CJEU case number like ``C-159/18`` into a :class:`CaseNumber`.

    Years are expanded with a 100-year window: ``50``–``99`` -> 19xx, ``00``–``49``
    -> 20xx (the EU courts started in the 1950s, so this is safe in practice).

    Raises ``ValueError`` if no case number can be found in *value*.
    """
    m = _CASE_NUMBER_RE.search(value or "")
    if not m:
        raise ValueError(
            f"No case number found in {value!r}. Expected e.g. 'C-159/18'."
        )
    raw_year = m["year"]
    if len(raw_year) == 4:
        full_year = int(raw_year)
    else:
        yy = int(raw_year)
        full_year = 1900 + yy if yy >= 50 else 2000 + yy
    return CaseNumber(
        court_letter=m["court"].upper(),
        sequence=int(m["seq"]),
        year=full_year,
    )
