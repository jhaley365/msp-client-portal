"""
Async HTTP client for the Syncro MSP REST API.

Configuration is read from the environment:
    SYNCRO_API_KEY   – API key issued in Syncro → Admin → API Keys
    SYNCRO_SUBDOMAIN – the subdomain portion of your Syncro URL
                       e.g. "acme" for acme.syncromsp.com

Usage
-----
    async with SyncroClient() as client:
        tickets = await client.get_tickets(customer_id="42", status="open")
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------

_MAX_ATTEMPTS = 3
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_BACKOFF_BASE = 1.0  # seconds; delay = _BACKOFF_BASE * 2 ** (attempt - 1)


# ---------------------------------------------------------------------------
# Typed error
# ---------------------------------------------------------------------------


class SyncroAPIError(Exception):
    """Raised when a Syncro API call fails after all retry attempts.

    Attributes
    ----------
    status_code : int | None
        HTTP status code from the last response, or None for network errors.
    response_body : str
        Raw response body (truncated to 500 chars) from the last attempt.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    def __repr__(self) -> str:
        return (
            f"SyncroAPIError({self.args[0]!r}, "
            f"status_code={self.status_code!r})"
        )


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class SyncroTicket(BaseModel):
    """A single support ticket as returned by the Syncro API."""

    id: int
    number: int | None = None          # human-readable ticket number shown in Syncro UI
    subject: str
    status: str
    priority: str | None = None
    created_at: str
    updated_at: str
    assigned_tech: str | None = Field(default=None, alias="user_email")
    customer_name: str | None = None
    customer_id: int | None = None
    problem_type: str | None = None
    body: str | None = None

    model_config = {"populate_by_name": True}


class SyncroTicketList(BaseModel):
    """Paginated list of tickets from GET /tickets."""

    tickets: list[SyncroTicket]
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_pages(self) -> int | None:
        return self.meta.get("total_pages")

    @property
    def total_count(self) -> int | None:
        return self.meta.get("total_count")


class SyncroCustomer(BaseModel):
    """A customer record as returned by the Syncro API."""

    id: int
    firstname: str | None = None
    lastname: str | None = None
    business_name: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def display_name(self) -> str:
        if self.business_name:
            return self.business_name
        parts = filter(None, [self.firstname, self.lastname])
        return " ".join(parts) or f"Customer #{self.id}"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SyncroClient:
    """Async client for the Syncro MSP REST API.

    Reads ``SYNCRO_API_KEY`` and ``SYNCRO_SUBDOMAIN`` from the environment.
    Can be used as an async context manager to ensure the underlying
    ``httpx.AsyncClient`` is properly closed:

        async with SyncroClient() as client:
            ...

    Or manage the lifecycle manually:

        client = SyncroClient()
        await client.aclose()
    """

    def __init__(
        self,
        api_key: str | None = None,
        subdomain: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key or os.environ["SYNCRO_API_KEY"]
        subdomain = subdomain or os.environ["SYNCRO_SUBDOMAIN"]
        self._base_url = f"https://{subdomain}.syncromsp.com/api/v1"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> SyncroClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal request helper with retry + logging
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an HTTP request with exponential-backoff retry.

        Retries on HTTP 429 and 5xx responses, up to ``_MAX_ATTEMPTS`` total
        attempts.  Raises ``SyncroAPIError`` if all attempts fail or a
        non-retryable error status is received.

        Returns the parsed JSON body.
        """
        url = path  # httpx resolves against base_url
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            t0 = time.monotonic()
            try:
                response = await self._client.request(
                    method, url, params=params
                )
                elapsed_ms = (time.monotonic() - t0) * 1000
                logger.info(
                    "Syncro %s %s → %d (%.0f ms) attempt=%d",
                    method,
                    path,
                    response.status_code,
                    elapsed_ms,
                    attempt,
                )

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    body_preview = response.text[:500]
                    last_exc = SyncroAPIError(
                        f"Syncro returned {response.status_code} for "
                        f"{method} {path}",
                        status_code=response.status_code,
                        response_body=body_preview,
                    )
                    if attempt < _MAX_ATTEMPTS:
                        delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                        logger.warning(
                            "Retryable error %d on %s %s — "
                            "waiting %.1fs before attempt %d",
                            response.status_code,
                            method,
                            path,
                            delay,
                            attempt + 1,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise last_exc

                # Raise for any other 4xx (not retryable)
                if response.is_error:
                    raise SyncroAPIError(
                        f"Syncro returned {response.status_code} for "
                        f"{method} {path}",
                        status_code=response.status_code,
                        response_body=response.text[:500],
                    )

                return response.json()

            except httpx.TransportError as exc:
                elapsed_ms = (time.monotonic() - t0) * 1000
                logger.warning(
                    "Network error on %s %s (%.0f ms) attempt=%d: %s",
                    method,
                    path,
                    elapsed_ms,
                    attempt,
                    exc,
                )
                last_exc = SyncroAPIError(
                    f"Network error contacting Syncro: {exc}",
                    status_code=None,
                )
                if attempt < _MAX_ATTEMPTS:
                    delay = _BACKOFF_BASE * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                    continue
                raise last_exc from exc

        # Unreachable, but satisfies type checkers.
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_tickets(
        self,
        customer_id: int | str,
        status: str | None = None,
        page: int = 1,
        since_date: str | None = None,
    ) -> SyncroTicketList:
        """Fetch a paginated list of tickets for a customer.

        Parameters
        ----------
        customer_id:
            Syncro customer ID to filter by.
        status:
            Optional ticket status filter, e.g. ``"open"`` or ``"closed"``.
            When omitted, all statuses are returned.
        page:
            1-based page number.  Use ``SyncroTicketList.total_pages`` to
            determine whether additional pages exist.
        since_date:
            ISO-8601 date string (e.g. ``"2026-01-01"``).  When provided,
            only tickets created on or after this date are returned.

        Returns
        -------
        SyncroTicketList
            Parsed ticket list and pagination metadata.

        Raises
        ------
        SyncroAPIError
            On non-retryable API errors or exhausted retries.
        """
        params: dict[str, Any] = {"customer_id": customer_id, "page": page}
        if status is not None:
            params["status"] = status
        if since_date is not None:
            params["created_at[gt]"] = since_date

        data = await self._request("GET", "/tickets", params=params)
        return SyncroTicketList.model_validate(data)

    async def get_ticket(self, ticket_id: int | str) -> SyncroTicket:
        """Fetch a single ticket by its Syncro ID.

        Parameters
        ----------
        ticket_id:
            The numeric Syncro ticket ID.

        Returns
        -------
        SyncroTicket
            The parsed ticket record.

        Raises
        ------
        SyncroAPIError
            On non-retryable API errors or exhausted retries.
        """
        data = await self._request("GET", f"/tickets/{ticket_id}")
        # Syncro wraps single resources: {"ticket": {...}}
        ticket_data = data.get("ticket", data)
        return SyncroTicket.model_validate(ticket_data)

    async def get_customer(self, customer_id: int | str) -> SyncroCustomer:
        """Fetch a customer record by its Syncro ID.

        Parameters
        ----------
        customer_id:
            The numeric Syncro customer ID.

        Returns
        -------
        SyncroCustomer
            The parsed customer record.

        Raises
        ------
        SyncroAPIError
            On non-retryable API errors or exhausted retries.
        """
        data = await self._request("GET", f"/customers/{customer_id}")
        # Syncro wraps single resources: {"customer": {...}}
        customer_data = data.get("customer", data)
        return SyncroCustomer.model_validate(customer_data)
