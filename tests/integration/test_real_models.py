"""End-to-end runs with the real faster-whisper and Ollama backends.

Run with `uv run pytest -m models`. Override the models with TIMEKOTIKI_TEST_ASR_MODEL and
TIMEKOTIKI_TEST_LLM_MODEL to use ones that are already installed locally.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from tests.contract.test_json_schema import SCHEMA

pytestmark = pytest.mark.models

FIXTURE = Path(__file__).parents[1] / "fixtures" / "speech_ru.ogg"
ASR = os.environ.get("TIMEKOTIKI_TEST_ASR_MODEL", "large-v3-turbo")
LLM = os.environ.get("TIMEKOTIKI_TEST_LLM_MODEL", "qwen2.5:7b-instruct")


def run(cache: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "TIMEKOTIKI_CACHE_DIR": str(cache)}
    return subprocess.run(
        [sys.executable, "-m", "timekotiki", *args, "--asr-model", ASR, "--llm-model", LLM],
        capture_output=True,
        text=True,
        env=env,
        timeout=1800,
    )


@pytest.fixture(scope="module", autouse=True)
def models_installed(tmp_path_factory: pytest.TempPathFactory) -> None:
    proc = run(tmp_path_factory.mktemp("cache"), "models", "status")
    if proc.returncode != 0:
        pytest.skip(f"models are not installed ({ASR}, {LLM}): {proc.stdout.strip()}")


def generate(cache: Path, *args: str) -> dict[str, object]:
    proc = run(cache, "generate", "--json", "--min-chapter", "10", *args, str(FIXTURE))
    assert proc.returncode == 0, proc.stderr
    document: dict[str, object] = json.loads(proc.stdout)
    jsonschema.validate(document, SCHEMA)
    return document


def test_generate_and_cache(tmp_path: Path) -> None:
    first = generate(tmp_path)
    chapters = first["chapters"]
    assert isinstance(chapters, list) and chapters
    assert chapters[0]["timecode"] == "00:00"
    assert first["speech_language"] == "ru"
    assert first["transcript_cached"] is False

    second = generate(tmp_path, "--max-chapters", "2")
    assert second["transcript_cached"] is True
    assert isinstance(second["chapters"], list) and len(second["chapters"]) <= 2


def test_english_titles(tmp_path: Path) -> None:
    document = generate(tmp_path, "--title-language", "en")
    chapters = document["chapters"]
    assert isinstance(chapters, list)
    for chapter in chapters:
        title = chapter["title"]
        ascii_share = sum(c.isascii() for c in title) / len(title)
        assert ascii_share > 0.8, title
