"""Tests for download options functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


from flowscribe.tasks.models import DownloadOptions, SourceSpec
from flowscribe.input.url_downloader import DownloadOptions as UrlDownloadOptions
from flowscribe.input.url_downloader import UrlAudioDownloader


class TestDownloadOptions:
    """Test download options data structure."""

    def test_default_options(self):
        """Test default download options."""
        opts = DownloadOptions()
        assert opts.quality == "best"
        assert opts.prefer_format is None

    def test_custom_options(self):
        """Test custom download options."""
        opts = DownloadOptions(quality="high", prefer_format="mp4")
        assert opts.quality == "high"
        assert opts.prefer_format == "mp4"


class TestUrlDownloadOptions:
    """Test URL downloader download options."""

    def test_default_url_options(self):
        """Test default URL download options."""
        opts = UrlDownloadOptions()
        assert opts.media_kind == "audio"
        assert opts.quality == "best"
        assert opts.prefer_format is None

    def test_custom_url_options(self):
        """Test custom URL download options."""
        opts = UrlDownloadOptions(
            media_kind="video", quality="medium", prefer_format="webm"
        )
        assert opts.media_kind == "video"
        assert opts.quality == "medium"
        assert opts.prefer_format == "webm"


class TestSourceSpecMediaType:
    """Test SourceSpec with media type options."""

    def test_source_spec_audio_type(self):
        """Test SourceSpec with audio media type."""
        download_opts = DownloadOptions(quality="high")
        source = SourceSpec(
            kind="url",
            value="https://example.com/video",
            keep_media=True,
            url_media_kind="audio",
            download_options=download_opts,
            auto_bind_media=True,
        )
        assert source.url_media_kind == "audio"
        assert source.keep_media is True
        assert source.auto_bind_media is True
        assert source.download_options.quality == "high"

    def test_source_spec_video_type(self):
        """Test SourceSpec with video media type."""
        download_opts = DownloadOptions(quality="medium", prefer_format="mp4")
        source = SourceSpec(
            kind="url",
            value="https://example.com/video",
            keep_media=True,
            url_media_kind="video",
            download_options=download_opts,
            auto_bind_media=True,
        )
        assert source.url_media_kind == "video"
        assert source.keep_media is True
        assert source.auto_bind_media is True
        assert source.download_options.quality == "medium"
        assert source.download_options.prefer_format == "mp4"


class TestFormatSelector:
    """Test format selector building."""

    def test_audio_best_quality(self):
        """Test audio best quality format selector."""
        selector = UrlAudioDownloader._build_format_selector("audio", "best")
        assert selector == "bestaudio"

    def test_audio_high_quality(self):
        """Test audio high quality format selector."""
        selector = UrlAudioDownloader._build_format_selector("audio", "high")
        assert selector == "bestaudio[abr>=128]"

    def test_audio_medium_quality(self):
        """Test audio medium quality format selector."""
        selector = UrlAudioDownloader._build_format_selector("audio", "medium")
        assert selector == "bestaudio[abr>=64][abr<128]"

    def test_audio_low_quality(self):
        """Test audio low quality format selector."""
        selector = UrlAudioDownloader._build_format_selector("audio", "low")
        assert selector == "worstaudio"

    def test_audio_with_format_preference(self):
        """Test audio with format preference."""
        selector = UrlAudioDownloader._build_format_selector(
            "audio", "best", prefer_format="mp3"
        )
        assert selector == "bestaudio[ext=mp3]/bestaudio"

    def test_video_best_quality(self):
        """Test video best quality format selector."""
        selector = UrlAudioDownloader._build_format_selector("video", "best")
        assert (
            selector == "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        )

    def test_video_high_quality(self):
        """Test video high quality format selector."""
        selector = UrlAudioDownloader._build_format_selector("video", "high")
        assert selector == "bestvideo[height<=1080]+bestaudio/best[height<=1080]"

    def test_video_medium_quality(self):
        """Test video medium quality format selector."""
        selector = UrlAudioDownloader._build_format_selector("video", "medium")
        assert selector == "bestvideo[height<=720]+bestaudio/best[height<=720]"

    def test_video_low_quality(self):
        """Test video low quality format selector."""
        selector = UrlAudioDownloader._build_format_selector("video", "low")
        assert selector == "worstvideo+worstaudio/worst"

    def test_video_with_format_preference(self):
        """Test video with format preference."""
        selector = UrlAudioDownloader._build_format_selector(
            "video", "best", prefer_format="webm"
        )
        expected = (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best[ext=webm]/"
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        )
        assert selector == expected


class TestDownloadAudioWithOptions:
    """Test download_audio with options."""

    @patch("flowscribe.input.url_downloader.validate_public_http_url")
    @patch("flowscribe.input.url_downloader.Path.mkdir")
    @patch("flowscribe.input.url_downloader.Path.exists")
    @patch("flowscribe.input.url_downloader.shutil.rmtree")
    def test_download_with_quality_option(
        self, mock_rmtree, mock_exists, mock_mkdir, mock_validate
    ):
        """Test download with quality option."""
        mock_exists.return_value = False

        downloader = UrlAudioDownloader(
            download_dir=Path("/tmp/test"),
            max_bytes=1024 * 1024 * 100,
            max_duration_seconds=3600,
            timeout_seconds=30,
        )

        opts = UrlDownloadOptions(quality="high", prefer_format="mp3")

        # Mock the actual download methods
        with patch.object(
            downloader, "_download_page_audio"
        ) as mock_download_page:
            mock_download_page.return_value = (
                Path("/tmp/test/audio.mp3"),
                Path("/tmp/test/audio.mp3"),
                "audio",
            )

            result = downloader.download_audio(
                "https://example.com/video", download_options=opts
            )

            assert result.path == Path("/tmp/test/audio.mp3")
            mock_download_page.assert_called_once()
            call_args = mock_download_page.call_args
            assert call_args.kwargs["download_options"] == opts

