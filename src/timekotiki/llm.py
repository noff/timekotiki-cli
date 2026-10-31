"""Local LLM backends that split a transcript into topics and title them."""

from __future__ import annotations

import ipaddress
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from typing import Any, Protocol

from timekotiki.errors import BackendUnavailableError, ProcessingError
from timekotiki.models import MAX_TITLE_LENGTH, Boundary

ProgressCallback = Callable[[float], None]

DEFAULT_OLLAMA_HOST = "127.0.0.1:11434"
DEFAULT_OLLAMA_PORT = 11434
REQUEST_TIMEOUT = 300.0
SEED = 42
TITLE_INPUT_LIMIT = 6000

LANGUAGE_NAMES = {
    "ru": "Russian",
    "en": "English",
    "uk": "Ukrainian",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
}

BOUNDARIES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "boundaries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"segment": {"type": "integer"}, "topic": {"type": "string"}},
                "required": ["segment", "topic"],
            },
        }
    },
    "required": ["boundaries"],
}

TITLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}

BOUNDARIES_PROMPT = """\
You split video transcripts into chapters.
Each input line is "[index] timecode text" for one transcript segment.
Return the indices of the segments where a NEW topic starts, with a few words naming
the topic in {language}. A topic usually lasts 3-15 minutes; ignore small digressions.
If the whole excerpt continues one topic, return an empty list."""

TITLE_PROMPT = """\
You write chapter titles for video descriptions.
Write one short, specific title (at most {limit} characters) in {language} for the
transcript excerpt you are given. No quotes, no trailing period, no numbering."""


class ChapterModel(Protocol):
    model_name: str

    def is_available(self) -> None:
        """Raise BackendUnavailableError unless the model can be used right now."""
        ...

    def is_installed(self) -> bool:
        """Whether the model is available locally."""
        ...

    def pull(self, on_progress: ProgressCallback) -> None:
        """Download the model. The only network operation of this backend."""
        ...

    def find_boundaries(self, window_lines: list[str], language: str) -> list[Boundary]:
        """Return the segments in this window where a new topic starts."""
        ...

    def make_title(self, text: str, language: str, topic_hint: str | None) -> str:
        """Return a short chapter title for `text` in `language`."""
        ...


def ollama_base_url(env: Mapping[str, str]) -> str:
    """Base URL of the Ollama server; refuses anything that is not this machine."""
    raw = env.get("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST
    parts = urllib.parse.urlsplit(raw if "://" in raw else f"http://{raw}")
    host = parts.hostname or ""
    try:
        port = parts.port or DEFAULT_OLLAMA_PORT
    except ValueError:
        port = -1
    if host in ("0.0.0.0", ""):
        host = "127.0.0.1"
    elif host == "::":
        host = "::1"
    if parts.scheme != "http" or port < 0 or not _is_loopback(host):
        raise BackendUnavailableError(
            f"OLLAMA_HOST must point to this machine (loopback address), got {raw!r}",
            hint=f"unset OLLAMA_HOST or set it to {DEFAULT_OLLAMA_HOST}",
        )
    netloc = f"[{host}]" if ":" in host else host
    return f"http://{netloc}:{port}"


def _is_loopback(host: str) -> bool:
    # Only literal addresses and "localhost" are accepted, so no DNS lookup ever happens.
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def clean_title(raw: str) -> str:
    title = re.sub(r"\s+", " ", raw).strip().strip("\"'«»“”").strip()
    title = title.rstrip(".").strip()
    if len(title) > MAX_TITLE_LENGTH:
        cut = title[:MAX_TITLE_LENGTH]
        if " " in cut and title[MAX_TITLE_LENGTH] != " ":
            cut = cut[: cut.rfind(" ")]
        title = cut.rstrip(" ,;:-—").strip()
    return title


def _sample_text(text: str, limit: int = TITLE_INPUT_LIMIT) -> str:
    """The beginning of `text` plus evenly spaced excerpts, at most `limit` characters."""
    if len(text) <= limit:
        return text
    head = limit // 2
    pieces, piece_len = 6, (limit - head) // 6 - 5
    rest = text[head:]
    step = (len(rest) - piece_len) / (pieces - 1)
    excerpts = [rest[round(i * step) : round(i * step) + piece_len] for i in range(pieces)]
    return " … ".join([text[:head], *excerpts])


class OllamaChapterModel:
    def __init__(self, model_name: str, base_url: str, timeout: float = REQUEST_TIMEOUT) -> None:
        self.model_name = model_name
        self._base_url = base_url
        self._timeout = timeout
        self._can_think = False

    # --- HTTP ------------------------------------------------------------------------

    def _open(self, path: str, payload: dict[str, Any]) -> Any:
        req = urllib.request.Request(
            self._base_url + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            return urllib.request.urlopen(req, timeout=self._timeout)
        except urllib.error.HTTPError:
            raise
        except TimeoutError as exc:
            raise self._timeout_error() from exc
        except (urllib.error.URLError, OSError) as exc:
            if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, TimeoutError):
                raise self._timeout_error() from exc
            raise BackendUnavailableError(
                f"cannot reach Ollama at {self._base_url}",
                hint="start Ollama ('ollama serve') or check OLLAMA_HOST",
            ) from exc

    def _timeout_error(self) -> ProcessingError:
        return ProcessingError(
            f"Ollama did not answer within {self._timeout:g} s (model {self.model_name})"
        )

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        with self._open(path, payload) as response:
            return json.loads(response.read())

    def _stream(self, path: str, payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
        with self._open(path, payload) as response:
            for line in response:
                if line.strip():
                    yield json.loads(line)

    def _chat(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0, "seed": SEED},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self._can_think:
            # Reasoning makes every call tens of times slower and adds nothing to a title.
            payload["think"] = False
        for _attempt in range(2):
            try:
                reply = self._post("/api/chat", payload)
            except urllib.error.HTTPError as exc:
                raise ProcessingError(f"Ollama request failed: HTTP {exc.code}") from exc
            try:
                data = json.loads(reply["message"]["content"])
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and all(k in data for k in schema["required"]):
                return data
        raise ProcessingError(f"model {self.model_name} returned an invalid answer twice")

    # --- ChapterModel ----------------------------------------------------------------

    def is_available(self) -> None:
        try:
            info = self._post("/api/show", {"model": self.model_name})
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise BackendUnavailableError(
                    f"LLM model {self.model_name} is not installed",
                    hint="timekotiki models pull",
                ) from exc
            raise BackendUnavailableError(f"Ollama error: HTTP {exc.code}") from exc
        self._can_think = "thinking" in (info.get("capabilities") or [])

    def is_installed(self) -> bool:
        try:
            self.is_available()
        except BackendUnavailableError:
            return False
        return True

    def pull(self, on_progress: ProgressCallback) -> None:
        try:
            for event in self._stream("/api/pull", {"model": self.model_name, "stream": True}):
                if "error" in event:
                    raise BackendUnavailableError(f"cannot download model: {event['error']}")
                if event.get("total") and "completed" in event:
                    on_progress(event["completed"] / event["total"])
                if event.get("status") == "success":
                    on_progress(1.0)
        except urllib.error.HTTPError as exc:
            raise BackendUnavailableError(f"cannot download model: HTTP {exc.code}") from exc

    def find_boundaries(self, window_lines: list[str], language: str) -> list[Boundary]:
        data = self._chat(
            BOUNDARIES_PROMPT.format(language=LANGUAGE_NAMES.get(language, language)),
            "\n".join(window_lines),
            BOUNDARIES_SCHEMA,
        )
        found = []
        for item in data["boundaries"]:
            if isinstance(item, dict) and isinstance(item.get("segment"), int):
                found.append(Boundary(item["segment"], str(item.get("topic", "")).strip()))
        return found

    def make_title(self, text: str, language: str, topic_hint: str | None) -> str:
        user = _sample_text(text)
        if topic_hint:
            user = f"Draft topic: {topic_hint}\n\nTranscript:\n{user}"
        data = self._chat(
            TITLE_PROMPT.format(
                language=LANGUAGE_NAMES.get(language, language), limit=MAX_TITLE_LENGTH
            ),
            user,
            TITLE_SCHEMA,
        )
        return clean_title(str(data["title"]))
