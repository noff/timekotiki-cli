<!--
Sync Impact Report
==================
Version change: (unversioned template) → 1.0.0
Modified principles: n/a (initial adoption)
  - [PRINCIPLE_1_NAME] → I. Test-First (NON-NEGOTIABLE)
  - [PRINCIPLE_2_NAME] → II. Text I/O & Machine-Readable Output
  - [PRINCIPLE_3_NAME] → III. Local-First Data Ownership
  - [PRINCIPLE_4_NAME] → IV. Stable CLI Contract & Semantic Versioning
  - [PRINCIPLE_5_NAME] → V. Simplicity (YAGNI)
Added sections: Technical Constraints; Development Workflow & Quality Gates; Governance
Removed sections: none
Templates: not modified (dependent templates read this file at runtime)
Follow-up TODOs: none
-->

# timekotiki-cli Constitution

## Core Principles

### I. Test-First (NON-NEGOTIABLE)

- Every behavior change MUST begin with a test that fails for the right reason, before any
  implementation code is written. Red → Green → Refactor is strictly enforced.
- Bug fixes MUST include a regression test that reproduces the bug before the fix lands.
- Each CLI command MUST have end-to-end tests that invoke it as a user would (arguments in,
  stdout/stderr/exit code out), in addition to unit tests of the underlying logic.
- Time-dependent logic MUST be tested with an injected or frozen clock; tests MUST NOT depend
  on the real wall clock, the host timezone, or test execution order.
- Code without tests MUST NOT be merged.

**Rationale**: A time tracker is only useful if its numbers are trusted. Test-first keeps every
duration, rounding rule and report verifiable, and keeps the CLI contract (Principle IV) guarded.

### II. Text I/O & Machine-Readable Output

- Input comes from arguments, flags and stdin; results go to stdout; diagnostics, warnings and
  errors go to stderr only.
- Every command that produces data MUST support `--json` output with a documented schema.
  Human-readable output is the default when stdout is a TTY.
- Exit codes MUST be stable and documented: `0` success, non-zero for distinct failure classes.
- Commands MUST NOT require interactive prompts to complete; any prompt MUST have a flag or
  stdin equivalent so the command is fully scriptable.
- Color and decoration MUST be disabled when stdout is not a TTY or when `NO_COLOR` is set.

**Rationale**: The CLI must compose with shells, scripts, status bars and other tools. Predictable
streams, JSON and exit codes make it automatable and debuggable.

### III. Local-First Data Ownership

- All core functionality (start/stop, edit, list, report) MUST work fully offline with no account
  and no network access.
- User data MUST be stored locally in a documented, open format at a location that follows
  platform conventions (XDG base directories on Linux/macOS, the equivalent on Windows), and that
  location MUST be overridable via an environment variable or flag.
- The user MUST always be able to export all of their data losslessly (at minimum JSON and CSV)
  and to import it back.
- No telemetry, analytics or network calls by default. Any network feature (e.g. sync) MUST be
  explicit opt-in and the tool MUST remain fully usable without it.
- Writes MUST be atomic (write-then-rename or a transactional store) so a crash or interrupt
  never corrupts existing records. Storage format changes MUST ship with an automatic,
  tested migration.

**Rationale**: Time logs are personal work records. Users must own them, trust them to survive,
and never be locked in.

### IV. Stable CLI Contract & Semantic Versioning

- Command names, flags, arguments, exit codes, `--json` schemas, environment variables and
  the on-disk data format form the public API.
- Releases follow Semantic Versioning (MAJOR.MINOR.PATCH). Any backward-incompatible change to
  the public API MUST bump MAJOR; new commands/flags/fields bump MINOR; fixes bump PATCH.
- Breaking changes MUST be preceded by at least one MINOR release that emits a deprecation
  warning on stderr, unless the change fixes data loss or a security defect.
- Every user-visible change MUST be recorded in a changelog.
- Contract tests MUST pin the `--json` schemas and exit codes so accidental breakage fails CI.

**Rationale**: Scripts and integrations built on the CLI must not break silently on upgrade.

### V. Simplicity (YAGNI)

- Build only what a current, specified user need requires. No speculative abstractions, plugin
  systems or configuration options without a concrete use case in a spec.
- Prefer the Python standard library. Each new runtime dependency MUST be justified in the
  feature plan (what it replaces, why the stdlib is insufficient, maintenance health).
- Any deviation from these principles MUST be recorded in the plan's Complexity Tracking table
  with the simpler alternative that was rejected and why.

**Rationale**: A small, focused tool is easier to test, install, audit and keep stable.

## Technical Constraints

- **Language**: Python 3.11+ with type hints on all public functions; code MUST pass static
  type checking (mypy or pyright) in strict mode for the package source.
- **Packaging**: A single `pyproject.toml`; the CLI MUST be installable with `pipx install` and
  `uv tool install` and MUST start without a compiler toolchain.
- **Tooling**: `pytest` for tests; `ruff` for lint and formatting. All three gates (tests, lint,
  types) MUST pass locally and in CI.
- **Time handling**: Timestamps MUST be stored as timezone-aware UTC; conversion to local time
  happens only at presentation. Durations MUST be computed from stored timestamps, never from
  accumulated counters, and rounding rules MUST be explicit and tested.
- **Performance**: Common commands (start, stop, status) SHOULD complete in under 200 ms on a
  typical laptop with a year of data, so the tool stays usable in prompts and status bars.
- **Platforms**: macOS and Linux MUST be supported; Windows SHOULD be supported unless a spec
  documents why not.

## Development Workflow & Quality Gates

- Features follow the Spec Kit flow: specify → (clarify) → plan → tasks → implement. The plan's
  Constitution Check MUST pass before implementation begins and be re-checked after design.
- Tasks MUST order test tasks before the implementation tasks they cover.
- A change is mergeable only when: tests were written first and now pass, lint and type checks
  pass, `--json` contract tests pass, the changelog is updated for user-visible changes, and
  `--help` text reflects any new or changed commands.
- Code review MUST verify compliance with this constitution; reviewers MUST reject unjustified
  complexity or untested behavior.

## Governance

- This constitution supersedes all other development practices for timekotiki-cli. Where a
  spec, plan or habit conflicts with it, the constitution wins until it is amended.
- **Amendments**: Proposed as a change to this file with a written rationale, the version bump
  type, and a migration note for any affected specs, plans or code. Amendments take effect when
  merged.
- **Versioning policy** for this document: MAJOR for removing or redefining a principle in a
  backward-incompatible way; MINOR for adding a principle or section or materially expanding
  guidance; PATCH for clarifications and wording fixes.
- **Compliance review**: Every plan runs the Constitution Check gate; every review verifies
  compliance; deviations MUST be justified in Complexity Tracking or the change is rejected.

**Version**: 1.0.0 | **Ratified**: 2026-10-31 | **Last Amended**: 2026-10-31
