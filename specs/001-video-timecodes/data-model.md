# Data Model: Генерация тайм-кодов из видеоролика

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Все сущности — неизменяемые dataclass'ы (`frozen=True`) в `src/timekotiki/models.py`.
Время везде — смещение от начала ролика в секундах (`float`, ≥ 0).

## MediaSource

Входной файл после проверки (`media.py`).

| Поле | Тип | Правила |
|------|-----|---------|
| `path` | `Path` | Абсолютный, существует, читается. URL отклоняется (код 3) |
| `duration` | `float` | > 0; из контейнера |
| `has_audio` | `bool` | `False` → ошибка `NoAudioError` (код 5) |
| `sha256` | `str` | 64 hex; вычисляется лениво для кэша |

## TranscriptSegment

| Поле | Тип | Правила |
|------|-----|---------|
| `index` | `int` | 0..n-1, непрерывно |
| `start` | `float` | ≥ 0, ≤ `end` |
| `end` | `float` | ≤ `MediaSource.duration` (+ допуск 0.5 с) |
| `text` | `str` | Непустой после `strip()` |

## Transcript

| Поле | Тип | Правила |
|------|-----|---------|
| `segments` | `tuple[TranscriptSegment, ...]` | Отсортированы по `start`; пустой → `NoSpeechError` (код 5) |
| `language` | `str` | ISO 639-1 (`ru`, `en`, …), определён ASR или задан |
| `asr_model` | `str` | Имя модели, часть ключа кэша |
| `duration` | `float` | Длительность медиа |

**Кэш-представление** (JSON): `{"format_version": 1, "sha256", "asr_model", "language",
"duration", "segments": [{"start", "end", "text"}]}`. Несовпадение `format_version` → запись
считается отсутствующей.

## Boundary (внутренняя)

Результат прохода A до постобработки.

| Поле | Тип | Правила |
|------|-----|---------|
| `segment_index` | `int` | Валидный индекс сегмента, иначе отбрасывается |
| `topic_hint` | `str` | Черновая тема; используется только как подсказка в проходе B |

## Chapter

| Поле | Тип | Правила |
|------|-----|---------|
| `start` | `float` | Первая глава = 0.0; строго возрастает |
| `end` | `float` | = `start` следующей главы; у последней = `duration` |
| `title` | `str` | 1..60 символов, без переводов строк |
| `timecode` | `str` (вычисляемое) | `MM:SS` при `start` < 3600, иначе `H:MM:SS`; floor до секунд |

**Инварианты списка глав** (проверяются в `postprocess.py` и тестах):
1. `chapters[0].start == 0.0`.
2. `chapters[i].start < chapters[i+1].start`, а отформатированные тайм-коды строго возрастают
   (главы, совпавшие после floor, сливаются).
3. `end - start ≥ min_chapter` для всех, кроме, возможно, последней.
4. `len(chapters) ≤ max_chapters`, если задан.
5. Все `start ≤ duration`.

## Options

| Поле | Тип | По умолчанию | Правила |
|------|-----|--------------|---------|
| `min_chapter` | `float` (сек) | 60 | ≥ 10; CLI принимает `90`, `1m30s`, `5m` |
| `max_chapters` | `int \| None` | `None` | ≥ 1 |
| `title_language` | `str \| None` | `None` → язык речи | ISO 639-1 |
| `speech_language` | `str \| None` | `None` → автоопределение | ISO 639-1 |
| `asr_model` | `str` | `large-v3-turbo` | — |
| `llm_model` | `str` | `qwen2.5:7b-instruct` | — |
| `use_cache` | `bool` | `True` | `--no-cache` → `False` (чтение пропускается, запись остаётся) |

## ChapterResult

Итог работы конвейера, источник для всех форматов вывода.

| Поле | Тип |
|------|-----|
| `source` | `Path` (имя файла в выводе) |
| `duration` | `float` |
| `speech_language` | `str` |
| `title_language` | `str` |
| `chapters` | `tuple[Chapter, ...]` |
| `options` | `Options` (параметры, фактически применённые) |
| `warnings` | `tuple[str, ...]` (например, `fewer_than_3_chapters`) |
| `transcript_cached` | `bool` |

## Состояния конвейера

```text
probe ──► (cache hit?) ──yes──► segment ──► postprocess ──► title ──► render
   │            │no                                                    │
   │            ▼                                                      ▼
   │        transcribe ──► cache write                          stdout | file (atomic)
   ▼
 error → код выхода (contracts/cli.md)
```
