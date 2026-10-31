import subprocess
import sys

from timekotiki import __version__


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "timekotiki", *args], capture_output=True, text=True, timeout=60
    )


def test_version() -> None:
    proc = run("--version")
    assert proc.returncode == 0
    assert proc.stdout.strip() == __version__


def test_missing_file() -> None:
    proc = run("generate", "/nonexistent/talk.mp4")
    assert proc.returncode == 3
    assert proc.stdout == ""
    assert proc.stderr.splitlines()[-1].startswith("timekotiki: error: file not found")
