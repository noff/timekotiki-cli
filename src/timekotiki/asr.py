"""Speech recognition backends."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from timekotiki.errors import BackendUnavailableError, NoSpeechError, ProcessingError
from timekotiki.models import Transcript, TranscriptSegment

ProgressCallback = Callable[[float], None]


class Transcriber(Protocol):
    model_name: str

    def transcribe(
        self, path: Path, *, language: str | None, on_progress: ProgressCallback
    ) -> Transcript:
        """Return time-stamped speech; raise NoSpeechError when nothing was recognised."""
        ...

    def is_installed(self) -> bool:
        """Whether the model is available locally, checked without network access."""
        ...

    def pull(self, on_progress: ProgressCallback) -> None:
        """Download the model. The only network operation of this backend."""
        ...


def _detect_device() -> str:
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


class FasterWhisperTranscriber:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            import faster_whisper

            device = _detect_device()
            try:
                self._model = faster_whisper.WhisperModel(
                    self.model_name,
                    device=device,
                    compute_type="float16" if device == "cuda" else "int8",
                    local_files_only=True,
                )
            except (OSError, ValueError) as exc:
                raise BackendUnavailableError(
                    f"ASR model {self.model_name} is not installed",
                    hint="timekotiki models pull",
                ) from exc
        return self._model

    def transcribe(
        self, path: Path, *, language: str | None, on_progress: ProgressCallback
    ) -> Transcript:
        model = self._load()
        try:
            pieces, info = model.transcribe(
                str(path),
                language=language,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            duration = float(info.duration)
            segments: list[TranscriptSegment] = []
            for piece in pieces:
                text = piece.text.strip()
                if text:
                    start = max(0.0, float(piece.start))
                    segments.append(
                        TranscriptSegment(
                            index=len(segments),
                            start=start,
                            end=max(start, float(piece.end)),
                            text=text,
                        )
                    )
                if duration > 0:
                    on_progress(min(1.0, float(piece.end) / duration))
        except (RuntimeError, ValueError, OSError) as exc:
            raise ProcessingError(f"speech recognition failed: {exc}") from exc
        if not segments:
            raise NoSpeechError(f"no speech detected in {path.name}")
        return Transcript(
            segments=tuple(segments),
            language=str(info.language),
            asr_model=self.model_name,
            duration=duration,
        )

    def is_installed(self) -> bool:
        import faster_whisper

        try:
            faster_whisper.download_model(self.model_name, local_files_only=True)
        except (OSError, ValueError):
            return False
        return True

    def pull(self, on_progress: ProgressCallback) -> None:
        import faster_whisper

        try:
            faster_whisper.download_model(self.model_name)
        except (OSError, ValueError) as exc:
            raise BackendUnavailableError(
                f"cannot download ASR model {self.model_name}: {exc}"
            ) from exc
        on_progress(1.0)
