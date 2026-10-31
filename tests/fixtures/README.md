# Test fixtures

## `speech_ru.ogg`

62 s of Russian speech, mono OGG Opus at 16 kbit/s (about 125 KB). It was synthesised with the
macOS `say` command and the "Milena" voice from a script about writing a small CLI tool, with
1.5 s pauses between four topics:

| Starts at | Topic |
|-----------|-------|
| ~00:00 | Introduction: what the utility does |
| ~00:15 | Setting up the project (pyproject, dependencies, linter, uv) |
| ~00:30 | Tests first: timecode formatting |
| ~00:47 | Summary and goodbye |

Used only by `tests/integration` (`pytest -m models`). Each topic is shorter than the default
`--min-chapter` of 1 minute, so the integration tests pass `--min-chapter 10` to keep them.
