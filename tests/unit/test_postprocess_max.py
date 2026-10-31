from tests.conftest import make_transcript
from timekotiki.models import Boundary, Options
from timekotiki.postprocess import build_chapters


def transcript():  # type: ignore[no-untyped-def]
    return make_transcript([(60, f"фраза {i}") for i in range(20)])  # 20 min, segment per minute


def test_max_chapters_merges_smallest_adjacent_pair() -> None:
    # chapters (minutes): 0-2, 2-3, 3-10, 10-12, 12-20 → lengths 2, 1, 7, 2, 8
    boundaries = [Boundary(2), Boundary(3), Boundary(10), Boundary(12)]
    drafts, _ = build_chapters(transcript(), boundaries, Options(max_chapters=4))
    # smallest pair is 0-2 + 2-3 (3 min)
    assert [d.start / 60 for d in drafts] == [0, 3, 10, 12]
    drafts, _ = build_chapters(transcript(), boundaries, Options(max_chapters=3))
    # now 0-3, 3-10, 10-12, 12-20: pair sums 10, 9, 10, so 3-10 absorbs 10-12
    assert [d.start / 60 for d in drafts] == [0, 3, 12]


def test_ties_merge_earliest_pair() -> None:
    boundaries = [Boundary(5), Boundary(10), Boundary(15)]  # four 5-minute chapters
    drafts, _ = build_chapters(transcript(), boundaries, Options(max_chapters=3))
    assert [d.start / 60 for d in drafts] == [0, 10, 15]


def test_max_one_chapter_covers_whole_video() -> None:
    t = transcript()
    drafts, warnings = build_chapters(t, [Boundary(5), Boundary(10)], Options(max_chapters=1))
    assert len(drafts) == 1
    assert (drafts[0].start, drafts[0].end) == (0.0, t.duration)
    assert "single_topic" in warnings


def test_limit_not_reached_changes_nothing() -> None:
    boundaries = [Boundary(5), Boundary(10)]
    unlimited, _ = build_chapters(transcript(), boundaries, Options())
    limited, _ = build_chapters(transcript(), boundaries, Options(max_chapters=10))
    assert unlimited == limited
