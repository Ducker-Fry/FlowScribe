from pathlib import Path

from flowscribe.cli.args import CliOptions, DoctorOptions, SimpleCommandOptions, parse_args
from flowscribe.cli.doctor import check_output_dir, resolve_faster_whisper_repo


def test_parse_doctor_args() -> None:
    options = parse_args(["doctor", "-o", "health-out", "--model", "tiny"])

    assert isinstance(options, DoctorOptions)
    assert options.command == "doctor"
    assert options.output_dir == Path("health-out")
    assert options.model_name == "tiny"


def test_parse_transcribe_subcommand_args() -> None:
    options = parse_args(["transcribe", "video.mp4", "-o", "out", "--format", "txt,md,json,srt"])

    assert isinstance(options, CliOptions)
    assert options.command == "transcribe"
    assert options.inputs == [Path("video.mp4")]
    assert options.output_dir == Path("out")
    assert options.output_formats == ("txt", "md", "json", "srt")


def test_parse_legacy_transcribe_args() -> None:
    options = parse_args(["video.mp4", "-o", "out"])

    assert isinstance(options, CliOptions)
    assert options.command == "transcribe"
    assert options.inputs == [Path("video.mp4")]
    assert options.output_formats == ("txt", "md")


def test_parse_simple_command_args() -> None:
    options = parse_args(["version"])

    assert isinstance(options, SimpleCommandOptions)
    assert options.command == "version"


def test_doctor_output_dir_check_writes_temp_file(tmp_path: Path) -> None:
    check = check_output_dir(tmp_path / "out")

    assert check.ok
    assert "writable" in check.message


def test_resolve_known_faster_whisper_model_repo() -> None:
    assert resolve_faster_whisper_repo("small") == "Systran/faster-whisper-small"


def test_resolve_explicit_hugging_face_repo() -> None:
    assert resolve_faster_whisper_repo("org/model") == "org/model"
