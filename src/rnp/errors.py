"""Error types and exit codes.

Exit code contract (documented in docs/architecture.md):

* ``0`` — success
* ``2`` — validation/configuration error: nothing was written
* ``3`` — partial result: some inputs were processed, at least one failed
* ``1`` — unexpected internal error (bug, not a data problem)
"""

from __future__ import annotations

from typing import Any


class RnpError(Exception):
    """Base class for expected, user-facing errors."""

    exit_code = 2

    def __init__(self, message: str, *, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []

    def render(self) -> str:
        lines = [self.message]
        lines.extend(f"  - {d}" for d in self.details)
        return "\n".join(lines)


class ConfigError(RnpError):
    """The run config is missing, unreadable, or violates its JSON Schema."""

    exit_code = 2


class InputError(RnpError):
    """A declared input is missing or cannot be parsed."""

    exit_code = 2


class PartialResult(RnpError):
    """Some files were processed and at least one failed; outputs are incomplete."""

    exit_code = 3


class ExternalToolError(RnpError):
    """An external process (Rscript) failed or did not exit cleanly.

    A non-zero process status is authoritative even when its output files look
    normal, so this is never downgraded to a successful enrichment.
    """

    exit_code = 3


class SchemaViolation(RnpError):
    """An output artifact does not satisfy its schema (an internal consistency bug)."""

    exit_code = 1


def exit_code_for(exc: BaseException) -> int:
    if isinstance(exc, RnpError):
        return exc.exit_code
    return 1


def as_json_error(exc: RnpError) -> dict[str, Any]:
    return {"error": exc.message, "details": exc.details, "exit_code": exc.exit_code}
