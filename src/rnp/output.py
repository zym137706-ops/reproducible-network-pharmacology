"""Output-directory handling: no accidental overwrite, no half-finished runs."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .errors import InputError


@contextmanager
def staged_output(out_dir: str | Path, *, force: bool = False) -> Iterator[Path]:
    """Yield a temporary sibling directory and atomically move it into place.

    * An existing output directory is an error unless ``force`` is set.
    * Nothing named ``out_dir`` exists until the block finishes successfully.
    * On failure the temporary directory is removed, so a crashed run cannot be
      mistaken for a completed one.
    """
    destination = Path(out_dir).resolve()
    if destination.exists():
        if not destination.is_dir():
            raise InputError(f"output path exists and is not a directory: {destination}")
        if not force:
            raise InputError(
                f"output directory already exists: {destination}",
                details=["choose a new --out/--run-id, or pass --force to replace it"],
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.tmp-", dir=destination.parent)
    )
    try:
        yield temporary
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def write_table_atomic(path: str | Path, write) -> None:
    """Write via a temporary file and rename; ``write`` receives the temp path."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        write(temporary)
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
