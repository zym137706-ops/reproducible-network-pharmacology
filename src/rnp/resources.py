"""Locate package resources both in the source tree and in an installed wheel."""

from __future__ import annotations

from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Return a packaged resource, falling back to the repository layout."""
    packaged = Path(__file__).resolve().parent.joinpath(*parts)
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parents[2].joinpath(*parts)


def r_script(name: str) -> Path:
    return resource_path("R", name)
