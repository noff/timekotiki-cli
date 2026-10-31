from tests.contract.test_text_format import sample_result
from timekotiki.formats import render_vtt


def test_render_vtt_snapshot() -> None:
    assert render_vtt(sample_result()) == (
        "WEBVTT\n"
        "\n"
        "1\n"
        "00:00:00.000 --> 00:04:12.000\n"
        "Вступление\n"
        "\n"
        "2\n"
        "00:04:12.000 --> 01:02:30.000\n"
        "Настройка проекта\n"
        "\n"
        "3\n"
        "01:02:30.000 --> 01:06:40.000\n"
        "Итоги и вопросы\n"
    )
