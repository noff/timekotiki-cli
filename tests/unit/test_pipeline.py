import io
from pathlib import Path

import pytest

from tests.conftest import FakeChapterModel, FakeTranscriber, topic_transcript
from timekotiki.errors import BackendUnavailableError
from timekotiki.models import MediaSource, Options
from timekotiki.pipeline import run_pipeline
from timekotiki.progress import Progress


def quiet() -> Progress:
    return Progress(io.StringIO(), is_tty=False, quiet=True)


def test_stages_run_in_order_and_result_is_valid() -> None:
    events: list[str] = []
    transcript = topic_transcript([("Вступление", 120), ("Настройка", 600), ("Итоги", 300)])

    class Asr(FakeTranscriber):
        def transcribe(self, path, *, language, on_progress):  # type: ignore[no-untyped-def]
            events.append("transcribe")
            return super().transcribe(path, language=language, on_progress=on_progress)

    class Llm(FakeChapterModel):
        def is_available(self) -> None:
            events.append("available")

        def find_boundaries(self, window_lines, language):  # type: ignore[no-untyped-def]
            events.append("segment")
            return super().find_boundaries(window_lines, language)

        def make_title(self, text, language, topic_hint):  # type: ignore[no-untyped-def]
            events.append("title")
            return super().make_title(text, language, topic_hint)

    def probe(arg: str) -> MediaSource:
        events.append("probe")
        return MediaSource(Path(arg), transcript.duration, True)

    result = run_pipeline(
        "talk.mp4",
        Options(),
        probe=probe,
        transcriber=Asr(transcript=transcript),
        chapter_model=Llm(),
        progress=quiet(),
    )
    assert events[:3] == ["probe", "available", "transcribe"]
    assert "segment" in events
    assert events[-1] == "title"
    assert events.index("title") > max(i for i, e in enumerate(events) if e == "segment")
    assert [c.title for c in result.chapters] == ["Вступление", "Настройка", "Итоги"]
    assert [c.timecode for c in result.chapters] == ["00:00", "02:00", "12:00"]
    assert result.chapters[-1].end == transcript.duration
    assert result.speech_language == "ru"
    assert result.title_language == "ru"
    assert result.transcript_cached is False


def test_backend_checked_before_transcription() -> None:
    asr = FakeTranscriber(transcript=topic_transcript([("a", 100)]))
    llm = FakeChapterModel(available_exc=BackendUnavailableError("Ollama is not running"))
    with pytest.raises(BackendUnavailableError):
        run_pipeline(
            "talk.mp4",
            Options(),
            probe=lambda arg: MediaSource(Path(arg), 100.0, True),
            transcriber=asr,
            chapter_model=llm,
            progress=quiet(),
        )
    assert asr.calls == []


def test_empty_title_falls_back_to_hint() -> None:
    class Llm(FakeChapterModel):
        def make_title(self, text, language, topic_hint):  # type: ignore[no-untyped-def]
            return ""

    transcript = topic_transcript([("Вступление", 120), ("Код", 600)])
    result = run_pipeline(
        "talk.mp4",
        Options(),
        probe=lambda arg: MediaSource(Path(arg), transcript.duration, True),
        transcriber=FakeTranscriber(transcript=transcript),
        chapter_model=Llm(),
        progress=quiet(),
    )
    assert [c.title for c in result.chapters] == ["Вступление", "Код"]
