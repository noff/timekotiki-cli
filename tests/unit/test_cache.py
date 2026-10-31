import hashlib
import json
from pathlib import Path

import pytest

from tests.conftest import make_transcript
from timekotiki import cache as cache_module
from timekotiki.cache import TranscriptCache, cache_dir, file_sha256

HOME = Path("/home/user")


def test_cache_dir_env_override() -> None:
    assert cache_dir({"TIMEKOTIKI_CACHE_DIR": "/tmp/tk"}, "linux", HOME) == Path("/tmp/tk")


def test_cache_dir_linux() -> None:
    assert cache_dir({}, "linux", HOME) == HOME / ".cache/timekotiki"
    assert cache_dir({"XDG_CACHE_HOME": "/xdg"}, "linux", HOME) == Path("/xdg/timekotiki")


def test_cache_dir_macos() -> None:
    assert cache_dir({}, "darwin", HOME) == HOME / "Library/Caches/timekotiki"


def test_cache_dir_windows() -> None:
    env = {"LOCALAPPDATA": "C:/Users/u/AppData/Local"}
    assert cache_dir(env, "win32", HOME) == Path("C:/Users/u/AppData/Local/timekotiki/Cache")


def test_file_sha256_streams_in_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = b"x" * (3 * 1024 * 1024 + 5)
    path = tmp_path / "v.mp4"
    path.write_bytes(data)
    assert cache_module.BLOCK_SIZE == 1024 * 1024
    assert file_sha256(path) == hashlib.sha256(data).hexdigest()


def test_round_trip_and_key_layout(tmp_path: Path) -> None:
    store = TranscriptCache(tmp_path)
    transcript = make_transcript([(10, "привет"), (5, "мир")])
    store.save("ab" * 32, None, transcript)
    expected = tmp_path / "transcripts" / f"{'ab' * 32}.large-v3-turbo.auto.json"
    assert expected.is_file()
    assert store.load("ab" * 32, "large-v3-turbo", None) == transcript
    assert store.load("ab" * 32, "small", None) is None
    assert store.load("ab" * 32, "large-v3-turbo", "ru") is None


def test_wrong_version_or_corrupt_entry_is_a_miss(tmp_path: Path) -> None:
    store = TranscriptCache(tmp_path)
    transcript = make_transcript([(10, "привет")])
    store.save("cd" * 32, "ru", transcript)
    path = tmp_path / "transcripts" / f"{'cd' * 32}.large-v3-turbo.ru.json"
    document = json.loads(path.read_text())
    assert document["format_version"] == 1
    document["format_version"] = 99
    path.write_text(json.dumps(document))
    assert store.load("cd" * 32, "large-v3-turbo", "ru") is None
    path.write_text("{not json")
    assert store.load("cd" * 32, "large-v3-turbo", "ru") is None


def test_save_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Path] = []
    real = cache_module.atomic_write_text

    def spy(path: Path, text: str) -> None:
        calls.append(path)
        real(path, text)

    monkeypatch.setattr(cache_module, "atomic_write_text", spy)
    TranscriptCache(tmp_path).save("ef" * 32, None, make_transcript([(1, "a")]))
    assert len(calls) == 1


def test_clear(tmp_path: Path) -> None:
    store = TranscriptCache(tmp_path / "c")
    store.clear()  # nothing to clear
    store.save("01" * 32, None, make_transcript([(1, "a")]))
    store.clear()
    assert not (tmp_path / "c" / "transcripts").exists()
