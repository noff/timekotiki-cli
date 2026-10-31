from tests.conftest import DepsFactory


def test_version(make_deps: DepsFactory) -> None:
    env = make_deps()
    assert env.main(["--version"]) == 0
    assert env.stdout.getvalue().strip() == "0.1.0"


def test_help_lists_subcommands(make_deps: DepsFactory) -> None:
    env = make_deps()
    assert env.main(["--help"]) == 0
    out = env.stdout.getvalue()
    for name in ("generate", "models", "cache"):
        assert name in out


def test_unknown_flag_is_usage_error(make_deps: DepsFactory) -> None:
    env = make_deps()
    assert env.main(["--bogus"]) == 2
    assert env.stdout.getvalue() == ""
    assert env.stderr.getvalue().startswith("timekotiki: error:")


def test_no_command_is_usage_error(make_deps: DepsFactory) -> None:
    env = make_deps()
    assert env.main([]) == 2
    assert env.stdout.getvalue() == ""


GENERATE_FLAGS = [
    "--format",
    "--json",
    "--output",
    "--force",
    "--min-chapter",
    "--max-chapters",
    "--title-language",
    "--speech-language",
    "--asr-model",
    "--llm-model",
    "--no-cache",
    "--quiet",
]


def test_generate_help_documents_every_contract_flag(make_deps: DepsFactory) -> None:
    env = make_deps()
    assert env.main(["generate", "--help"]) == 0
    out = env.stdout.getvalue()
    for flag in GENERATE_FLAGS:
        assert flag in out, flag
    for default in ("large-v3-turbo", "qwen2.5:7b-instruct", "1m", "text"):
        assert default in out, default


def test_models_and_cache_help(make_deps: DepsFactory) -> None:
    for argv, expected in (
        (["models", "--help"], ["status", "pull"]),
        (["models", "status", "--help"], ["--json", "--asr-model", "--llm-model"]),
        (["models", "pull", "--help"], ["--asr-model", "--llm-model", "network"]),
        (["cache", "--help"], ["clear"]),
    ):
        env = make_deps()
        assert env.main(argv) == 0
        for word in expected:
            assert word in env.stdout.getvalue(), (argv, word)
