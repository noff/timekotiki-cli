# Implementation Plan: Генерация тайм-кодов из видеоролика

**Branch**: `001-video-timecodes` | **Date**: 2026-10-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-video-timecodes/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

CLI `timekotiki` принимает локальный видео- или аудиофайл и выдаёт список глав
(`00:00 Вступление`) в текстовом виде, JSON или WebVTT. Конвейер полностью локальный:
распознавание речи с тайм-стампами через faster-whisper → разбиение расшифровки на
смысловые разделы и генерация заголовков локальной LLM через Ollama на loopback-адресе →
детерминированная постобработка (первая глава `00:00`, минимальная длительность, максимум
глав) → сериализация. Расшифровка кэшируется по SHA-256 содержимого файла, поэтому повторный
запуск с другими параметрами пропускает распознавание. Модели скачиваются только явной
командой `timekotiki models pull`; после этого генерация работает без сети. Детали и
альтернативы — в [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+ (разработка на 3.13)

**Primary Dependencies**: `faster-whisper` (распознавание речи, декодирование аудио через
встроенный PyAV — системный ffmpeg не нужен); Ollama как внешнее локальное приложение для
LLM (вызывается через `urllib` stdlib на `127.0.0.1`, без Python-зависимости). CLI —
`argparse` (stdlib).

**Storage**: Файловый кэш расшифровок (JSON) в пользовательском каталоге кэша по конвенциям
платформы, переопределяется `TIMEKOTIKI_CACHE_DIR`. Результат — в stdout или файл с атомарной
записью.

**Testing**: `pytest`; ASR и LLM за протоколами с фейковыми реализациями для детерминированных
unit/contract/e2e-тестов; интеграционные тесты с реальными моделями помечены `@pytest.mark.models`
и запускаются явно. `ruff` (lint + format), `mypy --strict`.

**Target Platform**: macOS (Apple Silicon/Intel) и Linux, обязательно; Windows — желательно.

**Project Type**: CLI (single project)

**Performance Goals**: часовой ролик ≤ 15 мин end-to-end на типичном ноутбуке (SC-003);
повторная генерация из кэша ≤ 1 мин (SC-004).

**Constraints**: Без сети при генерации (FR-015/016); единственный сетевой сокет — loopback к
Ollama. 4-часовой ролик в пределах 16 ГБ RAM (SC-006). Прерывание не оставляет повреждённых
файлов.

**Scale/Scope**: Один пользователь, один файл за запуск; ролики от 1 минуты до 4+ часов;
3 подкоманды (`generate`, `models`, `cache`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Конституция v1.0.0 написана под трекер времени; часть формулировок не применима к этой фиче.
Ниже — проверка по существу, неприменимые пункты отмечены «N/A» с обоснованием.

| Принцип | Статус | Как соблюдается |
|---------|--------|-----------------|
| I. Test-First | ✅ PASS | Тесты пишутся до кода (порядок в tasks.md). ASR/LLM за протоколами → детерминированные фейки; e2e-тесты вызывают `main(argv)` как пользователь (argv → stdout/stderr/exit code) плюс subprocess-смоук. «Замороженные часы» → N/A: нет логики, зависящей от wall-clock; аналог — фиксированные фейковые расшифровки. |
| II. Text I/O & JSON | ✅ PASS | Результат → stdout, прогресс/ошибки → stderr; `--json`; документированные коды выхода ([contracts/cli.md](contracts/cli.md)); без интерактивных промптов; цвет/прогресс отключаются вне TTY и при `NO_COLOR`. |
| III. Local-First | ✅ PASS (с оговоркой) | Обработка полностью локальная, без аккаунта и телеметрии; загрузка моделей только явной командой; атомарная запись результата и кэша; каталог кэша по XDG/платформе с override. Loopback-HTTP к Ollama → см. Complexity Tracking. «start/stop/edit/report» и «экспорт/импорт данных» → N/A: у фичи нет пользовательского хранилища; кэш — производные данные, удаляемые без потерь, результат сам по себе является экспортом (text/JSON/VTT). Миграции формата кэша: версия формата в файле, несовпадение → пересоздание. |
| IV. Stable CLI Contract | ✅ PASS | Публичный API зафиксирован в [contracts/](contracts/); JSON-схема и коды выхода закреплены contract-тестами; CHANGELOG.md с первого релиза; версия 0.1.0. |
| V. Simplicity | ✅ PASS (с оговоркой) | stdlib для CLI, HTTP, путей, хэшей. Одна runtime-зависимость (`faster-whisper`) и одно внешнее приложение (Ollama) — обоснованы ниже. |
| Tech: Python 3.11+, strict types, pyproject, pipx/uv | ✅ PASS | faster-whisper поставляется колёсами для macOS/Linux/Windows — компилятор не нужен. |
| Tech: UTC timestamps, 200 мс на start/stop/status | N/A | Время в фиче — смещения от начала видео (float секунды), не моменты календарного времени. Нет команд start/stop/status. Аналог: `--help`, `models status`, `cache clear` отвечают мгновенно. |

**Gate result**: PASS. Рекомендуется амендмент конституции (MAJOR) под реальный домен
до `/speckit-tasks`, чтобы проверки не опирались на N/A.

**Post-design re-check (после Phase 1)**: PASS — контракты, модель данных и quickstart не
вводят новых зависимостей, сетевых вызовов или интерактивности сверх перечисленного выше.

## Project Structure

### Documentation (this feature)

```text
specs/001-video-timecodes/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── cli.md           # Команды, флаги, коды выхода, env
│   └── result.schema.json  # JSON-схема вывода --json
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml
CHANGELOG.md
src/timekotiki/
├── __init__.py          # __version__
├── __main__.py          # python -m timekotiki
├── cli.py               # argparse, main(argv, deps) -> exit code, вывод в stdout/stderr
├── errors.py            # иерархия исключений ↔ коды выхода
├── models.py            # dataclasses: VideoSource, Transcript, TranscriptSegment, Chapter, ChapterResult, Options
├── media.py             # проверка входа: существование, URL, наличие аудиодорожки, длительность (PyAV)
├── asr.py               # протокол Transcriber + FasterWhisperTranscriber
├── llm.py               # протокол ChapterModel + OllamaChapterModel (urllib, loopback-only)
├── segmentation.py      # окна расшифровки, сбор границ от LLM, слияние
├── postprocess.py       # 00:00, мин. длительность, макс. глав, привязка к сегментам, предупреждения
├── formats.py           # форматирование тайм-кодов; text / json / webvtt
├── cache.py             # SHA-256 файла, каталог кэша, атомарное чтение/запись расшифровки
├── fsutil.py            # атомарная запись (tmp + os.replace), проверка конфликта вывода
├── progress.py          # прогресс по этапам в stderr (TTY/NO_COLOR-aware)
└── pipeline.py          # оркестрация: media → cache/asr → segmentation → postprocess → result

tests/
├── conftest.py          # фейковые Transcriber/ChapterModel, фабрики расшифровок
├── unit/                # formats, postprocess, segmentation, cache, fsutil, errors
├── contract/            # JSON-схема, коды выхода, формат text/VTT, --help
├── e2e/                 # main(argv) с фейками; subprocess-смоук `python -m timekotiki`
├── integration/         # @pytest.mark.models: реальные faster-whisper + Ollama
└── fixtures/            # короткие аудио (тишина, речь RU ~30 с), битый файл, эталонные главы
```

**Structure Decision**: Один пакет `src/timekotiki` (src-layout) с плоскими модулями по этапам
конвейера; тесты разделены по видам, чтобы contract-тесты закрепляли публичный API
(принцип IV), а интеграция с реальными моделями была опциональной.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Runtime-зависимость `faster-whisper` (+ транзитивно ctranslate2, av, huggingface_hub, tokenizers, onnxruntime) | Распознавание речи с тайм-стампами — ядро фичи; stdlib этого не умеет. Даёт и декодирование аудио (PyAV), и VAD. | `openai-whisper` (PyTorch, ~2 ГБ, медленнее на CPU); `mlx-whisper` (только macOS); `whisper.cpp` через subprocess (нужна сборка или отдельная установка бинарника и моделей). |
| Внешнее приложение Ollama + HTTP на `127.0.0.1` | Смысловое разбиение и заголовки на русском требуют LLM; Ollama даёт готовые квантованные модели, Metal/CUDA-ускорение и JSON-structured output без Python-зависимостей. Трафик не покидает машину; адрес не-loopback отвергается. | `llama-cpp-python` (часто требует компилятор — нарушает Tech Constraints); `transformers` (PyTorch, тяжело и медленно на CPU); алгоритмическая сегментация по эмбеддингам без LLM (не даёт заголовков — всё равно нужна LLM). |
