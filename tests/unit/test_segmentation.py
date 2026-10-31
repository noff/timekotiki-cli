from tests.conftest import make_transcript
from timekotiki.models import Boundary
from timekotiki.segmentation import build_windows, merge_boundaries


def long_transcript(minutes: int):  # type: ignore[no-untyped-def]
    return make_transcript([(15, f"фраза {i}") for i in range(minutes * 4)])


def test_windows_cover_all_segments_with_overlap() -> None:
    t = long_transcript(25)
    windows = build_windows(t, size=600, overlap=60)
    covered = {i for w in windows for i in w.indices}
    assert covered == set(range(len(t.segments)))
    for prev, nxt in zip(windows, windows[1:], strict=False):
        overlap = t.segments[prev.indices[-1]].end - t.segments[nxt.indices[0]].start
        assert overlap >= 60


def test_window_line_format() -> None:
    t = make_transcript([(65, "привет"), (10, "мир")])
    (window,) = build_windows(t)
    assert window.lines == ["[0] 00:00 привет", "[1] 01:05 мир"]


def test_short_transcript_is_one_window() -> None:
    assert len(build_windows(long_transcript(5))) == 1


def test_merge_drops_foreign_indices_and_adds_zero() -> None:
    t = long_transcript(25)
    w1, w2, w3 = build_windows(t)
    merged = merge_boundaries(
        t,
        [
            (w1, [Boundary(w1.indices[10], "a"), Boundary(w3.indices[-1], "foreign")]),
            (w2, [Boundary(w2.indices[20], "b")]),
            (w3, []),
        ],
    )
    assert [b.segment_index for b in merged] == [0, w1.indices[10], w2.indices[20]]
    assert merged[1].topic_hint == "a"


def test_merge_collapses_close_boundaries_keeping_earlier() -> None:
    t = long_transcript(25)
    w1, w2, _ = build_windows(t)
    shared = sorted(set(w1.indices) & set(w2.indices))
    merged = merge_boundaries(
        t, [(w1, [Boundary(shared[0], "first")]), (w2, [Boundary(shared[1], "second")])]
    )
    assert [b.segment_index for b in merged] == [0, shared[0]]
    assert merged[1].topic_hint == "first"


def test_merge_near_zero_adopts_hint() -> None:
    t = long_transcript(5)
    (w,) = build_windows(t)
    merged = merge_boundaries(t, [(w, [Boundary(1, "Вступление")])])
    assert merged == [Boundary(0, "Вступление")]
