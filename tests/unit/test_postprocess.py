import math

from tests.conftest import make_transcript
from timekotiki.models import Boundary, Options
from timekotiki.postprocess import build_chapters


def transcript_every(seconds: float, count: int):  # type: ignore[no-untyped-def]
    return make_transcript([(seconds, f"фраза {i}") for i in range(count)])


def starts(drafts) -> list[float]:  # type: ignore[no-untyped-def]
    return [d.start for d in drafts]


def test_no_boundaries_gives_single_chapter() -> None:
    t = transcript_every(30, 10)
    drafts, warnings = build_chapters(t, [], Options())
    assert starts(drafts) == [0.0]
    assert drafts[0].end == t.duration
    assert "single_topic" in warnings
    assert "fewer_than_3_chapters" in warnings


def test_first_chapter_is_always_zero_and_boundaries_snap() -> None:
    t = make_transcript([(5.5, "вступление")] + [(30, f"фраза {i}") for i in range(20)])
    drafts, _ = build_chapters(t, [Boundary(3, "a"), Boundary(10, "b")], Options())
    assert starts(drafts) == [0.0, t.segments[3].start, t.segments[10].start]
    assert drafts[1].topic_hint == "a"


def test_chapters_are_contiguous_and_end_at_duration() -> None:
    t = transcript_every(30, 20)
    drafts, _ = build_chapters(t, [Boundary(4), Boundary(8), Boundary(14)], Options())
    for prev, nxt in zip(drafts, drafts[1:], strict=False):
        assert prev.end == nxt.start
    assert drafts[-1].end == t.duration


def test_duplicates_and_same_second_are_merged() -> None:
    t = make_transcript([(100, "a"), (0.3, "b"), (100, "c"), (100, "d")])
    drafts, _ = build_chapters(
        t, [Boundary(1), Boundary(1), Boundary(2), Boundary(3)], Options(min_chapter=10)
    )
    floored = [math.floor(d.start) for d in drafts]
    assert floored == sorted(set(floored))
    assert len(drafts) == 3


def test_short_chapters_merge_into_previous() -> None:
    t = transcript_every(10, 30)  # 300 s
    # chapter 60..80 is only 20 s long, so it becomes the tail of 0..60
    drafts, _ = build_chapters(t, [Boundary(6), Boundary(8), Boundary(20)], Options())
    assert starts(drafts) == [0.0, 80.0, 200.0]
    assert all(d.end - d.start >= 60 for d in drafts)


def test_short_first_chapter_merges_into_next() -> None:
    t = transcript_every(10, 30)
    drafts, _ = build_chapters(t, [Boundary(2), Boundary(15)], Options())
    assert starts(drafts) == [0.0, 150.0]
    assert drafts[0].end == 150.0


def test_short_last_chapter_merges_into_previous() -> None:
    t = transcript_every(10, 30)
    drafts, _ = build_chapters(t, [Boundary(10), Boundary(27)], Options())
    assert starts(drafts) == [0.0, 100.0]
    assert drafts[-1].end == 300.0


def test_warnings_for_platform_rules() -> None:
    t = transcript_every(10, 30)
    _, warnings = build_chapters(t, [Boundary(10), Boundary(20)], Options())
    assert warnings == []
    _, warnings = build_chapters(t, [Boundary(15)], Options())
    assert warnings == ["fewer_than_3_chapters"]


def test_chapters_shorter_than_floor_never_survive() -> None:
    t = make_transcript([(5, "a"), (20, "b"), (20, "c"), (20, "d")])
    drafts, warnings = build_chapters(t, [Boundary(1), Boundary(2), Boundary(3)], Options(10))
    assert all(d.end - d.start >= 10 for d in drafts)
    assert "chapter_shorter_than_10s" not in warnings


def test_very_short_media_warns_about_10s_rule() -> None:
    t = make_transcript([(4, "коротко")])
    _, warnings = build_chapters(t, [], Options())
    assert "chapter_shorter_than_10s" in warnings
