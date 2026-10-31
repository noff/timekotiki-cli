import json
from pathlib import Path

import jsonschema

from tests.contract.test_text_format import sample_result
from timekotiki.formats import render_json, render_text

SCHEMA = json.loads(
    (
        Path(__file__).parents[2] / "specs/001-video-timecodes/contracts/result.schema.json"
    ).read_text()
)


def test_json_validates_against_contract_schema() -> None:
    document = json.loads(render_json(sample_result()))
    jsonschema.validate(document, SCHEMA)
    assert document["schema_version"] == 1
    assert document["source"] == "talk.mp4"


def test_json_matches_text_output() -> None:
    result = sample_result()
    document = json.loads(render_json(result))
    from_json = [f"{c['timecode']} {c['title']}" for c in document["chapters"]]
    assert from_json == render_text(result).splitlines()


def test_json_is_utf8_and_newline_terminated() -> None:
    out = render_json(sample_result())
    assert "Вступление" in out
    assert out.endswith("\n")


def test_json_contains_options_and_warnings() -> None:
    document = json.loads(render_json(sample_result()))
    assert document["options"] == {
        "min_chapter": 60.0,
        "max_chapters": None,
        "asr_model": "large-v3-turbo",
        "llm_model": "qwen2.5:7b-instruct",
    }
    assert document["warnings"] == []
    assert document["transcript_cached"] is False


def test_schema_rejects_unknown_fields() -> None:
    document = json.loads(render_json(sample_result()))
    document["extra"] = 1
    try:
        jsonschema.validate(document, SCHEMA)
    except jsonschema.ValidationError:
        return
    raise AssertionError("schema must reject unknown fields")
