import json
from collections.abc import Callable
from pathlib import Path

from tests.conftest import DepsFactory, FakeTranscriber, topic_transcript

TOPICS = [("Вступление", 240), ("Настройка", 600), ("Итоги", 300)]


def run_twice(
    make_deps: DepsFactory, path: Path, first: list[str], second: list[str]
) -> tuple[FakeTranscriber, dict[str, object], str]:
    transcript = topic_transcript(TOPICS)
    asr = FakeTranscriber(transcript=transcript)
    env = make_deps(transcriber=asr, media_duration=transcript.duration)
    assert env.main(["generate", *first, str(path)]) == 0
    env = make_deps(transcriber=asr, media_duration=transcript.duration)
    assert env.main(["generate", "--json", *second, str(path)]) == 0
    return asr, json.loads(env.stdout.getvalue()), env.stderr.getvalue()


def test_us4_ac1_second_run_skips_transcription(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    asr, document, stderr = run_twice(make_deps, media_file(), [], ["--max-chapters", "2"])
    assert len(asr.calls) == 1
    assert document["transcript_cached"] is True
    assert len(document["chapters"]) == 2  # type: ignore[arg-type]
    assert "Transcribing speech: skipped (cached)" in stderr


def test_first_run_is_not_cached(make_deps: DepsFactory, media_file: Callable[..., Path]) -> None:
    transcript = topic_transcript(TOPICS)
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", "--json", str(media_file())]) == 0
    assert json.loads(env.stdout.getvalue())["transcript_cached"] is False


def test_us4_ac2_changed_file_is_transcribed_again(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = topic_transcript(TOPICS)
    asr = FakeTranscriber(transcript=transcript)
    path = media_file(content=b"version one")
    assert make_deps(transcriber=asr, media_duration=1140.0).main(["generate", str(path)]) == 0
    path.write_bytes(b"version two, re-encoded")
    assert make_deps(transcriber=asr, media_duration=1140.0).main(["generate", str(path)]) == 0
    assert len(asr.calls) == 2


def test_us4_ac3_no_cache_forces_transcription(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    asr, document, _ = run_twice(make_deps, media_file(), [], ["--no-cache"])
    assert len(asr.calls) == 2
    assert document["transcript_cached"] is False


def test_different_asr_model_is_a_miss(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    asr, document, _ = run_twice(make_deps, media_file(), [], ["--asr-model", "small"])
    assert len(asr.calls) == 2
    assert document["transcript_cached"] is False


def test_cache_clear(make_deps: DepsFactory, media_file: Callable[..., Path]) -> None:
    transcript = topic_transcript(TOPICS)
    asr = FakeTranscriber(transcript=transcript)
    path = media_file()
    assert make_deps(transcriber=asr, media_duration=1140.0).main(["generate", str(path)]) == 0
    env = make_deps(transcriber=asr)
    assert env.main(["cache", "clear"]) == 0
    assert make_deps(transcriber=asr).main(["cache", "clear"]) == 0  # already empty
    assert make_deps(transcriber=asr, media_duration=1140.0).main(["generate", str(path)]) == 0
    assert len(asr.calls) == 2
