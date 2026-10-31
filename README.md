# timekotiki

Генерирует тайм-коды глав для видео — готовые к вставке в описание ролика:

```text
00:00 Вступление
04:12 Настройка проекта
1:02:30 Итоги и вопросы
```

`timekotiki` распознаёт речь в локальном видео- или аудиофайле, делит её на темы и придумывает
заголовок для каждой. **Всё работает на вашем компьютере**: видео, звук и расшифровка никуда не
отправляются. Сеть нужна только один раз — когда вы явно скачиваете модели командой
`timekotiki models pull`.

## Установка

Нужны:

- [uv](https://docs.astral.sh/uv/) — менеджер Python-окружений (сам скачает подходящий Python 3.11+);
- [Ollama](https://ollama.com) — среда для локальных LLM, должна быть запущена (приложение или
  `ollama serve`).

Системный ffmpeg не нужен. Поддерживаются распространённые форматы: MP4, MKV, MOV, WebM, MP3,
WAV, M4A, OGG.

### Запуск из клонированного репозитория

Пакет не опубликован в PyPI, поэтому сразу после `git clone` команды `timekotiki` в системе
**нет** — `timekotiki: command not found` это нормально. Зависимости ставятся в локальное
окружение проекта (`.venv`), и команду нужно запускать через `uv run` из папки репозитория:

```bash
git clone <адрес репозитория> timekotiki-cli
cd timekotiki-cli
uv sync                               # один раз: создаёт .venv и ставит зависимости
uv run timekotiki models pull         # один раз: скачивает модели, около 7 ГБ
uv run timekotiki models status       # обе модели должны быть "installed"
uv run timekotiki generate talk.mp4
```

`uv run` сам находит `.venv` проекта, поэтому активировать окружение вручную не нужно.

### Запуск без `uv run`

Чтобы команда `timekotiki` работала из любой папки, установите её как инструмент:

```bash
cd timekotiki-cli
uv tool install .              # копия текущей версии; после git pull повторите с --reinstall
# или, если вы меняете код:
uv tool install --editable .   # изменения в src/ подхватываются без переустановки
```

Если после установки `timekotiki` всё равно не находится, каталог инструментов uv
(обычно `~/.local/bin`) не добавлен в `PATH`. Выполните `uv tool update-shell` и откройте
новый терминал. Удалить инструмент: `uv tool uninstall timekotiki`.

Дальше во всех примерах `timekotiki` — это либо установленная команда, либо `uv run timekotiki`.

### Модели

По умолчанию нужны `large-v3-turbo` (распознавание речи) и `qwen2.5:7b-instruct` (Ollama);
`timekotiki models pull` скачивает обе. Это единственная команда, которой нужна сеть. Если у
вас уже есть другие модели, их можно указать флагами, ничего не скачивая:

```bash
timekotiki generate talk.mp4 --asr-model small --llm-model qwen3.5:9b-mlx   # любая из ollama list
```

Если моделей нет, `generate` завершается с кодом 6 и подсказкой, что сделать.

## Использование

```bash
timekotiki generate talk.mp4                       # главы в stdout
timekotiki generate talk.mp4 -o chapters.txt       # записать в файл (--force — перезаписать)
timekotiki generate talk.mp4 --json                # машиночитаемый результат
timekotiki generate talk.mp4 --format vtt          # главы WebVTT для видеоплееров
timekotiki generate stream.mkv --max-chapters 12 --min-chapter 5m
timekotiki generate talk.mp4 --title-language en   # английские заголовки для русской речи
timekotiki generate talk.mp4 --no-cache            # распознать речь заново
timekotiki cache clear                             # удалить кэш расшифровок
```

Прогресс, предупреждения и ошибки выводятся в stderr, поэтому в stdout — только результат.
Флаг `-q` скрывает прогресс.

Дольше всего идёт распознавание речи. Его результат кэшируется по содержимому файла, поэтому
повторный запуск с другими `--min-chapter`, `--max-chapters` или `--title-language` заново
выполняет только этап LLM.

### Параметры `generate`

| Флаг | По умолчанию | Назначение |
|------|--------------|------------|
| `--format {text,json,vtt}` | `text` | Формат вывода; `--json` — сокращение для `--format json` |
| `-o, --output PATH` | stdout | Атомарно записать результат в файл |
| `--force` | выкл. | Разрешить `--output` перезаписать существующий файл |
| `--min-chapter DURATION` | `1m` | Минимальная длина главы: `90`, `1m30s`, `5m` (не меньше 10 с) |
| `--max-chapters N` | без ограничения | Максимальное число глав |
| `--title-language LANG` | язык речи | Код языка заголовков по ISO 639-1 |
| `--speech-language LANG` | автоопределение | Код языка речи по ISO 639-1 |
| `--asr-model NAME` | `large-v3-turbo` | Модель faster-whisper; `small` и `medium` быстрее |
| `--llm-model NAME` | `qwen2.5:7b-instruct` | Модель Ollama |
| `--no-cache` | выкл. | Не использовать сохранённую расшифровку |
| `-q, --quiet` | выкл. | Не показывать прогресс в stderr |

JSON-вывод соответствует схеме
[`result.schema.json`](specs/001-video-timecodes/contracts/result.schema.json).

### Коды выхода

| Код | Значение |
|-----|----------|
| 0 | Успех |
| 2 | Неверные аргументы |
| 3 | Файл не найден или не читается, либо передана ссылка вместо файла |
| 4 | Формат не поддерживается или файл повреждён |
| 5 | Нет звуковой дорожки или речи |
| 6 | Модели или Ollama недоступны, либо `OLLAMA_HOST` указывает не на этот компьютер |
| 7 | Ошибка обработки (распознавание или LLM) |
| 8 | Файл вывода уже существует (без `--force`) или не может быть записан |
| 130 | Прервано |

### Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `TIMEKOTIKI_CACHE_DIR` | Каталог кэша расшифровок (по умолчанию — стандартный каталог кэша платформы) |
| `OLLAMA_HOST` | Адрес Ollama; только loopback, например `127.0.0.1:11434` |
| `HF_HOME` | Где хранятся модели faster-whisper (стандарт Hugging Face) |
| `NO_COLOR` | Соблюдается: timekotiki никогда не выводит цвет |

## Разработка

Все команды выполняются из папки репозитория через `uv run`:

```bash
uv sync
uv run pytest                 # детерминированные тесты, модели не нужны
uv run pytest -m models       # реальные модели (переопределяются TIMEKOTIKI_TEST_ASR_MODEL / _LLM_MODEL)
uv run ruff check . && uv run ruff format --check . && uv run mypy
TIMEKOTIKI_BENCH_DIR=~/bench uv run python scripts/bench.py   # бенчмарк качества и скорости
```

Проектные документы лежат в [`specs/001-video-timecodes`](specs/001-video-timecodes/).
