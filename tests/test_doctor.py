from pathlib import Path

from flowscribe.cli.args import (
    CliOptions,
    DoctorOptions,
    InspectOptions,
    SearchOptions,
    SimpleCommandOptions,
    parse_args,
    parse_time_value,
)
from flowscribe.cli.doctor import (
    check_native_model_path,
    check_output_dir,
    resolve_faster_whisper_repo,
)


def test_parse_doctor_args() -> None:
    options = parse_args(["doctor", "-o", "health-out", "--model", "tiny"])

    assert isinstance(options, DoctorOptions)
    assert options.command == "doctor"
    assert options.output_dir == Path("health-out")
    assert options.provider_name == "local-whisper"
    assert options.model_name == "tiny"
    assert options.skip_model_access is False


def test_parse_doctor_args_supports_native_provider() -> None:
    options = parse_args(
        [
            "doctor",
            "--provider",
            "native-engine",
            "--model",
            "models\\ggml-base.en.bin",
            "--hello-smoke",
        ]
    )

    assert isinstance(options, DoctorOptions)
    assert options.provider_name == "native-engine"
    assert options.hello_smoke is True


def test_parse_doctor_args_supports_skip_model_access() -> None:
    options = parse_args(["doctor", "--skip-model-access"])

    assert isinstance(options, DoctorOptions)
    assert options.skip_model_access is True


def test_run_doctor_can_skip_model_access(monkeypatch, tmp_path: Path) -> None:
    from flowscribe.cli.doctor import run_doctor

    monkeypatch.setattr("flowscribe.cli.doctor.check_command", lambda name: type("C", (), {"name": name, "ok": True, "message": "ok", "marker": "OK"})())
    monkeypatch.setattr("flowscribe.cli.doctor.check_python_version", lambda: type("C", (), {"name": "Python", "ok": True, "message": "ok", "marker": "OK"})())
    monkeypatch.setattr("flowscribe.cli.doctor.check_output_dir", lambda path: type("C", (), {"name": "Output directory", "ok": True, "message": "ok", "marker": "OK"})())
    monkeypatch.setattr("flowscribe.cli.doctor.check_faster_whisper_import", lambda: type("C", (), {"name": "faster-whisper", "ok": True, "message": "ok", "marker": "OK"})())

    called = {"model_access": False}

    def fail_if_called(model_name: str):
        called["model_access"] = True
        raise AssertionError("check_model_download should be skipped")

    monkeypatch.setattr("flowscribe.cli.doctor.check_model_download", fail_if_called)

    exit_code = run_doctor(
        output_dir=tmp_path / "out",
        provider_name="local-whisper",
        model_name="small",
        skip_model_access=True,
        print_result=False,
    )

    assert exit_code == 0
    assert called["model_access"] is False


def test_parse_transcribe_subcommand_args() -> None:
    options = parse_args(
        [
            "transcribe",
            "video.mp4",
            "-o",
            "out",
            "--format",
            "txt,md,json,srt,vtt",
            "--word-timestamps",
            "--no-vad-filter",
        ]
    )

    assert isinstance(options, CliOptions)
    assert options.command == "transcribe"
    assert options.inputs == [Path("video.mp4")]
    assert options.output_dir == Path("out")
    assert options.output_formats == ("txt", "md", "json", "srt", "vtt")
    assert options.word_timestamps is True
    assert options.vad_filter is False
    assert options.no_vad_filter is True


def test_parse_legacy_transcribe_args() -> None:
    options = parse_args(["video.mp4", "-o", "out"])

    assert isinstance(options, CliOptions)
    assert options.command == "transcribe"
    assert options.inputs == [Path("video.mp4")]
    assert options.output_formats == ("txt", "md")
    assert options.no_vad_filter is False


def test_vad_flags_are_mutually_exclusive() -> None:
    try:
        parse_args(["transcribe", "video.mp4", "--vad-filter", "--no-vad-filter"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected argparse to reject mutually exclusive VAD flags.")


def test_parse_simple_command_args() -> None:
    options = parse_args(["version"])

    assert isinstance(options, SimpleCommandOptions)
    assert options.command == "version"


def test_parse_search_args() -> None:
    options = parse_args(
        [
            "search",
            "lesson.json",
            "keyword",
            "--context-chars",
            "12",
            "--limit",
            "10",
            "--after",
            "00:10:00",
            "--before",
            "00:30:00",
            "--json",
        ]
    )

    assert isinstance(options, SearchOptions)
    assert options.command == "search"
    assert options.transcript == Path("lesson.json")
    assert options.query == "keyword"
    assert options.context_chars == 12
    assert options.limit == 10
    assert options.after_seconds == 600
    assert options.before_seconds == 1800
    assert options.json_output is True


def test_parse_inspect_args() -> None:
    options = parse_args(
        [
            "inspect",
            "https://example.com/video",
            "--json",
            "--timeout",
            "12",
            "--network-family",
            "ipv4",
        ]
    )

    assert isinstance(options, InspectOptions)
    assert options.command == "inspect"
    assert options.source == "https://example.com/video"
    assert options.json_output is True
    assert options.timeout_seconds == 12
    assert options.network_family == "ipv4"


def test_parse_time_value_accepts_common_timestamp_forms() -> None:
    assert parse_time_value("12.5") == 12.5
    assert parse_time_value("03:21.4") == 201.4
    assert parse_time_value("01:02:03") == 3723


def test_doctor_output_dir_check_writes_temp_file(tmp_path: Path) -> None:
    check = check_output_dir(tmp_path / "out")

    assert check.ok
    assert "writable" in check.message


def test_resolve_known_faster_whisper_model_repo() -> None:
    assert resolve_faster_whisper_repo("small") == "Systran/faster-whisper-small"


def test_resolve_explicit_hugging_face_repo() -> None:
    assert resolve_faster_whisper_repo("org/model") == "org/model"


def test_check_native_model_path_requires_existing_bin(tmp_path: Path) -> None:
    missing = check_native_model_path(str(tmp_path / "missing.bin"))
    wrong_suffix = check_native_model_path(str(tmp_path / "model.txt"))
    valid_model = tmp_path / "model.bin"
    valid_model.write_bytes(b"model")

    assert missing.ok is False
    assert "requires --model" in missing.message

    (tmp_path / "model.txt").write_text("bad", encoding="utf-8")
    wrong_suffix = check_native_model_path(str(tmp_path / "model.txt"))
    assert wrong_suffix.ok is False
    assert ".bin" in wrong_suffix.message

    valid = check_native_model_path(str(valid_model))
    assert valid.ok is True
