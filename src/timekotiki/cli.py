"""Command-line interface. See contracts/cli.md for the public contract."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, TextIO

from timekotiki import __version__
from timekotiki.asr import Transcriber
from timekotiki.cache import TranscriptCache, cache_dir
from timekotiki.errors import (
    EXIT_INTERRUPTED,
    EXIT_OK,
    BackendUnavailableError,
    TimekotikiError,
    UsageError,
    exit_code_for,
    format_error,
)
from timekotiki.formats import RENDERERS
from timekotiki.fsutil import atomic_write_text, check_output_target
from timekotiki.llm import ChapterModel, ollama_base_url
from timekotiki.models import MIN_CHAPTER_FLOOR, MediaSource, Options
from timekotiki.pipeline import run_pipeline
from timekotiki.progress import Progress

DEFAULTS = Options()

WARNINGS = {
    "fewer_than_3_chapters": "fewer than 3 chapters; video platforms usually require at least 3",
    "chapter_shorter_than_10s": "a chapter is shorter than 10 seconds; platforms may reject it",
    "single_topic": "the whole video was recognised as a single topic",
}


@dataclass
class Deps:
    """Everything `main` touches outside its own arguments, so tests can swap it."""

    transcriber_factory: Callable[[str], Transcriber]
    chapter_model_factory: Callable[[str, str], ChapterModel]
    stdout: TextIO
    stderr: TextIO
    is_tty: bool
    env: Mapping[str, str]
    probe: Callable[[str], MediaSource]


_DURATION = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")
_LANGUAGE = re.compile(r"^[a-z]{2,3}$")


def parse_duration(raw: str) -> float:
    """Seconds from `90`, `12.5`, `5m`, `1m30s` or `1h`; at least MIN_CHAPTER_FLOOR."""
    try:
        seconds = float(raw)
    except ValueError:
        match = _DURATION.match(raw)
        if not raw or match is None:
            raise argparse.ArgumentTypeError(
                f"invalid duration {raw!r}; use seconds or forms like 5m, 1m30s, 1h"
            ) from None
        hours, minutes, secs = (int(g) if g else 0 for g in match.groups())
        seconds = float(hours * 3600 + minutes * 60 + secs)
    if seconds < MIN_CHAPTER_FLOOR:
        raise argparse.ArgumentTypeError(
            f"duration must be at least {MIN_CHAPTER_FLOOR:g} seconds, got {raw!r}"
        )
    return seconds


def parse_language(raw: str) -> str:
    if not _LANGUAGE.match(raw):
        raise argparse.ArgumentTypeError(
            f"invalid language {raw!r}; use an ISO 639-1 code such as ru or en"
        )
    return raw


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {raw!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise UsageError(message, hint=f"see '{self.prog} --help'")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="timekotiki",
        description="Generate video chapter timecodes from a local video or audio file.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    generate = commands.add_parser("generate", help="generate chapters for a local media file")
    generate.add_argument("file", metavar="FILE", help="path to a local video or audio file")
    generate.add_argument(
        "--format", choices=sorted(RENDERERS), help="output format (default: text)"
    )
    generate.add_argument("--json", action="store_true", help="same as --format json")
    generate.add_argument(
        "-o", "--output", type=Path, metavar="PATH", help="write the result to PATH, not stdout"
    )
    generate.add_argument(
        "--force", action="store_true", help="allow --output to overwrite an existing file"
    )
    generate.add_argument(
        "--min-chapter",
        type=parse_duration,
        default=DEFAULTS.min_chapter,
        metavar="DURATION",
        help="minimum chapter length: 90, 1m30s, 5m (default: 1m)",
    )
    generate.add_argument(
        "--max-chapters",
        type=_positive_int,
        metavar="N",
        help="maximum number of chapters (default: no limit)",
    )
    generate.add_argument(
        "--title-language",
        type=parse_language,
        metavar="LANG",
        help="language of chapter titles, ISO 639-1 (default: language of the speech)",
    )
    generate.add_argument(
        "--speech-language",
        type=parse_language,
        metavar="LANG",
        help="language of the speech, skips auto-detection (default: auto)",
    )
    generate.add_argument(
        "--no-cache",
        action="store_true",
        help="transcribe again even if a cached transcript exists",
    )
    _add_model_flags(generate)
    generate.add_argument(
        "-q", "--quiet", action="store_true", help="do not show progress on stderr"
    )
    generate.set_defaults(handler=_cmd_generate)

    models = commands.add_parser("models", help="check or download the local models")
    models_commands = models.add_subparsers(dest="models_command", metavar="ACTION", required=True)
    status = models_commands.add_parser("status", help="show whether the models are installed")
    _add_model_flags(status)
    status.add_argument("--json", action="store_true", help="print the status as JSON")
    status.set_defaults(handler=_cmd_models_status)
    pull = models_commands.add_parser(
        "pull",
        help="download the models (uses the network)",
        description="Download the ASR and LLM models. This is the only command that uses the "
        "network; generation works offline afterwards.",
    )
    _add_model_flags(pull)
    pull.set_defaults(handler=_cmd_models_pull)

    cache = commands.add_parser("cache", help="manage the transcript cache")
    cache_commands = cache.add_subparsers(dest="cache_command", metavar="ACTION", required=True)
    clear = cache_commands.add_parser("clear", help="delete all cached transcripts")
    clear.set_defaults(handler=_cmd_cache_clear)
    return parser


def _add_model_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--asr-model",
        default=DEFAULTS.asr_model,
        metavar="NAME",
        help=f"faster-whisper model (default: {DEFAULTS.asr_model})",
    )
    parser.add_argument(
        "--llm-model",
        default=DEFAULTS.llm_model,
        metavar="NAME",
        help=f"Ollama model (default: {DEFAULTS.llm_model})",
    )


def _output_format(args: argparse.Namespace) -> str:
    if args.json and args.format not in (None, "json"):
        raise UsageError(f"--json conflicts with --format {args.format}")
    return "json" if args.json else args.format or "text"


def _cmd_generate(args: argparse.Namespace, deps: Deps) -> int:
    render = RENDERERS[_output_format(args)]
    if args.output is not None:
        check_output_target(args.output, force=args.force)
    options = Options(
        min_chapter=args.min_chapter,
        max_chapters=args.max_chapters,
        title_language=args.title_language,
        speech_language=args.speech_language,
        asr_model=args.asr_model,
        llm_model=args.llm_model,
        use_cache=not args.no_cache,
    )
    base_url = ollama_base_url(deps.env)
    result = run_pipeline(
        args.file,
        options,
        probe=deps.probe,
        transcriber=deps.transcriber_factory(options.asr_model),
        chapter_model=deps.chapter_model_factory(options.llm_model, base_url),
        progress=Progress(deps.stderr, is_tty=deps.is_tty, quiet=args.quiet),
        cache=_cache(deps),
    )
    for warning in result.warnings:
        print(f"timekotiki: warning: {WARNINGS[warning]}", file=deps.stderr)
    if args.output is not None:
        atomic_write_text(args.output, render(result))
    else:
        deps.stdout.write(render(result))
    return EXIT_OK


def _cmd_models_status(args: argparse.Namespace, deps: Deps) -> int:
    asr = deps.transcriber_factory(args.asr_model)
    llm = deps.chapter_model_factory(args.llm_model, ollama_base_url(deps.env))
    status = {
        "asr": {"model": args.asr_model, "installed": asr.is_installed()},
        "llm": {"model": args.llm_model, "installed": llm.is_installed()},
    }
    if args.json:
        print(json.dumps(status), file=deps.stdout)
    else:
        for kind, item in status.items():
            state = "installed" if item["installed"] else "missing"
            print(f"{kind:<4} {item['model']:<28} {state}", file=deps.stdout)
    if not all(item["installed"] for item in status.values()):
        raise BackendUnavailableError("some models are missing", hint="timekotiki models pull")
    return EXIT_OK


def _cmd_models_pull(args: argparse.Namespace, deps: Deps) -> int:
    asr = deps.transcriber_factory(args.asr_model)
    llm = deps.chapter_model_factory(args.llm_model, ollama_base_url(deps.env))
    backends: tuple[tuple[str, Transcriber | ChapterModel], ...] = (("ASR", asr), ("LLM", llm))
    for kind, backend in backends:
        print(f"Downloading {kind} model {backend.model_name}...", file=deps.stderr)
        backend.pull(_pull_reporter(deps))
        if deps.is_tty:
            print(file=deps.stderr)
    print("All models are installed.", file=deps.stderr)
    return EXIT_OK


def _pull_reporter(deps: Deps) -> Callable[[float], None]:
    def report(fraction: float) -> None:
        if deps.is_tty:
            deps.stderr.write(f"\r  {round(min(max(fraction, 0.0), 1.0) * 100):3d}%")
            deps.stderr.flush()

    return report


def _cache(deps: Deps) -> TranscriptCache:
    return TranscriptCache(cache_dir(deps.env, sys.platform, Path.home()))


def _cmd_cache_clear(args: argparse.Namespace, deps: Deps) -> int:
    _cache(deps).clear()
    print("Transcript cache cleared.", file=deps.stderr)
    return EXIT_OK


def main(argv: list[str], deps: Deps) -> int:
    try:
        with contextlib.redirect_stdout(deps.stdout), contextlib.redirect_stderr(deps.stderr):
            try:
                args = build_parser().parse_args(argv)
            except SystemExit as exit_:  # --help / --version
                return exit_.code if isinstance(exit_.code, int) else EXIT_OK
        handler: Callable[[argparse.Namespace, Deps], int] = args.handler
        return handler(args, deps)
    except TimekotikiError as exc:
        print(format_error(exc), file=deps.stderr)
        return exit_code_for(exc)
    except KeyboardInterrupt:
        print("\ntimekotiki: interrupted", file=deps.stderr)
        return EXIT_INTERRUPTED


def run() -> None:
    sys.exit(main(sys.argv[1:], _real_deps()))


def _real_deps() -> Deps:
    from timekotiki.asr import FasterWhisperTranscriber
    from timekotiki.llm import OllamaChapterModel
    from timekotiki.media import probe

    return Deps(
        transcriber_factory=FasterWhisperTranscriber,
        chapter_model_factory=OllamaChapterModel,
        stdout=sys.stdout,
        stderr=sys.stderr,
        is_tty=sys.stderr.isatty(),
        env=os.environ,
        probe=probe,
    )
