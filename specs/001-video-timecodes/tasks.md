---

description: "Task list for 001-video-timecodes"
---

# Tasks: Генерация тайм-кодов из видеоролика

**Input**: Design documents from `/specs/001-video-timecodes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, contracts/result.schema.json, quickstart.md

**Tests**: ВКЛЮЧЕНЫ. Конституция, принцип I (Test-First, NON-NEGOTIABLE): каждая тестовая
задача выполняется ДО соответствующей задачи реализации, и тест должен упасть по правильной
причине.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project, src-layout: `src/timekotiki/`, `tests/` в корне репозитория (см. plan.md → Project Structure).
- Тесты без моделей используют фейки из `tests/conftest.py`; тесты с реальными моделями помечены `@pytest.mark.models` и по умолчанию пропускаются.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create `pyproject.toml`: project `timekotiki` version `0.1.0`, `requires-python = ">=3.11"`, build backend `hatchling`, src-layout package `src/timekotiki`, console script `timekotiki = "timekotiki.cli:run"`, runtime deps `faster-whisper>=1.1` and `av>=12` (declared explicitly, research R2), dev dependency group `pytest`, `jsonschema`, `ruff`, `mypy`; `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, marker `models: requires real ASR/LLM models`, `addopts = "-m 'not models'"`; `[tool.ruff]` line-length 100, `select = ["E","F","I","UP","B","SIM"]`; `[tool.mypy]` `strict = true`, `files = ["src"]`
- [X] T002 Create package skeleton: `src/timekotiki/__init__.py` (`__version__ = "0.1.0"`), `src/timekotiki/__main__.py` (calls `timekotiki.cli.run()`), and empty `tests/__init__.py`, `tests/unit/`, `tests/contract/`, `tests/e2e/`, `tests/integration/`, `tests/fixtures/` directories (with `__init__.py` where needed)
- [X] T003 [P] Create `.gitignore` (`.venv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `dist/`) and `CHANGELOG.md` with an `## [Unreleased]` section (Constitution IV)
- [X] T004 Run `uv sync` and verify `uv run pytest` (0 tests collected, exit 5 is acceptable at this point), `uv run ruff check .`, `uv run mypy` all execute

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational (write FIRST, must FAIL)

- [X] T005 [P] Unit tests for error → exit-code mapping in `tests/unit/test_errors.py`: each exception class maps to the code in contracts/cli.md (UsageError 2, InputUnavailableError 3, UnsupportedFormatError 4, NoAudioError 5, NoSpeechError 5, BackendUnavailableError 6, ProcessingError 7, OutputConflictError 8); `format_error(exc)` returns `"timekotiki: error: <message>"` plus optional second line `"hint: <hint>"`
- [X] T006 [P] Unit tests for models invariants in `tests/unit/test_models.py`: `TranscriptSegment` rejects `start > end` and empty-after-strip `text`; `Chapter.title` must be "1..60 символов, без переводов строк"; dataclasses are frozen
- [X] T007 [P] Unit tests for atomic write in `tests/unit/test_fsutil.py`: `atomic_write_text(path, text)` writes via temp file in same directory + `os.replace`; on exception mid-write the target keeps its previous content and no temp file remains; `check_output_target(path, force)` raises `OutputConflictError` when file exists and `force=False`, and when parent directory is not writable
- [X] T008 [P] Unit tests for progress reporter in `tests/unit/test_progress.py`: writes only to the given stderr stream; TTY mode emits `\r`-updated line with percent; non-TTY mode emits one line per stage and no `\r`; `quiet=True` emits nothing; never writes ANSI escape codes

### Implementation for Foundational

- [X] T009 [P] Implement exception hierarchy and `EXIT_CODES`, `exit_code_for(exc)`, `format_error(exc)` in `src/timekotiki/errors.py` (base `TimekotikiError(message, hint=None)`; `EXIT_INTERRUPTED = 130`) — makes T005 pass
- [X] T010 [P] Implement frozen dataclasses `MediaSource`, `TranscriptSegment`, `Transcript`, `Boundary`, `Chapter`, `Options`, `ChapterResult` in `src/timekotiki/models.py` exactly per data-model.md (fields, types, defaults: `min_chapter=60.0`, `max_chapters=None`, `asr_model="large-v3-turbo"`, `llm_model="qwen2.5:7b-instruct"`, `use_cache=True`; validation in `__post_init__`) — makes T006 pass
- [X] T011 [P] Implement `atomic_write_text` and `check_output_target` in `src/timekotiki/fsutil.py` (temp file via `tempfile.NamedTemporaryFile(dir=path.parent, delete=False)`, `flush` + `os.fsync`, `os.replace`, cleanup in `finally`) — makes T007 pass
- [X] T012 [P] Implement `Progress` (stages `probe`, `transcribe`, `segment`, `title`; methods `stage(name)`, `update(fraction)`, `done()`) in `src/timekotiki/progress.py`, constructed with `stream`, `is_tty`, `quiet` — makes T008 pass
- [X] T013 Define backend protocols in `src/timekotiki/asr.py` (`class Transcriber(Protocol): def transcribe(self, path: Path, *, language: str | None, on_progress: Callable[[float], None]) -> Transcript` and `def is_installed(self) -> bool`) and `src/timekotiki/llm.py` (`class ChapterModel(Protocol)` with `find_boundaries(window_lines: list[str], language: str) -> list[Boundary]`, `make_title(text: str, language: str, topic_hint: str | None) -> str`, `is_available() -> None` raising `BackendUnavailableError`) — protocols only, no real backends yet
- [X] T014 Create test fakes and factories in `tests/conftest.py`: `FakeTranscriber(transcript | exception)` counting calls, `FakeChapterModel(boundaries_by_window, titles)` deterministic, `make_transcript(durations_and_texts, language="ru")`, `make_wav(tmp_path, seconds, silent=True)` using stdlib `wave` (16 kHz mono), and a `Deps` fixture wiring fakes + `io.StringIO` stdout/stderr
- [X] T015 Implement CLI skeleton in `src/timekotiki/cli.py`: `build_parser()` with subcommands `generate`, `models {status,pull}`, `cache clear` and `--version`; `@dataclass Deps(transcriber_factory, chapter_model_factory, stdout, stderr, is_tty, env)`; `main(argv: list[str], deps: Deps) -> int` catching `TimekotikiError` → `format_error` to stderr + `exit_code_for`, `KeyboardInterrupt` → 130; argparse usage errors → exit 2; `run()` builds real `Deps` and calls `sys.exit(main(sys.argv[1:], deps))`. Subcommand handlers are stubs raising `NotImplementedError` until their story phase
- [X] T016 Contract test for `--help`/`--version` in `tests/contract/test_cli_help.py`: `main(["--version"])` prints `0.1.0` to stdout, exit 0; `main(["--help"])` lists `generate`, `models`, `cache`; unknown flag → exit 2 with message on stderr only

**Checkpoint**: Foundation ready — `uv run pytest` green, `ruff` and `mypy --strict` clean

---

## Phase 3: User Story 1 - Получить список тайм-кодов для видео (Priority: P1) 🎯 MVP

**Goal**: `timekotiki generate FILE` выводит в stdout строки `ТАЙМКОД Заголовок`, первая `00:00`, по возрастанию; прогресс — в stderr; ошибки — с документированными кодами выхода. Включает `models status`/`models pull`, без которых генерация невозможна (FR-015).

**Independent Test**: `main(["generate", "talk.wav"], deps=FakeDeps)` с фейковой расшифровкой даёт ожидаемый текст в stdout и код 0; на реальных моделях — сценарии 1–5, 14, 15 из quickstart.md.

### Tests for User Story 1 (write FIRST, must FAIL) ⚠️

- [X] T017 [P] [US1] Unit tests for timecode formatting in `tests/unit/test_formats_timecode.py`: floor to whole seconds; `0.0 → "00:00"`, `252.9 → "04:12"`, `3599.99 → "59:59"`, `3600 → "1:00:00"`, `3750 → "1:02:30"`, `36000 → "10:00:00"` ("`MM:SS` при `start` < 3600, иначе `H:MM:SS`; floor до секунд")
- [X] T018 [P] [US1] Snapshot test for text renderer in `tests/contract/test_text_format.py`: `render_text(result)` produces exactly `"00:00 Вступление\n04:12 Настройка проекта\n1:02:30 Итоги и вопросы\n"` for the corresponding `ChapterResult`
- [X] T019 [P] [US1] Unit tests for media probe in `tests/unit/test_media.py`: missing path → `InputUnavailableError`; unreadable (chmod 000) → `InputUnavailableError`; argument matching `^[a-zA-Z][a-zA-Z0-9+.-]*://` → `InputUnavailableError` with message "only local files are supported"; text file renamed to `.mp4` → `UnsupportedFormatError`; WAV from `make_wav` → `MediaSource(has_audio=True, duration≈seconds)`; container without audio stream → `NoAudioError`
- [X] T020 [P] [US1] Unit tests for postprocess invariants in `tests/unit/test_postprocess.py` (data-model.md "Инварианты списка глав" 1, 2, 3, 5): boundaries snap to segment `start`; boundary at segment 0 always present so `chapters[0].start == 0.0`; duplicates and boundaries whose floored timecodes coincide are merged; chapters shorter than `min_chapter` merge into previous (first merges into next); last chapter `end == duration`; warnings `fewer_than_3_chapters` when < 3 chapters, `chapter_shorter_than_10s` when any chapter < 10 s, `single_topic` when exactly 1 chapter
- [X] T021 [P] [US1] Unit tests for segmentation windows in `tests/unit/test_segmentation.py`: `build_windows(transcript, size=600, overlap=60)` covers all segments, consecutive windows overlap by ≥ 60 s, lines formatted `[i] mm:ss текст`; `merge_boundaries` drops indices outside the window, collapses boundaries < 30 s apart keeping the earlier, sorts, adds index 0; a window where the model returns `[]` contributes no boundaries
- [X] T022 [P] [US1] Unit tests for Ollama client in `tests/unit/test_llm_ollama.py` (HTTP mocked by patching `urllib.request.urlopen`): `OLLAMA_HOST` default `127.0.0.1:11434`; hosts `localhost`, `127.0.0.5`, `[::1]` accepted; `10.0.0.5:11434` and `example.com` rejected with `BackendUnavailableError` BEFORE any request is made; connection refused → `BackendUnavailableError` with hint `ollama serve`; `/api/show` 404 → `BackendUnavailableError` with hint `timekotiki models pull`; `/api/chat` request body contains `format` JSON schema, `options.temperature == 0`, fixed `options.seed`; invalid JSON reply retried once then `ProcessingError`; `make_title` result trimmed to ≤ 60 chars on a word boundary with newlines removed
- [X] T023 [P] [US1] Unit tests for faster-whisper adapter in `tests/unit/test_asr_whisper.py` (patch `faster_whisper.WhisperModel`): model constructed with `local_files_only=True`, `compute_type="int8"` on CPU; `transcribe` called with `vad_filter=True` and `language` passthrough; segments converted to `TranscriptSegment` with continuous `index`, empty-text segments dropped; progress callback receives `segment.end / duration`; zero segments → `NoSpeechError`; missing model (`huggingface_hub` LocalEntryNotFoundError / OSError) → `BackendUnavailableError` with hint `timekotiki models pull`
- [X] T024 [P] [US1] Unit tests for pipeline orchestration in `tests/unit/test_pipeline.py`: stages called in order `probe → transcribe → segment → title`; `ChapterModel.is_available()` checked before transcription starts (fail fast, code 6); title language defaults to `transcript.language`; result chapters satisfy invariants 1, 2, 5
- [X] T025 [P] [US1] E2E tests for `generate` (text) in `tests/e2e/test_generate_text.py` via `main(argv, deps)` with fakes: US1/AC1 (30-min transcript → lines in order, first `00:00`, non-empty titles, exit 0); US1/AC2 (> 1 h → `H:MM:SS` after the first hour); US1/AC3 (`is_tty=True` → progress only in stderr, stdout contains only result lines; `-q` → stderr empty); US1/AC4 (missing file → exit 3, stdout empty); silence WAV → exit 5 "no speech detected"; URL argument → exit 3; non-loopback `OLLAMA_HOST` in `deps.env` → exit 6; `KeyboardInterrupt` raised by fake transcriber → exit 130
- [X] T026 [P] [US1] E2E tests for `models status`/`models pull` in `tests/e2e/test_models_cmd.py` with fakes: status with both installed → exit 0 and a two-line table on stdout; either missing → exit 6 with hint; `--json` → `{"asr": {"model", "installed"}, "llm": {"model", "installed"}}`; `pull` invokes download on both backends and reports progress on stderr only

### Implementation for User Story 1

- [X] T027 [P] [US1] Implement `format_timecode(seconds: float) -> str` and `render_text(result: ChapterResult) -> str` in `src/timekotiki/formats.py` — makes T017, T018 pass
- [X] T028 [P] [US1] Implement `probe(arg: str) -> MediaSource` in `src/timekotiki/media.py` using `av.open` (URL check first; `FileNotFoundError`/`PermissionError` → `InputUnavailableError`; `av.error.InvalidDataError`/`av.FFmpegError` → `UnsupportedFormatError`; no `container.streams.audio` → `NoAudioError`; duration from `container.duration / av.time_base`, fallback to audio stream duration) — makes T019 pass
- [X] T029 [P] [US1] Implement `build_chapters(transcript, boundaries, options) -> tuple[list[ChapterDraft], list[str]]` in `src/timekotiki/postprocess.py` (snap, ensure 0, dedupe by floored timecode, `min_chapter` merge, compute `end`, warnings) — makes T020 pass; leave a clearly named `_enforce_max_chapters` hook that is a no-op when `max_chapters is None`
- [X] T030 [P] [US1] Implement `build_windows` and `merge_boundaries` in `src/timekotiki/segmentation.py` (window 600 s, overlap 60 s, merge distance 30 s — research R4) — makes T021 pass
- [X] T031 [P] [US1] Implement `OllamaChapterModel` in `src/timekotiki/llm.py`: loopback validation via `ipaddress` + `socket.getaddrinfo` (all resolved addresses must be loopback); `is_available()` via `GET /api/tags`/`POST /api/show`; `find_boundaries` via `POST /api/chat` with `format={"type":"object","properties":{"boundaries":{"type":"array","items":{"type":"object","properties":{"segment":{"type":"integer"},"topic":{"type":"string"}},"required":["segment","topic"]}}},"required":["boundaries"]}`, system prompt asking for indices where a new topic starts ("тема обычно длится 3–15 минут"); `make_title` with `{"title": string}` schema, input text ≤ 6000 chars (start + uniform sample), answer in the requested language; `pull(on_progress)` via streaming `POST /api/pull`; timeouts 120 s; stdlib `urllib` only — makes T022 pass
- [X] T032 [P] [US1] Implement `FasterWhisperTranscriber(model_name, device="auto")` in `src/timekotiki/asr.py`: lazy `WhisperModel(model_name, device=..., compute_type="int8" on CPU / "float16" on CUDA, local_files_only=True)`; `transcribe` with `vad_filter=True`, `language`, iterating the segment generator and reporting progress; `is_installed()`; `pull(on_progress)` via `faster_whisper.download_model(model_name)` — makes T023 pass
- [X] T033 [US1] Implement `run_pipeline(arg, options, transcriber, chapter_model, progress) -> ChapterResult` in `src/timekotiki/pipeline.py` (probe → `chapter_model.is_available()` → transcribe → `build_windows` → `find_boundaries` per window → `merge_boundaries` → `build_chapters` → `make_title` per chapter → `ChapterResult` with `transcript_cached=False`) — makes T024 pass (depends on T027–T032)
- [X] T034 [US1] Wire `generate FILE [-q] [--asr-model] [--llm-model]` handler in `src/timekotiki/cli.py`: build `Options`, `Progress(deps.stderr, deps.is_tty, quiet)`, call `run_pipeline`, write `render_text` to `deps.stdout`; print each warning as `timekotiki: warning: …` to stderr — makes T025 pass
- [X] T035 [US1] Wire `models status [--json]` and `models pull` handlers in `src/timekotiki/cli.py` using `Transcriber.is_installed()/pull` and `OllamaChapterModel.is_available()/pull` — makes T026 pass
- [X] T036 [US1] Implement real `Deps` construction in `run()` in `src/timekotiki/cli.py` (`FasterWhisperTranscriber`, `OllamaChapterModel`, `sys.stdout`, `sys.stderr`, `sys.stderr.isatty()`, `os.environ`) and a subprocess smoke test in `tests/e2e/test_subprocess_smoke.py`: `python -m timekotiki --version` exit 0; `python -m timekotiki generate /nonexistent.mp4` exit 3 with stderr message and empty stdout

**Checkpoint**: MVP — User Story 1 fully functional; `uv run pytest` green

---

## Phase 4: User Story 2 - Машиночитаемый вывод и сохранение в файл (Priority: P2)

**Goal**: `--json` / `--format {text,json,vtt}`, `-o/--output` с атомарной записью и `--force`.

**Independent Test**: `generate FILE --json` валиден по `contracts/result.schema.json` и содержит те же главы, что текстовый вывод; `-o` не перезаписывает файл без `--force` (код 8).

### Tests for User Story 2 (write FIRST, must FAIL) ⚠️

- [X] T037 [P] [US2] Contract test for JSON output in `tests/contract/test_json_schema.py`: `render_json(result)` validates against `specs/001-video-timecodes/contracts/result.schema.json` via `jsonschema` (`schema_version == 1`, `title` "minLength 1, maxLength 60", `timecode` pattern `^(\d{2}:\d{2}|\d+:\d{2}:\d{2})$`, `warnings` items in enum `fewer_than_3_chapters | chapter_shorter_than_10s | single_topic`, `additionalProperties: false`); chapters identical in order/timecode/title to `render_text`; output ends with newline and uses `ensure_ascii=False`
- [X] T038 [P] [US2] Snapshot test for WebVTT in `tests/contract/test_vtt_format.py`: output starts with `WEBVTT\n\n`; one numbered cue per chapter `HH:MM:SS.mmm --> HH:MM:SS.mmm` from chapter start to next start (last → duration); title on the following line; blank line between cues
- [X] T039 [P] [US2] E2E tests in `tests/e2e/test_generate_output.py`: US2/AC1 (`--json` stdout parses and validates); US2/AC2 (`-o out.txt` writes file, stdout empty; second run → exit 8 and file unchanged; `--force` → exit 0 and file replaced; `-o` into non-writable dir → exit 8); US2/AC3 (`--format vtt` → WebVTT); `--json` together with `--format text` → exit 2; interruption during `-o` run leaves no `out.txt` and no temp files

### Implementation for User Story 2

- [X] T040 [P] [US2] Implement `render_json(result) -> str` in `src/timekotiki/formats.py` (field names/order per schema; `source` = file name only; floats rounded to 3 decimals) — makes T037 pass
- [X] T041 [P] [US2] Implement `render_vtt(result) -> str` in `src/timekotiki/formats.py` — makes T038 pass
- [X] T042 [US2] Add `--format {text,json,vtt}`, `--json`, `-o/--output`, `--force` to `generate` in `src/timekotiki/cli.py`; call `check_output_target` BEFORE running the pipeline (fail fast), write with `atomic_write_text` — makes T039 pass

**Checkpoint**: User Stories 1 and 2 work independently

---

## Phase 5: User Story 3 - Настройка детализации и языка заголовков (Priority: P3)

**Goal**: `--min-chapter`, `--max-chapters`, `--title-language`, `--speech-language`.

**Independent Test**: один и тот же фейковый ролик с разными параметрами даёт результаты, соблюдающие ограничения (≤ N глав, каждая кроме последней ≥ min, заголовки на заданном языке).

### Tests for User Story 3 (write FIRST, must FAIL) ⚠️

- [X] T043 [P] [US3] Unit tests for duration parsing in `tests/unit/test_cli_duration.py`: `parse_duration("90") == 90`, `"1m30s" == 90`, `"5m" == 300`, `"1h" == 3600`; `"abc"`, `"0"`, `"5s"` (below "≥ 10") → `argparse.ArgumentTypeError` → exit 2; `--max-chapters 0` → exit 2 ("≥ 1"); `--title-language`/`--speech-language` must match `^[a-z]{2,3}$`
- [X] T044 [P] [US3] Unit tests for max-chapters enforcement in `tests/unit/test_postprocess_max.py` (invariant 4): while `len > max_chapters` merge the adjacent pair with the smallest combined duration; first chapter stays at 0.0; result deterministic for ties (earliest pair wins); `max_chapters=1` → single chapter covering whole video
- [X] T045 [P] [US3] E2E tests in `tests/e2e/test_generate_options.py`: US3/AC1 (2 h fake transcript, `--max-chapters 10` → ≤ 10 lines); US3/AC2 (`--min-chapter 5m` → every chapter except the last ≥ 300 s, checked via `--json`); US3/AC3 (`--title-language en` → `FakeChapterModel.make_title` received `language="en"` and JSON `title_language == "en"`); `--speech-language ru` passed to transcriber as `language="ru"`; `options` block in JSON reflects applied values

### Implementation for User Story 3

- [X] T046 [P] [US3] Implement `parse_duration` and language validator in `src/timekotiki/cli.py` and add `--min-chapter`, `--max-chapters`, `--title-language`, `--speech-language` to `generate` — makes T043 pass
- [X] T047 [P] [US3] Implement `_enforce_max_chapters` in `src/timekotiki/postprocess.py` — makes T044 pass
- [X] T048 [US3] Pass the new options through `run_pipeline` in `src/timekotiki/pipeline.py` (speech language → transcriber, title language → `make_title`, limits → `build_chapters`) — makes T045 pass

**Checkpoint**: User Stories 1–3 work independently

---

## Phase 6: User Story 4 - Повторная генерация без повторного распознавания (Priority: P4)

**Goal**: кэш расшифровки по SHA-256 содержимого; `--no-cache`; `cache clear`.

**Independent Test**: два запуска `generate` на одном файле с разными `--max-chapters` — `FakeTranscriber` вызван один раз, во втором JSON `transcript_cached: true`.

### Tests for User Story 4 (write FIRST, must FAIL) ⚠️

- [X] T049 [P] [US4] Unit tests for cache in `tests/unit/test_cache.py`: `cache_dir(env, platform)` → `$TIMEKOTIKI_CACHE_DIR` if set, else `$XDG_CACHE_HOME/timekotiki` / `~/.cache/timekotiki` on Linux, `~/Library/Caches/timekotiki` on macOS, `%LOCALAPPDATA%\timekotiki\Cache` on Windows; `file_sha256` streams in 1 MiB blocks; key path `<cache_dir>/transcripts/<sha256>.<asr_model>.<lang|auto>.json`; round-trip `save`/`load` preserves segments; `format_version != 1` or corrupt JSON → `load` returns `None`; save is atomic (uses `atomic_write_text`); `clear()` removes `transcripts/` and succeeds when absent
- [X] T050 [P] [US4] E2E tests in `tests/e2e/test_generate_cache.py` with `TIMEKOTIKI_CACHE_DIR=tmp_path` in `deps.env`: US4/AC1 (second run with different `--max-chapters` → transcriber not called, stderr shows `transcribe` skipped, JSON `transcript_cached: true`); US4/AC2 (file content changed → transcriber called again); US4/AC3 (`--no-cache` → transcriber called, cache entry rewritten); different `--asr-model` → cache miss; `cache clear` → exit 0, next run transcribes

### Implementation for User Story 4

- [X] T051 [P] [US4] Implement `cache_dir`, `file_sha256`, `TranscriptCache(load, save, clear)` in `src/timekotiki/cache.py` (JSON: `{"format_version": 1, "sha256", "asr_model", "language", "duration", "segments": [{"start","end","text"}]}`) — makes T049 pass
- [X] T052 [US4] Integrate cache into `run_pipeline` in `src/timekotiki/pipeline.py` (lookup before transcribe unless `options.use_cache is False`; always save after a fresh transcription; set `ChapterResult.transcript_cached`; progress marks `transcribe` as skipped on hit)
- [X] T053 [US4] Add `--no-cache` to `generate` and implement `cache clear` handler in `src/timekotiki/cli.py` — makes T050 pass

**Checkpoint**: All user stories independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T054 [P] Create real-speech fixture `tests/fixtures/speech_ru_30s.ogg` (~30 s Russian speech, 2+ topics, recorded by the author, OGG Opus ≤ 150 KB) and its expected-topics notes in `tests/fixtures/README.md`
- [X] T055 Integration tests with real models in `tests/integration/test_real_models.py` (`@pytest.mark.models`; skip with reason when `models status` ≠ 0): full `generate` on `speech_ru_30s.ogg` → exit 0, ≥ 1 chapter, first `00:00`, JSON valid; `--title-language en` yields ASCII-dominant titles; second run reports `transcript_cached: true`
- [X] T056 [P] Implement benchmark script `scripts/bench.py`: for each `*.{mp4,mkv,mov,webm,mp3,wav,m4a}` with sibling `*.chapters.txt` in `$TIMEKOTIKI_BENCH_DIR`, run the pipeline, report boundary hit-rate within ±30 s (SC-001), wall time cold (SC-003) and warm-cache (SC-004), peak RSS via `resource.getrusage` (SC-006); output Markdown table to stdout
- [X] T057 [P] Write `README.md`: install (`pipx install` / `uv tool install`), Ollama prerequisite, `timekotiki models pull`, usage examples for all formats and options, exit-code table and env vars (copied from contracts/cli.md), privacy statement (no data leaves the machine; network only in `models pull`)
- [X] T058 [P] Update `CHANGELOG.md` `[Unreleased]` → `## [0.1.0] - <release date>` listing commands `generate`, `models status|pull`, `cache clear`, formats text/json/vtt
- [X] T059 Verify `--help` text of every subcommand in `src/timekotiki/cli.py` documents all flags from contracts/cli.md with defaults; extend `tests/contract/test_cli_help.py` to assert each flag name appears
- [X] T060 Run quality gates: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` — all clean
- [ ] T061 Run quickstart.md validation scenarios 1–15 manually with real models and network disabled for section 3; record results and any deviations in `specs/001-video-timecodes/quickstart.md` under a new "Validation log" section

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational
- **US2, US3, US4 (Phases 4–6)**: Depend on Foundational and on US1's `generate` handler (T034) and `run_pipeline` (T033), which they extend; independent of each other
- **Polish (Phase 7)**: Depends on all desired stories

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories
- **US2 (P2)**: Extends `formats.py` and `generate` from US1; independently testable via `--json`/`-o`
- **US3 (P3)**: Extends `postprocess.py`, `pipeline.py`, `generate` from US1; independent of US2 (E2E checks via `--json` assume T040 — if US2 not done, assert through `FakeChapterModel`/result object instead)
- **US4 (P4)**: Extends `pipeline.py` and `generate` from US1; independent of US2/US3 (the `transcript_cached` check uses `--json` if US2 is done, otherwise the `ChapterResult` returned by `run_pipeline`)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Constitution I)
- Pure modules (`formats`, `postprocess`, `segmentation`, `media`, `cache`) before `pipeline`
- `pipeline` before `cli` wiring
- Story complete (checkpoint green) before moving to the next priority

### Parallel Opportunities

- Phase 2: T005–T008 together; then T009–T012 together
- US1: T017–T026 (all tests, different files) together; then T027–T032 (different modules) together; T033 → T034 → T035 → T036 sequential (same files)
- US2: T037–T039 together; T040 and T041 touch the same file `formats.py` — run sequentially if one agent, or merge carefully
- US3: T043–T045 together; T046 and T047 together
- US4: T049, T050 together
- After US1, phases 4, 5 and 6 can be worked on in parallel by different people; they all edit `cli.py` and `pipeline.py`, so merge in priority order
- Polish: T054, T056, T057, T058 together

---

## Parallel Example: User Story 1

```bash
# Write all failing tests for User Story 1 together:
Task: "Unit tests for timecode formatting in tests/unit/test_formats_timecode.py"
Task: "Unit tests for media probe in tests/unit/test_media.py"
Task: "Unit tests for postprocess invariants in tests/unit/test_postprocess.py"
Task: "Unit tests for segmentation windows in tests/unit/test_segmentation.py"
Task: "Unit tests for Ollama client in tests/unit/test_llm_ollama.py"
Task: "Unit tests for faster-whisper adapter in tests/unit/test_asr_whisper.py"

# Then implement the independent modules together:
Task: "Implement format_timecode and render_text in src/timekotiki/formats.py"
Task: "Implement probe in src/timekotiki/media.py"
Task: "Implement build_chapters in src/timekotiki/postprocess.py"
Task: "Implement build_windows and merge_boundaries in src/timekotiki/segmentation.py"
Task: "Implement OllamaChapterModel in src/timekotiki/llm.py"
Task: "Implement FasterWhisperTranscriber in src/timekotiki/asr.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup
2. Phase 2: Foundational
3. Phase 3: User Story 1
4. **STOP and VALIDATE**: `uv run pytest`, then quickstart scenarios 1–5, 14, 15 on real models
5. Demo: paste the output into a video description

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → validate → MVP (text chapters)
3. US2 → validate → JSON / VTT / files for automation
4. US3 → validate → tuning for long streams and English titles
5. US4 → validate → fast re-runs
6. Polish → bench against SC-001…SC-006, README, release 0.1.0

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Verify each test fails for the right reason before implementing
- Commit after each task or logical group
- Constitution v1.0.0 is time-tracking-oriented; plan.md marks the non-applicable items N/A. Amend it via `/speckit-constitution` before or during implementation.

---

## Phase 8: Convergence

- [ ] T062 CRITICAL: resolve the constitution deviations that plan.md marks only as N/A (export/import JSON+CSV in Principle III, UTC timestamps, frozen-clock tests, 200 ms start/stop/status) — either amend `.specify/memory/constitution.md` to the video-timecode domain via `/speckit-constitution` and re-run the plan's Constitution Check, or record each deviation in the Complexity Tracking table of `specs/001-video-timecodes/plan.md` per Constitution V (contradicts)
- [ ] T063 Make `timekotiki models status` distinguish "Ollama is not reachable" (state `unavailable`, hint `start Ollama ('ollama serve')`) from "model not installed" (hint `timekotiki models pull`) in `src/timekotiki/cli.py` and `src/timekotiki/llm.py`, with e2e tests in `tests/e2e/test_models_cmd.py` written first per FR-015 / research R3 (partial)
- [ ] T064 Replace `tests/fixtures/speech_ru.ogg` (62 s synthetic `say` voice) with a ~30 s author-recorded Russian clip `tests/fixtures/speech_ru_30s.ogg` and update `tests/fixtures/README.md` and `tests/integration/test_real_models.py`, or record the synthetic-fixture decision in `specs/001-video-timecodes/research.md` R9 per T054 / research R9 (partial)
- [ ] T065 Document the decisions made during real-model runs in `specs/001-video-timecodes/research.md` (R2: `av>=12,<19` because faster-whisper 1.2 passes `metadata_errors` removed in PyAV 19; R3: 300 s request timeout reported as exit 7, `think: false` when `/api/show` lists the `thinking` capability, `OLLAMA_HOST=0.0.0.0`/`::` mapped to loopback) and the `0.0.0.0` rule in `specs/001-video-timecodes/contracts/cli.md` per T031 / research R2, R3 (unrequested)
- [ ] T066 Align `src/timekotiki/models.py` with data-model.md: either add the lazily computed `sha256` to `MediaSource` and validate `TranscriptSegment.end ≤ duration + 0.5 s` in `Transcript`, or update `specs/001-video-timecodes/data-model.md` to the current design, with unit tests first per data-model.md (partial)
- [ ] T067 Declare `numpy` in the `dev` dependency group of `pyproject.toml` (used directly by `tests/unit/test_media.py`) per Constitution V / Tech: Tooling (partial)
- [ ] T068 Verify the package installs as a tool from a built wheel in a clean environment (`uv build`, then `uv tool install dist/timekotiki-0.1.0-py3-none-any.whl` and `pipx install` of the same wheel, then `timekotiki --version`), and record the result in the quickstart.md Validation log per Constitution Tech: Packaging (partial)
