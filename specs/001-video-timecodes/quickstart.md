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
