import re
from collections.abc import Callable
from pathlib import Path

from tests.conftest import DepsFactory, FakeTranscriber, make_wav, topic_transcript
from timekotiki.errors import NoSpeechError

LINE = re.compile(r"^(\d{2}:\d{2}|\d+:\d{2}:\d{2}) \S.*$")


def to_seconds(timecode: str) -> int:
    parts = [int(p) for p in timecode.split(":")]
    return sum(v * 60**i for i, v in enumerate(reversed(parts)))


def test_us1_ac1_chapters_for_30_minute_video(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = topic_transcript(
        [("Вступление", 240), ("Настройка проекта", 780), ("Парсер", 600), ("Итоги", 180)]
    )
    env = make_deps(transcript, media_duration=transcript.duration)
    code = env.main(["generate", str(media_file())])
    assert code == 0
    lines = env.stdout.getvalue().splitlines()
    assert lines == ["00:00 Вступление", "04:00 Настройка проекта", "17:00 Парсер", "27:00 Итоги"]
    assert all(LINE.match(line) for line in lines)
    seconds = [to_seconds(line.split(" ", 1)[0]) for line in lines]
    assert seconds == sorted(seconds)


def test_us1_ac2_hours_format_after_first_hour(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = topic_transcript(
        [("Начало", 1800), ("Середина", 1950), ("Итоги и вопросы", 600)], piece=60
    )
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", str(media_file())]) == 0
    assert env.stdout.getvalue().splitlines() == [
        "00:00 Начало",
        "30:00 Середина",
        "1:02:30 Итоги и вопросы",
    ]


def test_us1_ac3_progress_only_on_stderr(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = topic_transcript([("А", 300), ("Б", 300), ("В", 300)])
    env = make_deps(transcript, media_duration=transcript.duration, is_tty=True)
    assert env.main(["generate", str(media_file())]) == 0
    assert "Transcribing speech" in env.stderr.getvalue()
    assert "%" in env.stderr.getvalue()
    assert all(LINE.match(line) for line in env.stdout.getvalue().splitlines())


def test_quiet_flag_silences_stderr(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = topic_transcript([("А", 300), ("Б", 300), ("В", 300)])
    env = make_deps(transcript, media_duration=transcript.duration, is_tty=True)
    assert env.main(["generate", "-q", str(media_file())]) == 0
    assert env.stderr.getvalue() == ""


def test_us1_ac4_missing_file(make_deps: DepsFactory, tmp_path: Path) -> None:
    env = make_deps()
    assert env.main(["generate", str(tmp_path / "missing.mp4")]) == 3
    assert env.stdout.getvalue() == ""
    assert "timekotiki: error: file not found" in env.stderr.getvalue()


def test_no_speech(make_deps: DepsFactory, tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "silence.wav", 2.0)
    env = make_deps(transcriber=FakeTranscriber(exc=NoSpeechError("no speech detected")))
    assert env.main(["generate", str(wav)]) == 5
    assert env.stdout.getvalue() == ""
    assert "no speech detected" in env.stderr.getvalue()


def test_url_is_rejected(make_deps: DepsFactory) -> None:
    env = make_deps()
    assert env.main(["generate", "https://youtu.be/abc"]) == 3
    assert "only local files are supported" in env.stderr.getvalue()


def test_remote_ollama_host_is_refused(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = topic_transcript([("А", 300)])
    env = make_deps(
        transcript, media_duration=transcript.duration, env={"OLLAMA_HOST": "10.0.0.5:11434"}
    )
    assert env.main(["generate", str(media_file())]) == 6
    assert env.transcriber.calls == []
    assert env.chapter_model.windows == []


def test_interrupt_exit_code(make_deps: DepsFactory, media_file: Callable[..., Path]) -> None:
    env = make_deps(transcriber=FakeTranscriber(exc=KeyboardInterrupt()), media_duration=100.0)
    assert env.main(["generate", str(media_file())]) == 130
    assert env.stdout.getvalue() == ""


def test_model_names_are_passed_through(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = topic_transcript([("А", 300)])
    env = make_deps(transcript, media_duration=transcript.duration)
    argv = ["generate", "--asr-model", "small", "--llm-model", "llama3.1:8b", str(media_file())]
    assert env.main(argv) == 0
    assert env.asr_models == ["small"]
    assert env.llm_models == ["llama3.1:8b"]


def test_platform_warnings_go_to_stderr(
    make_deps: DepsFactory, media_file: Callable[..., Path]
) -> None:
    transcript = topic_transcript([("Единственная тема", 300)])
    env = make_deps(transcript, media_duration=transcript.duration)
    assert env.main(["generate", str(media_file())]) == 0
    assert env.stdout.getvalue() == "00:00 Единственная тема\n"
    assert "timekotiki: warning:" in env.stderr.getvalue()
