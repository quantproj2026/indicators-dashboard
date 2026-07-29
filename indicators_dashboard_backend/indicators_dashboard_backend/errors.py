"""Domain exceptions and the HTTP problem shape they are rendered into."""

from __future__ import annotations

from typing import Any

from fastapi import status


class UpstreamError(Exception):
    """Base class for every failure originating from Alpha Vantage."""

    status_code: int = status.HTTP_502_BAD_GATEWAY
    code: str = "upstream_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return {"error": payload}


class UpstreamUnavailableError(UpstreamError):
    """Network failure, timeout, or a 5xx from Alpha Vantage."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "upstream_unavailable"


class UpstreamRateLimitError(UpstreamError):
    """The daily/per-minute free-tier quota has been exhausted.

    Alpha Vantage signals this with HTTP 200 and an ``Information`` field, so it
    has to be detected from the body rather than the status code.
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "upstream_rate_limited"


class UpstreamInvalidRequestError(UpstreamError):
    """Alpha Vantage rejected the request (``Error Message`` in the body)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "upstream_invalid_request"


class UpstreamPayloadError(UpstreamError):
    """The response parsed, but did not look like an economic-indicator series."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "upstream_malformed_payload"


class ApiKeyMissingError(UpstreamError):
    """No ``ALPHA_VANTAGE_API_KEY`` is configured on the server."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "api_key_missing"

    def __init__(self) -> None:
        super().__init__(
            "ALPHA_VANTAGE_API_KEY is not configured on the server. "
            "Add it to indicators_dashboard_backend/.env and restart the API."
        )


class IndicatorNotFoundError(Exception):
    """The requested indicator slug is not in the catalog."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "indicator_not_found"

    def __init__(self, slug: str, known: list[str]) -> None:
        super().__init__(f"Unknown indicator '{slug}'.")
        self.message = f"Unknown indicator '{slug}'."
        self.details = {"requested": slug, "available": known}

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }
