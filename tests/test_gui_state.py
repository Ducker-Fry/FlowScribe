from pathlib import Path

import pytest

from flowscribe.core.errors import DownloadError
from flowscribe.gui.state import GuiTranscriptionForm, is_acceptable_local_source


def test_gui_form_builds_local_job(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    output = tmp_path / "out"

    form = GuiTranscriptionForm(
        local_paths=(media,),
        output_dir=output,
        output_name_base="custom-lesson",
        provider_name="native-engine",
        model_name="medium",
        language="zh",
        preset="zh",
        output_formats=("txt", "md", "json", "vtt"),
        timestamps=True,
        word_timestamps=True,
        overwrite=True,
        native_threads=6,
    )

    job = form.to_job()

    assert job.sources[0].kind == "local"
    assert job.sources[0].value == str(media)
    assert job.output_dir == output
    assert job.output_name_base == "custom-lesson"
    assert job.provider_name == "native-engine"
    assert job.model_name == "medium"
    assert job.language == "zh"
    assert job.preset == "zh"
    assert job.output_formats == ("txt", "md", "json", "vtt")
    assert job.timestamps is True
    assert job.word_timestamps is True
    assert job.overwrite is True
    assert job.native_threads == 6


def test_gui_form_builds_url_job_with_network_options(tmp_path: Path) -> None:
    cookies = tmp_path / "cookies.txt"
    media_dir = tmp_path / "saved-media"
    form = GuiTranscriptionForm(
        url="https://example.com/watch",
        output_dir=tmp_path / "out",
        keep_media=True,
        url_media_kind="video",
        url_media_output_dir=media_dir,
        auto_bind_media=False,
        network_family="ipv4",
        proxy="http://127.0.0.1:7890",
        cookies_path=cookies,
    )

    job = form.to_job()

    assert job.sources[0].kind == "url"
    assert job.sources[0].value == "https://example.com/watch"
    assert job.sources[0].keep_media is True
    assert job.sources[0].url_media_kind == "video"
    assert job.sources[0].media_output_dir == media_dir
    assert job.sources[0].auto_bind_media is False
    assert job.network_family == "ipv4"
    assert job.proxy == "http://127.0.0.1:7890"
    assert job.cookies_path == cookies


def test_gui_form_accepts_paraformer_provider(tmp_path: Path) -> None:
    media = tmp_path / "video.mp4"
    form = GuiTranscriptionForm(
        local_paths=(media,),
        provider_name="paraformer",
        model_name="paraformer-zh",
        language="zh",
        preset="zh",
    )

    job = form.to_job()

    assert job.provider_name == "paraformer"
    assert job.model_name == "paraformer-zh"
    assert job.language == "zh"


def test_gui_form_rejects_empty_sources() -> None:
    form = GuiTranscriptionForm()

    with pytest.raises(ValueError, match="Add at least one"):
        form.to_job()


def test_gui_form_rejects_invalid_url() -> None:
    form = GuiTranscriptionForm(url="not-a-url")

    with pytest.raises(ValueError, match="http"):
        form.to_job()


def test_gui_form_reuses_url_safety_validation(monkeypatch) -> None:
    def fake_validate_public_http_url(url: str, *, network_family: str = "auto") -> None:
        assert url == "http://localhost/audio.mp3"
        assert network_family == "ipv4"
        raise DownloadError("Localhost URLs are blocked for safety.")

    monkeypatch.setattr(
        "flowscribe.gui.state.validate_public_http_url",
        fake_validate_public_http_url,
    )
    form = GuiTranscriptionForm(
        url="http://localhost/audio.mp3",
        network_family="ipv4",
    )

    with pytest.raises(ValueError, match="Localhost URLs are blocked for safety."):
        form.to_job()


def test_gui_form_preview_is_plain_data(tmp_path: Path) -> None:
    media_dir = tmp_path / "saved-media"
    form = GuiTranscriptionForm(
        local_paths=(tmp_path / "a.mp4",),
        url="https://example.com/video",
        keep_media=True,
        url_media_kind="audio",
        url_media_output_dir=media_dir,
        cookies_path=tmp_path / "cookies.txt",
    )

    preview = form.preview()

    assert preview["sources"][0]["kind"] == "local"
    assert preview["sources"][1]["kind"] == "url"
    assert preview["sources"][1]["media_output_dir"] == str(media_dir)
    assert preview["sources"][1]["auto_bind_media"] is True
    assert preview["cookies_path"].endswith("cookies.txt")
    assert preview["output_name_base"] is None
    assert preview["provider_name"] == "local-whisper"
    assert preview["native_threads"] is None


def test_gui_form_rejects_file_path_for_url_media_output_dir(tmp_path: Path) -> None:
    bad_target = tmp_path / "saved-media.txt"
    bad_target.write_text("not a directory", encoding="utf-8")
    form = GuiTranscriptionForm(
        url="https://example.com/watch",
        keep_media=True,
        url_media_output_dir=bad_target,
    )

    with pytest.raises(ValueError, match="save path must be a folder"):
        form.to_job()


def test_gui_accepts_cli_supported_local_sources(tmp_path: Path) -> None:
    wav = tmp_path / "sample.wav"
    wav.write_bytes(b"placeholder")
    folder = tmp_path / "folder"
    folder.mkdir()
    text = tmp_path / "notes.txt"
    text.write_text("notes", encoding="utf-8")

    assert is_acceptable_local_source(wav)
    assert is_acceptable_local_source(folder)
    assert not is_acceptable_local_source(text)
