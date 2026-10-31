import io
import json
import socket
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

import pytest

from timekotiki.errors import BackendUnavailableError, ProcessingError
from timekotiki.llm import OllamaChapterModel, clean_title, ollama_base_url
from timekotiki.models import Boundary

Handler = Callable[[str, dict[str, Any] | None], Any]


class FakeServer:
    """Replaces urllib.request.urlopen; `handler(path, body)` returns a dict, list or exception."""

    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.requests: list[tuple[str, dict[str, Any] | None]] = []

    def __call__(self, req: urllib.request.Request, timeout: float | None = None) -> io.BytesIO:
        path = req.full_url.split("11434", 1)[1]
        body = json.loads(req.data) if req.data else None  # type: ignore[arg-type]
        self.requests.append((path, body))
        reply = self.handler(path, body)
        if isinstance(reply, BaseException):
            raise reply
        if isinstance(reply, list):  # streaming
            return io.BytesIO(b"".join(json.dumps(r).encode() + b"\n" for r in reply))
        return io.BytesIO(json.dumps(reply).encode())


def chat_reply(content: Any) -> dict[str, Any]:
    text = content if isinstance(content, str) else json.dumps(content)
    return {"message": {"role": "assistant", "content": text}}


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], FakeServer]:
    def install(handler: Handler) -> FakeServer:
        fake = FakeServer(handler)
        monkeypatch.setattr(urllib.request, "urlopen", fake)
        return fake

    return install


def model() -> OllamaChapterModel:
    return OllamaChapterModel("qwen2.5:7b-instruct", "http://127.0.0.1:11434")


# --- loopback-only host --------------------------------------------------------------


def test_default_host() -> None:
    assert ollama_base_url({}) == "http://127.0.0.1:11434"


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("localhost", "http://localhost:11434"),
        ("127.0.0.5", "http://127.0.0.5:11434"),
        ("127.0.0.1:9999", "http://127.0.0.1:9999"),
        ("http://127.0.0.1:11434", "http://127.0.0.1:11434"),
        ("[::1]:11434", "http://[::1]:11434"),
        ("0.0.0.0", "http://127.0.0.1:11434"),
    ],
)
def test_loopback_hosts_accepted(host: str, expected: str) -> None:
    assert ollama_base_url({"OLLAMA_HOST": host}) == expected


@pytest.mark.parametrize("host", ["10.0.0.5:11434", "example.com", "https://ollama.example.com"])
def test_remote_hosts_rejected_without_lookup(host: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_dns(*args: object, **kwargs: object) -> None:
        raise AssertionError("must not resolve remote names")

    monkeypatch.setattr(socket, "getaddrinfo", no_dns)
    with pytest.raises(BackendUnavailableError, match="loopback"):
        ollama_base_url({"OLLAMA_HOST": host})


# --- availability -------------------------------------------------------------------


def test_connection_refused_hint(server: Callable[[Handler], FakeServer]) -> None:
    server(lambda path, body: urllib.error.URLError(ConnectionRefusedError()))
    with pytest.raises(BackendUnavailableError) as info:
        model().is_available()
    assert info.value.hint is not None and "ollama serve" in info.value.hint


def test_missing_model_hint(server: Callable[[Handler], FakeServer]) -> None:
    server(
        lambda path, body: urllib.error.HTTPError(path, 404, "not found", {}, None)  # type: ignore[arg-type]
    )
    with pytest.raises(BackendUnavailableError) as info:
        model().is_available()
    assert info.value.hint == "timekotiki models pull"
    assert model().is_installed() is False


def test_available(server: Callable[[Handler], FakeServer]) -> None:
    fake = server(lambda path, body: {"modelfile": "..."})
    model().is_available()
    assert fake.requests == [("/api/show", {"model": "qwen2.5:7b-instruct"})]


# --- chat ---------------------------------------------------------------------------


def test_find_boundaries_request_and_parse(server: Callable[[Handler], FakeServer]) -> None:
    fake = server(
        lambda path, body: chat_reply(
            {"boundaries": [{"segment": 3, "topic": "Настройка"}, {"segment": 9, "topic": "Тесты"}]}
        )
    )
    result = model().find_boundaries(["[3] 00:30 привет", "[9] 01:30 тесты"], "ru")
    assert result == [Boundary(3, "Настройка"), Boundary(9, "Тесты")]
    path, body = fake.requests[0]
    assert path == "/api/chat"
    assert body is not None
    assert body["model"] == "qwen2.5:7b-instruct"
    assert body["stream"] is False
    assert body["format"]["required"] == ["boundaries"]
    assert body["options"]["temperature"] == 0
    assert isinstance(body["options"]["seed"], int)
    assert "[9] 01:30 тесты" in body["messages"][-1]["content"]


def test_invalid_json_is_retried_once(server: Callable[[Handler], FakeServer]) -> None:
    replies = iter([chat_reply("not json"), chat_reply({"boundaries": []})])
    fake = server(lambda path, body: next(replies))
    assert model().find_boundaries(["[0] 00:00 x"], "ru") == []
    assert len(fake.requests) == 2


def test_invalid_json_twice_is_processing_error(server: Callable[[Handler], FakeServer]) -> None:
    server(lambda path, body: chat_reply({"wrong": True}))
    with pytest.raises(ProcessingError):
        model().find_boundaries(["[0] 00:00 x"], "ru")


def test_make_title_cleans_and_limits(server: Callable[[Handler], FakeServer]) -> None:
    long_title = "Очень длинный заголовок\nпро настройку проекта и всё остальное что было в видео"
    fake = server(lambda path, body: chat_reply({"title": long_title}))
    title = model().make_title("текст " * 5000, "en", "Настройка")
    assert len(title) <= 60
    assert "\n" not in title
    assert not title.endswith(" ")
    body = fake.requests[0][1]
    assert body is not None
    assert len(body["messages"][-1]["content"]) < 7000
    assert "English" in body["messages"][0]["content"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('  "Вступление."  ', "Вступление"),
        ("Глава: настройка", "Глава: настройка"),
        ("a " * 40, "a " * 29 + "a"),
        ("x" * 70, "x" * 60),
    ],
)
def test_clean_title(raw: str, expected: str) -> None:
    assert clean_title(raw) == expected


# --- pull ---------------------------------------------------------------------------


def test_pull_reports_progress(server: Callable[[Handler], FakeServer]) -> None:
    server(
        lambda path, body: [
            {"status": "pulling manifest"},
            {"status": "downloading", "total": 100, "completed": 50},
            {"status": "downloading", "total": 100, "completed": 100},
            {"status": "success"},
        ]
    )
    seen: list[float] = []
    model().pull(seen.append)
    assert seen[-1] == 1.0
    assert 0.5 in seen


def test_pull_error(server: Callable[[Handler], FakeServer]) -> None:
    server(lambda path, body: [{"error": "pull model manifest: file does not exist"}])
    with pytest.raises(BackendUnavailableError, match="file does not exist"):
        model().pull(lambda f: None)


# --- thinking models and timeouts ---------------------------------------------------


def test_thinking_disabled_when_model_supports_it(server: Callable[[Handler], FakeServer]) -> None:
    def handler(path: str, body: dict[str, Any] | None) -> Any:
        if path == "/api/show":
            return {"capabilities": ["completion", "thinking"]}
        return chat_reply({"title": "Настройка"})

    fake = server(handler)
    m = model()
    m.is_available()
    m.make_title("текст", "ru", None)
    body = fake.requests[-1][1]
    assert body is not None and body["think"] is False


def test_think_flag_omitted_for_regular_models(server: Callable[[Handler], FakeServer]) -> None:
    def handler(path: str, body: dict[str, Any] | None) -> Any:
        if path == "/api/show":
            return {"capabilities": ["completion"]}
        return chat_reply({"title": "Настройка"})

    fake = server(handler)
    m = model()
    m.is_available()
    m.make_title("текст", "ru", None)
    body = fake.requests[-1][1]
    assert body is not None and "think" not in body


def test_timeout_is_processing_error(server: Callable[[Handler], FakeServer]) -> None:
    server(lambda path, body: urllib.error.URLError(TimeoutError("timed out")))
    with pytest.raises(ProcessingError, match="did not answer"):
        model().make_title("текст", "ru", None)
