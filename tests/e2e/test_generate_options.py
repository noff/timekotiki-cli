import json
from collections.abc import Callable
from pathlib import Path

from tests.conftest import DepsFactory, topic_transcript


def two_hour_stream():  # type: ignore[no-untyped-def]
    # 24 topics × 5 minutes = 2 hours
    return topic_transcript([(f"Тема номер {i}", 300) for i in range(24)], piece=60)


def test_us3_ac1_max_chapters(make_deps: DepsFactory, media_file: Callable[..., Path]) -> None:
    transcript = two_hour_stream()
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", "--max-chapters", "10", str(media_file())]) == 0
    lines = env.stdout.getvalue().splitlines()
    assert 1 <= len(lines) <= 10
    assert lines[0].startswith("00:00 ")


def test_us3_ac2_min_chapter(make_deps: DepsFactory, media_file: Callable[..., Path]) -> None:
    transcript = topic_transcript(
        [("А", 120), ("Б", 400), ("В", 90), ("Г", 600), ("Д", 200), ("Е", 500)]
    )
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", "--json", "--min-chapter", "5m", str(media_file())]) == 0
    chapters = json.loads(env.stdout.getvalue())["chapters"]
    assert all(c["end"] - c["start"] >= 300 for c in chapters[:-1])
    assert chapters[0]["start"] == 0


def test_us3_ac3_title_language(make_deps: DepsFactory, media_file: Callable[..., Path]) -> None:
    transcript = topic_transcript([("Вступление", 300), ("Код", 300), ("Итоги", 300)])
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", "--json", "--title-language", "en", str(media_file())]) == 0
    document = json.loads(env.stdout.getvalue())
    assert document["title_language"] == "en"
    assert document["speech_language"] == "ru"
    assert {language for _, language, _ in env.chapter_model.title_calls} == {"en"}


def test_speech_language_is_passed_to_transcriber(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = topic_transcript([("Intro", 300)], language="en")
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", "--json", "--speech-language", "ru", str(media_file())]) == 0
    assert env.transcriber.calls[0][1] == "ru"
    document = json.loads(env.stdout.getvalue())
    assert document["speech_language"] == "ru"
    assert document["title_language"] == "ru"


def test_options_block_reflects_applied_values(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = two_hour_stream()
    env = make_deps(transcript, media_duration=transcript.duration)
    argv = ["generate", "--json", "--min-chapter", "90", "--max-chapters", "8", str(media_file())]
    assert env.main(argv) == 0
    options = json.loads(env.stdout.getvalue())["options"]
    assert options["min_chapter"] == 90
    assert options["max_chapters"] == 8
