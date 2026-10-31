import os
from pathlib import Path

import pytest

from timekotiki import fsutil
from timekotiki.errors import OutputConflictError
from timekotiki.fsutil import atomic_write_text, check_output_target


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    atomic_write_text(target, "привет\n")
    assert target.read_text(encoding="utf-8") == "привет\n"
    assert os.listdir(tmp_path) == ["out.txt"]


def test_atomic_write_keeps_old_content_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.txt"
    target.write_text("old", encoding="utf-8")

    def boom(src: str, dst: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(fsutil.os, "replace", boom)
    with pytest.raises(OSError):
        atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "old"
    assert os.listdir(tmp_path) == ["out.txt"]


def test_check_output_target_conflict(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("x")
    with pytest.raises(OutputConflictError):
        check_output_target(target, force=False)
    check_output_target(target, force=True)


def test_check_output_target_new_file_ok(tmp_path: Path) -> None:
    check_output_target(tmp_path / "new.txt", force=False)


def test_check_output_target_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(OutputConflictError):
        check_output_target(tmp_path / "nope" / "out.txt", force=False)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permissions")
def test_check_output_target_unwritable_dir(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        with pytest.raises(OutputConflictError):
            check_output_target(locked / "out.txt", force=False)
    finally:
        locked.chmod(0o700)
