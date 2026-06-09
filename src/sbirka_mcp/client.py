"""Thin HTTP client for the e-Sbírka / e-Legislativa public REST API.

Both APIs share one access key, supplied as the HTTP header ``esel-api-access-key``
(the ``ApiKey`` security scheme in the official OpenAPI definition). The key is read
from the ``ESEL_API_ACCESS_KEY`` environment variable and is never stored in the repo.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

ACCESS_KEY_HEADER = "esel-api-access-key"
ACCESS_KEY_ENV = "ESEL_API_ACCESS_KEY"

DEFAULT_ESBIRKA_BASE_URL = "https://api.e-sbirka.gov.cz"
DEFAULT_ELEGISLATIVA_BASE_URL = "https://api.e-legislativa.gov.cz/esel-eleg-lever"


class EselApiError(RuntimeError):
    """Raised when an e-Sbírka / e-Legislativa API call fails."""


def _access_key() -> str:
    key = os.environ.get(ACCESS_KEY_ENV, "").strip()
    if not key:
        raise EselApiError(
            f"Chybí přístupový klíč. Nastavte proměnnou prostředí {ACCESS_KEY_ENV} "
            "na klíč přidělený Ministerstvem vnitra."
        )
    return key


class EselClient:
    """Minimal JSON client for one e-Sbírka/e-Legislativa base URL."""

    def __init__(self, base_url: str, *, timeout: float | None = None) -> None:
        if timeout is None:
            timeout = float(os.environ.get("ESEL_API_TIMEOUT", "30"))
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                ACCESS_KEY_HEADER: _access_key(),
                "Accept": "application/json",
            },
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise EselApiError(f"Vypršel časový limit požadavku na {path}.") from exc
        except httpx.HTTPError as exc:
            raise EselApiError(f"Chyba spojení s API: {exc}") from exc

        if resp.status_code in (401, 403):
            raise EselApiError(
                "Přístup odmítnut (HTTP "
                f"{resp.status_code}). Zkontrolujte platnost přístupového klíče "
                f"v {ACCESS_KEY_ENV} a rozsah jeho oprávnění."
            )
        if resp.status_code == 404:
            raise EselApiError(f"Nenalezeno (HTTP 404): {path}")
        if resp.status_code == 429:
            raise EselApiError(
                "Překročen povolený počet volání (HTTP 429). Respektujte prosím "
                "sjednanou kvótu a volání zpomalte."
            )
        if resp.status_code >= 400:
            raise EselApiError(
                f"API vrátilo HTTP {resp.status_code} pro {path}: {resp.text[:500]}"
            )

        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, *, json: Any = None) -> Any:
        return self._request("POST", path, json=json)

    def close(self) -> None:
        self._client.close()


def esbirka_client() -> EselClient:
    base = os.environ.get("ESBIRKA_API_BASE_URL", DEFAULT_ESBIRKA_BASE_URL)
    return EselClient(base)


def elegislativa_client() -> EselClient:
    base = os.environ.get("ELEGISLATIVA_API_BASE_URL", DEFAULT_ELEGISLATIVA_BASE_URL)
    return EselClient(base)
