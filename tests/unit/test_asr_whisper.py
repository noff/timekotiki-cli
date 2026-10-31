from pathlib import Path
from types import SimpleNamespace
from typing import Any

import faster_whisper
import pytest

from timekotiki import asr
from timekotiki.asr import FasterWhisperTranscriber
from timekotiki.errors import BackendUnavailableError, NoSpeechError


class FakeWhisperModel:
    instances: list["FakeWhisperModel"] = []
    segments: list[SimpleNamespace] = []
    load_error: Exception | None = None

    def __init__(self, name: str, **kwargs: Any) -> None:
        if FakeWhisperModel.load_error is not None:
            raise FakeWhisperModel.load_error
        self.name = name
        self.kwargs = kwargs
        self.transcribe_kwargs: dict[str, Any] = {}
        FakeWhisperModel.instances.append(self)

    def transcribe(self, audio: str, **kwargs: Any) -> tuple[Any, SimpleNamespace]:
        self.transcribe_kwargs = kwargs
        info = SimpleNamespace(language=kwargs.get("language") or "ru", duration=100.0)
        return iter(FakeWhisperModel.segments), info


@pytest.fixture(autouse=True)
def fake_whisper(monkeypatch: pytest.MonkeyPatch) -> type[FakeWhisperModel]:
    FakeWhisperModel.instances = []
    FakeWhisperModel.load_error = None
    FakeWhisperModel.segments = [
        SimpleNamespace(start=0.0, end=10.0, text=" Привет "),
        SimpleNamespace(start=10.0, end=12.0, text="   "),
        SimpleNamespace(start=12.0, end=50.0, text="мир"),
    ]
    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeWhisperModel)
    monkeypatch.setattr(asr, "_detect_device", lambda: "cpu")
    return FakeWhisperModel


def test_model_loaded_offline_int8_on_cpu(tmp_path: Path) -> None:
    FasterWhisperTranscriber("large-v3-turbo").transcribe(
        tmp_path / "a.wav", language=None, on_progress=lambda f: None
    )
    (instance,) = FakeWhisperModel.instances
    assert instance.name == "large-v3-turbo"
    assert instance.kwargs["local_files_only"] is True
    assert instance.kwargs["compute_type"] == "int8"
    assert instance.kwargs["device"] == "cpu"


def test_float16_on_cuda(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asr, "_detect_device", lambda: "cuda")
    FasterWhisperTranscriber("small").transcribe(
        tmp_path / "a.wav", language=None, on_progress=lambda f: None
    )
    assert FakeWhisperModel.instances[0].kwargs["compute_type"] == "float16"


def test_transcribe_converts_segments(tmp_path: Path) -> None:
    progress: list[float] = []
    t = FasterWhisperTranscriber("large-v3-turbo").transcribe(
        tmp_path / "a.wav", language="ru", on_progress=progress.append
    )
    kwargs = FakeWhisperModel.instances[0].transcribe_kwargs
    assert kwargs["vad_filter"] is True
    assert kwargs["language"] == "ru"
    assert [(s.index, s.start, s.end, s.text) for s in t.segments] == [
        (0, 0.0, 10.0, "Привет"),
        (1, 12.0, 50.0, "мир"),
    ]
    assert t.language == "ru"
    assert t.asr_model == "large-v3-turbo"
    assert t.duration == 100.0
    assert progress == [0.1, 0.12, 0.5]


def test_no_segments_is_no_speech(tmp_path: Path) -> None:
    FakeWhisperModel.segments = []
    with pytest.raises(NoSpeechError, match="no speech detected"):
        FasterWhisperTranscriber("small").transcribe(
            tmp_path / "a.wav", language=None, on_progress=lambda f: None
        )


def test_missing_model_is_backend_unavailable(tmp_path: Path) -> None:
    FakeWhisperModel.load_error = FileNotFoundError("not in cache")
    with pytest.raises(BackendUnavailableError) as info:
        FasterWhisperTranscriber("small").transcribe(
            tmp_path / "a.wav", language=None, on_progress=lambda f: None
        )
    assert info.value.hint == "timekotiki models pull"


def test_is_installed_and_pull(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    def download_model(name: str, local_files_only: bool = False, **kwargs: Any) -> str:
        calls.append((name, local_files_only))
        if local_files_only:
            raise FileNotFoundError(name)
        return "/models/" + name

    monkeypatch.setattr(faster_whisper, "download_model", download_model)
    t = FasterWhisperTranscriber("small")
    assert t.is_installed() is False
    done: list[float] = []
    t.pull(done.append)
    assert calls == [("small", True), ("small", False)]
    assert done == [1.0]
