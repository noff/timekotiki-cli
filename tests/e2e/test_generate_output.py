import json
import os
from collections.abc import Callable
from pathlib import Path

import jsonschema
import pytest

from tests.conftest import DepsFactory, FakeTranscriber, topic_transcript
from tests.contract.test_json_schema import SCHEMA

TOPICS = [("Вступление", 240), ("Настройка проекта", 780), ("Итоги", 300)]


def test_us2_ac1_json_output(make_deps: DepsFactory, media_file: Callable[..., Path]) -> None:
    transcript = topic_transcript(TOPICS)
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", "--json", str(media_file())]) == 0
    document = json.loads(env.stdout.getvalue())
    jsonschema.validate(document, SCHEMA)
    assert [c["title"] for c in document["chapters"]] == [
        "Вступление",
        "Настройка проекта",
        "Итоги",
    ]
    assert document["duration"] == transcript.duration
    assert document["speech_language"] == "ru"


def test_format_json_equals_json_flag(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = topic_transcript(TOPICS)
    outputs = []
    for argv in (["--json"], ["--format", "json"]):
        env = make_deps(transcript, media_duration=transcript.duration)
        assert env.main(["generate", "--no-cache", *argv, str(media_file())]) == 0
        outputs.append(env.stdout.getvalue())
    assert outputs[0] == outputs[1]


def test_json_conflicts_with_other_format(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    env = make_deps(topic_transcript(TOPICS), media_duration=1320.0)
    assert env.main(["generate", "--json", "--format", "text", str(media_file())]) == 2


def test_us2_ac2_output_file_and_force(
    make_deps: DepsFactory, media_file: Callable[..., Path], tmp_path: Path
) -> None:
    transcript = topic_transcript(TOPICS)
    out = tmp_path / "chapters.txt"
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", "-o", str(out), str(media_file())]) == 0
    assert env.stdout.getvalue() == ""
    assert out.read_text(encoding="utf-8").startswith("00:00 Вступление\n")

    out.write_text("edited by hand", encoding="utf-8")
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", "-o", str(out), str(media_file())]) == 8
    assert out.read_text(encoding="utf-8") == "edited by hand"
    assert env.transcriber.calls == []  # refused before doing any work

    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", "-o", str(out), "--force", str(media_file())]) == 0
    assert out.read_text(encoding="utf-8").startswith("00:00 Вступление\n")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permissions")
def test_output_into_unwritable_dir(
    make_deps: DepsFactory, media_file: Callable[..., Path], tmp_path: Path
) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        env = make_deps(topic_transcript(TOPICS), media_duration=1320.0)
        assert env.main(["generate", "-o", str(locked / "out.txt"), str(media_file())]) == 8
    finally:
        locked.chmod(0o700)


def test_us2_ac3_vtt(make_deps: DepsFactory, media_file: Callable[..., Path]) -> None:
    transcript = topic_transcript(TOPICS)
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", "--format", "vtt", str(media_file())]) == 0
    out = env.stdout.getvalue()
    assert out.startswith("WEBVTT\n\n1\n00:00:00.000 --> 00:04:00.000\nВступление\n")


def test_interrupted_run_leaves_no_output(
    make_deps: DepsFactory, media_file: Callable[..., Path], tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    env = make_deps(transcriber=FakeTranscriber(exc=KeyboardInterrupt()), media_duration=100.0)
    assert env.main(["generate", "-o", str(out_dir / "c.txt"), str(media_file())]) == 130
    assert list(out_dir.iterdir()) == []
