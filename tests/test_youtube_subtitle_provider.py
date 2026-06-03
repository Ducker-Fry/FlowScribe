from pathlib import Path
from types import SimpleNamespace

from flowscribe.capabilities.subtitle import SubtitleCapability
from flowscribe.providers.subtitle.youtube import YouTubeNativeSubtitleProvider
from flowscribe.tasks.models import OutputContract, RuntimePreferences, SourceSpec, TaskSpec


def test_youtube_native_subtitle_provider_fetches_vtt(monkeypatch) -> None:
    provider = YouTubeNativeSubtitleProvider()

    monkeypatch.setattr(
        provider,
        "_extract_info",
        lambda url, **kwargs: {
            "id": "abc123",
            "title": "Demo Video",
            "subtitles": {
                "en": [
                    {"ext": "vtt", "url": "https://example.com/subs.vtt"},
                ]
            },
            "automatic_captions": {},
        },
    )
    monkeypatch.setattr(
        provider,
        "_download_text",
        lambda url, **kwargs: "WEBVTT\n\n00:00:00.000 --> 00:00:01.500\nHello world.\n\n00:00:01.500 --> 00:00:03.000\nSecond line.\n",
    )

    result = provider.fetch("https://www.youtube.com/watch?v=abc123", language="en")

    assert result.language == "en"
    assert result.subtitle_format == "vtt"
    assert result.transcript.text == "Hello world.\nSecond line."
    assert result.transcript.metadata["source_url"] == "https://www.youtube.com/watch?v=abc123"


def test_youtube_language_preference_uses_matching_auto_caption_before_other_manual(monkeypatch) -> None:
    provider = YouTubeNativeSubtitleProvider()

    monkeypatch.setattr(
        provider,
        "_extract_info",
        lambda url, **kwargs: {
            "id": "abc123",
            "title": "Demo Video",
            "subtitles": {
                "de": [{"ext": "vtt", "url": "https://example.com/de.vtt"}],
            },
            "automatic_captions": {
                "en": [{"ext": "vtt", "url": "https://example.com/en-auto.vtt"}],
            },
        },
    )
    monkeypatch.setattr(
        provider,
        "_download_text",
        lambda url, **kwargs: (
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nEnglish auto.\n"
            if "en-auto" in url
            else "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nGerman manual.\n"
        ),
    )

    result = provider.fetch("https://www.youtube.com/watch?v=abc123", language="en")

    assert result.source_kind == "automatic_captions"
    assert result.language == "en"
    assert result.transcript.text == "English auto."


def test_subtitle_capability_writes_artifacts_for_youtube(monkeypatch, tmp_path: Path) -> None:
    provider_result = YouTubeNativeSubtitleProvider().fetch

    def fake_fetch(url: str, **kwargs):
        return provider_result.__self__.__class__()._build_transcript(  # type: ignore[attr-defined]
            media_name="demo-video",
            subtitle_payload="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello subtitle.\n",
            subtitle_format="vtt",
            transcript_language="en",
            provider_name="youtube-native-subtitle",
            task="transcribe",
            initial_prompt=None,
            preset=None,
            word_timestamps=False,
            source_url=url,
            title="Demo Video",
            source_kind="subtitles",
        )

    def fake_provider_fetch(self, url: str, **kwargs):
        transcript = fake_fetch(url, **kwargs)
        return SimpleNamespace(
            transcript=transcript,
            language="en",
            source_kind="subtitles",
            title="Demo Video",
            subtitle_format="vtt",
        )

    monkeypatch.setattr(
        "flowscribe.capabilities.subtitle.YouTubeNativeSubtitleProvider.fetch",
        fake_provider_fetch,
    )

    capability = SubtitleCapability()
    task = TaskSpec(
        task_id="task-1",
        source=SourceSpec(kind="url", value="https://www.youtube.com/watch?v=abc123"),
        requested_capabilities=("subtitle", "transcribe"),
        output_contract=OutputContract(formats=("txt", "json", "srt", "vtt"), output_dir=tmp_path, overwrite=True),
        runtime_preferences=RuntimePreferences(),
        raw_metadata={"task": "transcribe", "timestamps": True, "provider_name": "local-whisper"},
    )

    result = capability.run(task)

    assert result.status == "success"
    assert result.artifacts
    assert {path.suffix for path in result.artifacts[0].paths} == {".txt", ".json", ".srt", ".vtt"}
    assert (tmp_path / "demo-video.txt").read_text(encoding="utf-8") == "Hello subtitle.\n"
