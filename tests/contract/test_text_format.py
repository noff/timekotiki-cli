from pathlib import Path

from timekotiki.formats import render_text
from timekotiki.models import Chapter, ChapterResult, Options


def sample_result() -> ChapterResult:
    return ChapterResult(
        source=Path("talk.mp4"),
        duration=4000.0,
        speech_language="ru",
        title_language="ru",
        chapters=(
            Chapter(0.0, 252.0, "Вступление"),
            Chapter(252.0, 3750.0, "Настройка проекта"),
            Chapter(3750.0, 4000.0, "Итоги и вопросы"),
        ),
        options=Options(),
    )


def test_render_text_snapshot() -> None:
    assert render_text(sample_result()) == (
        "00:00 Вступление\n04:12 Настройка проекта\n1:02:30 Итоги и вопросы\n"
    )
