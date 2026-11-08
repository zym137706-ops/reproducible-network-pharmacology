"""Structure and sequence acquisition for ADR-0005.

A library only: there is no `rnp acquire` command yet.
"""

from .freeze import (
    RECORD_FILENAME,
    AcquisitionResult,
    acquire,
    verify_acquisition,
)
from .transport import (
    DEFAULT_TIMEOUT,
    Fetcher,
    FetchRequest,
    FetchResponse,
    NetworkError,
    urllib_fetcher,
)

__all__ = [
    "DEFAULT_TIMEOUT",
    "RECORD_FILENAME",
    "AcquisitionResult",
    "FetchRequest",
    "FetchResponse",
    "Fetcher",
    "NetworkError",
    "acquire",
    "urllib_fetcher",
    "verify_acquisition",
]
