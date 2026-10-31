"""Benchmark timekotiki against hand-made chapters (SC-001, SC-003, SC-004, SC-006).

For every media file in $TIMEKOTIKI_BENCH_DIR that has a sibling `<name>.chapters.txt`
(lines like `04:12 Title`), run `timekotiki generate` twice — cold (`--no-cache`) and warm
(cached transcript) — and print a Markdown table.

    TIMEKOTIKI_BENCH_DIR=~/bench uv run python scripts/bench.py [--asr-model M] [--llm-model M]

Peak memory is that of the timekotiki process only; Ollama runs in its own process.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MEDIA_SUFFIXES = {".mp4", ".mkv", ".mov", ".webm", ".mp3", ".wav", ".m4a", ".ogg"}
TOLERANCE_SECONDS = 30.0


def parse_timecode(timecode: str) -> int:
    parts = [int(p) for p in timecode.split(":")]
    return sum(value * 60**i for i, value in enumerate(reversed(parts)))


def reference_starts(path: Path) -> list[int]:
    starts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            starts.append(parse_timecode(line.split(maxsplit=1)[0]))
    return starts


def run_generate(
    media: Path, cache: Path, extra: list[str]
) -> tuple[dict[str, object], float, int]:
    """Return (json result, wall seconds, peak RSS in bytes) of one generate run."""
    env = {**os.environ, "TIMEKOTIKI_CACHE_DIR": str(cache)}
    argv = [sys.executable, "-m", "timekotiki", "generate", "--json", "-q", *extra, str(media)]
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        started = time.monotonic()
        proc = subprocess.Popen(argv, stdout=out, stderr=err, env=env)
        # wait4 reports the resource usage of this one child, unlike RUSAGE_CHILDREN.
        _, status, usage = os.wait4(proc.pid, 0)
        elapsed = time.monotonic() - started
        out.seek(0)
        err.seek(0)
        code = os.waitstatus_to_exitcode(status)
        if code != 0:
            raise RuntimeError(f"{media.name}: exit {code}: {err.read().decode().strip()}")
        result: dict[str, object] = json.loads(out.read())
    peak = usage.ru_maxrss if sys.platform == "darwin" else usage.ru_maxrss * 1024
    return result, elapsed, peak


def hit_rate(reference: list[int], generated: list[float]) -> tuple[int, int]:
    targets = [r for r in reference if r > 0]  # 00:00 is always present
    hits = sum(any(abs(r - g) <= TOLERANCE_SECONDS for g in generated) for r in targets)
    return hits, len(targets)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--asr-model")
    parser.add_argument("--llm-model")
    args = parser.parse_args()
    bench_dir = Path(os.environ.get("TIMEKOTIKI_BENCH_DIR", "")).expanduser()
    if not bench_dir.is_dir():
        print("set TIMEKOTIKI_BENCH_DIR to a directory with media + .chapters.txt", file=sys.stderr)
        return 2
    extra = []
    if args.asr_model:
        extra += ["--asr-model", args.asr_model]
    if args.llm_model:
        extra += ["--llm-model", args.llm_model]

    rows = []
    total_hits = total_targets = 0
    with tempfile.TemporaryDirectory() as cache_root:
        for media in sorted(p for p in bench_dir.iterdir() if p.suffix.lower() in MEDIA_SUFFIXES):
            reference_file = media.with_suffix(".chapters.txt")
            if not reference_file.is_file():
                continue
            cache = Path(cache_root) / media.stem
            cold, cold_s, cold_rss = run_generate(media, cache, ["--no-cache", *extra])
            warm, warm_s, warm_rss = run_generate(media, cache, extra)
            starts = [c["start"] for c in cold["chapters"]]  # type: ignore[union-attr,index]
            hits, targets = hit_rate(reference_starts(reference_file), starts)
            total_hits += hits
            total_targets += targets
            rows.append(
                f"| {media.name} | {float(cold['duration']) / 60:.1f} | "  # type: ignore[arg-type]
                f"{hits}/{targets} | {cold_s / 60:.1f} | {warm_s:.0f} | "
                f"{max(cold_rss, warm_rss) / 2**30:.2f} | {warm['transcript_cached']} |"
            )

    print(
        "| File | Length, min | Boundaries ±30 s | Cold, min | Warm, s | Peak RSS, GiB | Cached |"
    )
    print(
        "|------|-------------|------------------|-----------|---------|---------------|--------|"
    )
    print("\n".join(rows))
    if total_targets:
        print(f"\nSC-001 boundary hit rate: {total_hits / total_targets:.0%} (target ≥ 80%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
