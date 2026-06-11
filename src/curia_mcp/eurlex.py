"""Thin client for the EU Publications Office **Cellar** repository.

Cellar is public and needs no registration. We use two of its faces:

* the **SPARQL endpoint** (``https://publications.europa.eu/webapi/rdf/sparql``) for
  metadata queries over case-law works (court, date, CELEX, ECLI, title);
* **REST content negotiation** by CELEX number
  (``https://publications.europa.eu/resource/celex/{CELEX}``) to fetch a document's
  full text in a chosen language.

Cellar uses 3-letter ISO 639-2 language codes (``eng``, ``fra``, ``deu``, ``ces`` …).

Network configuration comes from the environment so it can be pointed at a mirror or
given a longer timeout: ``CELLAR_SPARQL_URL``, ``CELLAR_RESOURCE_BASE``,
``CURIA_HTTP_TIMEOUT`` (seconds), ``CURIA_USER_AGENT``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
DEFAULT_RESOURCE_BASE = "https://publications.europa.eu/resource/celex"
DEFAULT_USER_AGENT = "curia-mcp/0.1 (+https://github.com/davzavada/sbirka-mcp)"

# cdm ontology prefix used throughout Cellar's RDF model.
CDM = "http://publications.europa.eu/ontology/cdm#"


class CellarError(RuntimeError):
    """Raised when a Cellar / EUR-Lex request fails."""


def _timeout() -> float:
    return float(os.environ.get("CURIA_HTTP_TIMEOUT", "30"))


def _user_agent() -> str:
    return os.environ.get("CURIA_USER_AGENT", DEFAULT_USER_AGENT)


class CellarClient:
    """Minimal HTTP client for Cellar SPARQL + REST content negotiation."""

    def __init__(self) -> None:
        self._sparql_url = os.environ.get("CELLAR_SPARQL_URL", DEFAULT_SPARQL_URL)
        self._resource_base = os.environ.get(
            "CELLAR_RESOURCE_BASE", DEFAULT_RESOURCE_BASE
        ).rstrip("/")
        self._client = httpx.Client(
            timeout=_timeout(),
            follow_redirects=True,
            headers={"User-Agent": _user_agent()},
        )

    # -- SPARQL -----------------------------------------------------------
    def sparql(self, query: str) -> list[dict[str, Any]]:
        """Run a SPARQL SELECT and return its bindings as a list of flat dicts.

        Each result row becomes ``{var: value}`` using the literal/IRI value of
        every bound variable (unbound variables are omitted).
        """
        try:
            resp = self._client.get(
                self._sparql_url,
                params={"query": query, "format": "application/sparql-results+json"},
                headers={"Accept": "application/sparql-results+json"},
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network
            raise CellarError(f"SPARQL request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise CellarError(
                f"SPARQL endpoint returned HTTP {resp.status_code}: {resp.text[:300]}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise CellarError("SPARQL endpoint did not return JSON.") from exc

        rows: list[dict[str, Any]] = []
        for binding in data.get("results", {}).get("bindings", []):
            rows.append({var: cell.get("value") for var, cell in binding.items()})
        return rows

    # -- REST content negotiation ----------------------------------------
    def fetch_celex_content(
        self,
        celex: str,
        *,
        language: str = "eng",
        accept: str = "text/html, application/xhtml+xml",
    ) -> str:
        """Fetch a document's content from Cellar by CELEX number.

        Returns the raw body (HTML by default). Cellar answers ``406``/``300`` when
        the requested language/format is unavailable; those surface as
        :class:`CellarError` so the caller can retry with another language.
        """
        url = f"{self._resource_base}/{celex}"
        try:
            resp = self._client.get(
                url,
                headers={"Accept": accept, "Accept-Language": language},
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network
            raise CellarError(f"Cellar request for {celex} failed: {exc}") from exc

        if resp.status_code == 300:
            raise CellarError(
                f"Cellar has multiple variants for {celex} and none matched language "
                f"{language!r}/format. Try another language."
            )
        if resp.status_code == 406:
            raise CellarError(
                f"Cellar has no {language!r} variant of {celex} in the requested format."
            )
        if resp.status_code == 404:
            raise CellarError(f"No Cellar document found for CELEX {celex}.")
        if resp.status_code >= 400:
            raise CellarError(
                f"Cellar returned HTTP {resp.status_code} for {celex}: {resp.text[:300]}"
            )
        return resp.text

    def close(self) -> None:
        self._client.close()


def cellar_client() -> CellarClient:
    return CellarClient()


# --- SPARQL query builders ----------------------------------------------
# NOTE: These target Cellar's `cdm` ontology. The shapes below are the documented
# model, but the live endpoint is the source of truth — tune predicates against a
# captured query if a field comes back empty.

def metadata_query(celex: str) -> str:
    """SPARQL to fetch core metadata for one case-law work by CELEX number."""
    return f"""
PREFIX cdm: <{CDM}>
SELECT DISTINCT ?work ?title ?ecli ?date ?celex WHERE {{
  ?work cdm:resource_legal_id_celex ?celex .
  FILTER(STR(?celex) = "{celex}")
  OPTIONAL {{ ?work cdm:case-law_ecli ?ecli . }}
  OPTIONAL {{ ?work cdm:work_date_document ?date . }}
  OPTIONAL {{
    ?expr cdm:expression_belongs_to_work ?work ;
          cdm:expression_title ?title .
  }}
}} LIMIT 5
"""


def search_query(
    *,
    title_contains: str | None = None,
    court_letter: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    limit: int = 20,
) -> str:
    """Build a SPARQL SELECT over case-law works, filtered by the given criteria.

    ``court_letter`` is ``C``/``T``/``F`` and is matched against the CELEX descriptor
    family (``CJ``/``CO`` … for ``C``). ``title_contains`` is a case-insensitive
    substring match on the document title. This searches **metadata/titles**, not the
    full body text (Cellar SPARQL does not index judgment bodies).
    """
    descriptor_prefix = {"C": "C", "T": "T", "F": "F"}.get(
        (court_letter or "").upper(), ""
    )
    filters = ['FILTER(STRSTARTS(STR(?celex), "6"))']
    if descriptor_prefix:
        # e.g. matches 6YYYY C J 0159 -> 5th char (index 5) is the court family letter.
        filters.append(
            f'FILTER(SUBSTR(STR(?celex), 6, 1) = "{descriptor_prefix}")'
        )
    if year_from is not None:
        filters.append(f"FILTER(?yearNum >= {int(year_from)})")
    if year_to is not None:
        filters.append(f"FILTER(?yearNum <= {int(year_to)})")
    title_block = ""
    if title_contains:
        safe = title_contains.replace('"', '\\"')
        title_block = (
            "?expr cdm:expression_belongs_to_work ?work ; "
            "cdm:expression_title ?title .\n"
            f'  FILTER(CONTAINS(LCASE(STR(?title)), LCASE("{safe}")))'
        )
    else:
        title_block = (
            "OPTIONAL { ?expr cdm:expression_belongs_to_work ?work ; "
            "cdm:expression_title ?title . }"
        )
    year_bind = "BIND(xsd:integer(SUBSTR(STR(?celex), 2, 4)) AS ?yearNum)"
    return f"""
PREFIX cdm: <{CDM}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?work ?celex ?title ?date WHERE {{
  ?work cdm:resource_legal_id_celex ?celex .
  {year_bind}
  {title_block}
  OPTIONAL {{ ?work cdm:work_date_document ?date . }}
  {chr(10).join("  " + f for f in filters)}
}} ORDER BY DESC(?date) LIMIT {int(limit)}
"""
