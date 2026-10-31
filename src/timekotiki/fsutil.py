"""Crash-safe file output."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from timekotiki.errors import OutputConflictError


def atomic_write_text(path: Path, text: str) -> None:
    """Write `text` so that `path` holds either its old content or the new one, never a mix."""
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(name)
    try:
        with open(fd, "w", encoding="utf-8") as tmp:
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()


def check_output_target(path: Path, *, force: bool) -> None:
    """Fail before any work is done if `path` cannot or must not be written."""
    if path.exists() and not force:
        raise OutputConflictError(
            f"output file already exists: {path}", hint="pass --force to overwrite it"
        )
    if path.is_dir():
        raise OutputConflictError(f"output path is a directory: {path}")
    parent = path.parent
    if not parent.is_dir():
        raise OutputConflictError(f"output directory does not exist: {parent}")
    if not os.access(parent, os.W_OK | os.X_OK):
        raise OutputConflictError(f"output directory is not writable: {parent}")
