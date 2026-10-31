import io

from timekotiki.progress import Progress


def test_tty_mode_updates_line_with_percent() -> None:
    stream = io.StringIO()
    p = Progress(stream, is_tty=True, quiet=False)
    p.stage("transcribe")
    p.update(0.37)
    p.done()
    out = stream.getvalue()
    assert "\r" in out
    assert "37%" in out
    assert out.endswith("\n")


def test_non_tty_mode_one_line_per_stage() -> None:
    stream = io.StringIO()
    p = Progress(stream, is_tty=False, quiet=False)
    p.stage("probe")
    p.stage("transcribe")
    p.update(0.5)
    p.skip("segment")
    p.done()
    out = stream.getvalue()
    assert "\r" not in out
    assert "%" not in out
    assert len(out.strip().splitlines()) == 3


def test_quiet_mode_is_silent() -> None:
    stream = io.StringIO()
    p = Progress(stream, is_tty=True, quiet=True)
    p.stage("probe")
    p.update(0.5)
    p.done()
    assert stream.getvalue() == ""


def test_no_ansi_escapes() -> None:
    stream = io.StringIO()
    p = Progress(stream, is_tty=True, quiet=False)
    for name in ("probe", "transcribe", "segment", "title"):
        p.stage(name)
        p.update(1.0)
    p.done()
    assert "\x1b" not in stream.getvalue()
