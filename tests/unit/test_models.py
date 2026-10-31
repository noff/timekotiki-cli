import dataclasses

import pytest

from timekotiki.models import Chapter, Options, TranscriptSegment


def test_segment_rejects_start_after_end() -> None:
    with pytest.raises(ValueError):
        TranscriptSegment(index=0, start=5.0, end=4.0, text="hello")


def test_segment_rejects_blank_text() -> None:
    with pytest.raises(ValueError):
        TranscriptSegment(index=0, start=0.0, end=1.0, text="   ")


def test_segment_is_frozen() -> None:
    seg = TranscriptSegment(index=0, start=0.0, end=1.0, text="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        seg.text = "other"  # type: ignore[misc]


@pytest.mark.parametrize("title", ["", "a" * 61, "line\nbreak"])
def test_chapter_title_rules(title: str) -> None:
    with pytest.raises(ValueError):
        Chapter(start=0.0, end=10.0, title=title)


def test_chapter_timecode_is_computed() -> None:
    assert Chapter(start=3750.4, end=3800.0, title="Итоги").timecode == "1:02:30"


def test_options_defaults() -> None:
    opts = Options()
    assert opts.min_chapter == 60.0
    assert opts.max_chapters is None
    assert opts.asr_model == "large-v3-turbo"
    assert opts.llm_model == "qwen2.5:7b-instruct"
    assert opts.use_cache is True


@pytest.mark.parametrize("kwargs", [{"min_chapter": 9.0}, {"max_chapters": 0}])
def test_options_validation(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        Options(**kwargs)  # type: ignore[arg-type]
