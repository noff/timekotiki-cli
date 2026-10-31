# Quickstart: проверка фичи end-to-end

**Feature**: [spec.md](spec.md) | Контракты: [contracts/cli.md](contracts/cli.md)

## Предусловия

- Python 3.11+, `uv`.
- [Ollama](https://ollama.com) установлена и запущена (`ollama serve` или приложение).
- Около 7 ГБ свободного места на диске под модели.
- Тестовые файлы: `talk.mp4` с речью около 30 минут, `long.mkv` длиннее часа, `silence.wav`
  без речи.

## Установка

```bash
uv sync                         # dev-окружение
uv run timekotiki --version     # 0.1.0
```

## 1. Детерминированные тесты (без моделей)

```bash
uv run pytest                   # unit + contract + e2e на фейках
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

Ожидаемо: всё зелёное, сеть и модели не нужны.

## 2. Модели (единственный онлайн-шаг)

```bash
uv run timekotiki models status        # до загрузки: код 6, подсказка `models pull`
uv run timekotiki models pull
uv run timekotiki models status --json # обе модели "installed": true, код 0
```

## 3. Сценарии из спецификации (офлайн)

Перед шагом отключите сеть (Wi-Fi off), чтобы проверить FR-015 и FR-016.

| # | Команда | Ожидаемый результат | Источник |
|---|---------|---------------------|----------|
| 1 | `timekotiki generate talk.mp4` | stdout: строки `MM:SS Заголовок`, первая `00:00`; прогресс только в stderr; код 0 | US1/AC1, AC3 |
| 2 | `timekotiki generate long.mkv` | после часа тайм-коды вида `1:02:30` | US1/AC2 |
| 3 | `timekotiki generate missing.mp4; echo $?` | `timekotiki: error: …` в stderr, код 3 | US1/AC4 |
| 4 | `timekotiki generate silence.wav; echo $?` | «no speech detected», код 5, stdout пуст | Edge case |
| 5 | `timekotiki generate https://youtu.be/x; echo $?` | «only local files are supported», код 3 | Edge case |
| 6 | `timekotiki generate talk.mp4 --json \| python -m json.tool` | валидный JSON по [result.schema.json](contracts/result.schema.json), `transcript_cached: true` | US2/AC1, US4/AC1 |
| 7 | `timekotiki generate talk.mp4 -o ch.txt` дважды | второй раз: код 8; с `--force` — код 0 | US2/AC2 |
| 8 | `timekotiki generate talk.mp4 --format vtt` | `WEBVTT` + cue на каждую главу | US2/AC3 |
| 9 | `timekotiki generate long.mkv --max-chapters 10 --min-chapter 5m --json` | ≤ 10 глав, каждая (кроме последней) ≥ 300 с | US3/AC1, AC2 |
| 10 | `timekotiki generate talk.mp4 --title-language en` | заголовки на английском | US3/AC3 |
| 11 | `time timekotiki generate talk.mp4 --max-chapters 5` | этап `transcribe` пропущен, заметно быстрее | US4/AC1, SC-004 |
| 12 | `touch`-неизменённый vs. перекодированный `talk.mp4` | для изменённого файла распознавание заново | US4/AC2 |
| 13 | `timekotiki generate talk.mp4 --no-cache` | распознавание выполняется заново | US4/AC3 |
| 14 | `OLLAMA_HOST=10.0.0.5:11434 timekotiki generate talk.mp4` | отказ с кодом 6, никаких соединений | FR-016 |
| 15 | Ctrl+C во время распознавания с `-o out.txt` | код 130; `out.txt` не создан, кэш не повреждён | Edge case |

## 4. Интеграция и бенчмарк

```bash
uv run pytest -m models                              # реальные модели на фикстуре RU
TIMEKOTIKI_BENCH_DIR=~/bench uv run python scripts/bench.py
```

`bench.py` выводит отчёт с метриками, по которым сверяются критерии:

- доля эталонных границ в пределах ±30 с (SC-001, цель ≥ 80%);
- время на часовой ролик (SC-003, цель ≤ 15 мин);
- время повторного запуска (SC-004, цель ≤ 1 мин);
- пиковая память на 4-часовом ролике (SC-006, цель < 16 ГБ).

## Validation log

### 2026-10-31 — macOS, Apple M2 Max, 32 GB

**Deviations from the procedure**: the default models (`large-v3-turbo`, `qwen2.5:7b-instruct`)
were not installed, so the run used `--asr-model small --llm-model qwen3.5:9b-mlx`. The network
was **not** disabled; FR-016 relies on the loopback check (scenario 14) and unit tests. Inputs:
`tests/fixtures/speech_ru.ogg` (62 s), a 20 s silent WAV, a text file renamed to `.mp4`, and a
75-minute WAV made of 70 copies of the fixture.

| # | Result | Notes |
|---|--------|-------|
| 1 | ✅ | 2 chapters from `00:00`, progress only on stderr (needs `--min-chapter 10` for a 1-minute clip) |
| 2 | ✅ | 75-min file: `1:00:09`, `1:14:11` after the first hour; ~15 min with `small` while other runs shared the CPU; peak RSS ~1.2 GB |
| 3 | ✅ | exit 3 |
| 4 | ✅ | silence → "no speech detected", exit 5; text file as `.mp4` → exit 4 |
| 5 | ✅ | exit 3 with a hint |
| 6 | ✅ | valid JSON, `transcript_cached: true` on the repeated run |
| 7 | ✅ | second run exit 8, `--force` exit 0 |
| 8 | ✅ | WebVTT with one cue per chapter |
| 9 | ⚠️ not run on a real long video | covered by e2e tests with fakes |
| 10 | ✅ | English titles |
| 11 | ✅ | warm run 3.4 s, transcription skipped |
| 12 | ⚠️ not run manually | covered by `tests/e2e/test_generate_cache.py` |
| 13 | ✅ | transcription runs again |
| 14 | ✅ | exit 6, no connection attempted |
| 15 | ✅ | SIGINT during transcription: exit 130 after 0.1 s, no output, temp or cache files |

**Found during validation and fixed**: PyAV 19 is incompatible with faster-whisper 1.2 (pinned
`av<19`); thinking models took ~50 s per call (`think: false` is now sent when supported); an
LLM timeout was reported as "cannot reach Ollama" (now exit 7).

**Found during validation, still open**: files written with `-o` get mode `0600`, because
`tempfile.mkstemp` ignores the umask, and `--force` drops the original file's permissions.

**Packaging**: `uv tool install .` and `uv tool install --editable .` work from a clean tool
directory and `timekotiki --version` prints `0.1.0`; `pipx` is not installed on this machine,
so it was not checked. The titles on the 75-minute file repeat, because the input is one
clip repeated 70 times; the quality of SC-001/SC-002 still needs a real annotated set.
