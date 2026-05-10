from __future__ import annotations

from poe.exceptions import PoeError


class NinjaError(PoeError):
    """Base exception for all poe.ninja errors."""


class RateLimitError(NinjaError):
    """Raised when poe.ninja returns 429 after retries."""


class StaleDataError(NinjaError):
    """Raised when cached data is stale and no refresh is possible."""


class ApiSchemaError(NinjaError):
    """Raised when API response has unexpected format."""


class NetworkError(NinjaError):
    """Raised for HTTP transport failures."""
