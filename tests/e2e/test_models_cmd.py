import json

from tests.conftest import DepsFactory, FakeChapterModel, FakeTranscriber


def test_status_all_installed(make_deps: DepsFactory) -> None:
    env = make_deps()
    assert env.main(["models", "status"]) == 0
    lines = env.stdout.getvalue().splitlines()
    assert len(lines) == 2
    assert lines[0].split() == ["asr", "large-v3-turbo", "installed"]
    assert lines[1].split() == ["llm", "qwen2.5:7b-instruct", "installed"]


def test_status_missing_model(make_deps: DepsFactory) -> None:
    env = make_deps(transcriber=FakeTranscriber(installed=False))
    assert env.main(["models", "status"]) == 6
    assert "missing" in env.stdout.getvalue()
    assert "hint: timekotiki models pull" in env.stderr.getvalue()


def test_status_json(make_deps: DepsFactory) -> None:
    env = make_deps(chapter_model=FakeChapterModel(installed=False))
    assert env.main(["models", "status", "--json", "--asr-model", "small"]) == 6
    assert json.loads(env.stdout.getvalue()) == {
        "asr": {"model": "small", "installed": True},
        "llm": {"model": "qwen2.5:7b-instruct", "installed": False},
    }


def test_pull_downloads_both(make_deps: DepsFactory) -> None:
    env = make_deps(
        transcriber=FakeTranscriber(installed=False),
        chapter_model=FakeChapterModel(installed=False),
    )
    assert env.main(["models", "pull"]) == 0
    assert env.transcriber.pulled and env.chapter_model.pulled
    assert env.stdout.getvalue() == ""
    assert "large-v3-turbo" in env.stderr.getvalue()
    assert "qwen2.5:7b-instruct" in env.stderr.getvalue()
