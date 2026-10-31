"""Local cache of transcripts, keyed by the content of the media file."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from pathlib import Path

from timekotiki.fsutil import atomic_write_text
from timekotiki.models import Transcript, TranscriptSegment

FORMAT_VERSION = 1
BLOCK_SIZE = 1024 * 1024


def cache_dir(env: Mapping[str, str], platform: str, home: Path) -> Path:
    if env.get("TIMEKOTIKI_CACHE_DIR"):
        return Path(env["TIMEKOTIKI_CACHE_DIR"])
    if platform == "darwin":
        return home / "Library" / "Caches" / "timekotiki"
    if platform == "win32":
        base = env.get("LOCALAPPDATA")
        return (Path(base) if base else home / "AppData" / "Local") / "timekotiki" / "Cache"
    base = env.get("XDG_CACHE_HOME")
    return (Path(base) if base else home / ".cache") / "timekotiki"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(BLOCK_SIZE):
            digest.update(block)
    return digest.hexdigest()


class TranscriptCache:
    def __init__(self, root: Path) -> None:
        self._dir = root / "transcripts"

    def _path(self, sha256: str, asr_model: str, language: str | None) -> Path:
        # Model names like "Systran/faster-whisper-small" must not create subdirectories.
        model = asr_model.replace("/", "_")
        return self._dir / f"{sha256}.{model}.{language or 'auto'}.json"

    def load(self, sha256: str, asr_model: str, language: str | None) -> Transcript | None:
        """The cached transcript, or None when absent, outdated or unreadable."""
        try:
            document = json.loads(self._path(sha256, asr_model, language).read_text("utf-8"))
            if document.get("format_version") != FORMAT_VERSION:
                return None
            return Transcript(
                segments=tuple(
                    TranscriptSegment(index=i, start=s["start"], end=s["end"], text=s["text"])
                    for i, s in enumerate(document["segments"])
                ),
                language=document["language"],
                asr_model=document["asr_model"],
                duration=document["duration"],
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save(self, sha256: str, language: str | None, transcript: Transcript) -> None:
        """Store `transcript` under the language that was requested (None = auto-detected)."""
        document = {
            "format_version": FORMAT_VERSION,
            "sha256": sha256,
            "asr_model": transcript.asr_model,
            "language": transcript.language,
            "duration": transcript.duration,
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text} for s in transcript.segments
            ],
        }
        self._dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self._path(sha256, transcript.asr_model, language),
            json.dumps(document, ensure_ascii=False),
        )

    def clear(self) -> None:
        shutil.rmtree(self._dir, ignore_errors=True)
