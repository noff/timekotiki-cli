# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-31

### Added

- `timekotiki generate FILE` builds chapter timecodes for a local video or audio file, fully
  offline: faster-whisper speech recognition plus a local Ollama LLM for topics and titles.
- Output formats: text for video descriptions (default), `--json` / `--format json` with a
  versioned schema, and `--format vtt` (WebVTT chapters); `-o/--output` with `--force`.
- Granularity and language options: `--min-chapter`, `--max-chapters`, `--title-language`,
  `--speech-language`, `--asr-model`, `--llm-model`.
- Transcript cache keyed by file content, `--no-cache`, and `timekotiki cache clear`.
- `timekotiki models status` and `timekotiki models pull` (the only command that uses the
  network).
- Documented exit codes 0, 2–8 and 130; `OLLAMA_HOST` is restricted to loopback addresses.
