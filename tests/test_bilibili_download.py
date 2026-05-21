"""Test Bilibili video download issue."""

import warnings
from unittest.mock import Mock, patch


from flowscribe.input.url_downloader import UrlAudioDownloader


def test_bilibili_url_format():
    """Test that Bilibili URL passes validation."""
    from flowscribe.input.url_security import validate_public_http_url

    url = "https://www.bilibili.com/video/BV1kPQjBLE1q/"
    # Should not raise
    validate_public_http_url(url)


def test_video_download_failure_emits_warning(tmp_path):
    """
    Test that video download failure emits a warning instead of failing silently.
    """
    url = "https://www.bilibili.com/video/BV1kPQjBLE1q/"

    downloader = UrlAudioDownloader(
        download_dir=tmp_path,
        max_bytes=500 * 1024 * 1024,
        max_duration_seconds=3600,
        timeout_seconds=60,
    )

    # Mock yt-dlp at the correct import location
    with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        # Mock extract_info to return video info
        mock_ydl.extract_info.return_value = {
            "duration": 300,
            "formats": [
                {
                    "url": "https://example.com/audio.m4a",
                    "acodec": "aac",
                    "vcodec": "none",
                },
            ],
        }

        # Mock audio download to succeed
        def mock_audio_download(urls):
            item_dir = tmp_path / downloader._safe_id(url)
            item_dir.mkdir(parents=True, exist_ok=True)
            audio_file = item_dir / "remote-audio.m4a"
            audio_file.write_bytes(b"fake audio data")

        # Mock video download to fail
        from yt_dlp.utils import DownloadError as YtDlpDownloadError

        def mock_video_download(urls):
            # First call is for audio (succeeds)
            if mock_ydl.download.call_count == 1:
                mock_audio_download(urls)
            # Second call is for video (fails)
            else:
                raise YtDlpDownloadError("Video format not available")

        mock_ydl.download.side_effect = mock_video_download

        # Mock ffprobe
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="300.0\n", stderr="", returncode=0)

            # Capture warnings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")

                # Test download with video preservation
                result = downloader.download_audio(url, saved_media_kind="video")

                # Audio should be downloaded successfully
                assert result.path.exists()

                # Video download should have failed with a warning
                assert len(w) >= 1
                warning_messages = [str(warning.message) for warning in w]
                assert any("Failed to download video file" in msg for msg in warning_messages)

                # saved_media_kind should fall back to "audio"
                assert result.saved_media_kind == "audio"


def test_video_download_success(tmp_path):
    """
    Test successful video download.
    """
    url = "https://www.bilibili.com/video/BV1kPQjBLE1q/"

    downloader = UrlAudioDownloader(
        download_dir=tmp_path,
        max_bytes=500 * 1024 * 1024,
        max_duration_seconds=3600,
        timeout_seconds=60,
    )

    with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        mock_ydl.extract_info.return_value = {
            "duration": 300,
            "formats": [
                {
                    "url": "https://example.com/audio.m4a",
                    "acodec": "aac",
                    "vcodec": "none",
                },
            ],
        }

        def mock_download(urls):
            item_dir = tmp_path / downloader._safe_id(url)
            item_dir.mkdir(parents=True, exist_ok=True)

            # Create audio file on first call
            if mock_ydl.download.call_count == 1:
                audio_file = item_dir / "remote-audio.m4a"
                audio_file.write_bytes(b"fake audio data")
            # Create video file on second call
            else:
                video_file = item_dir / "remote-media.mp4"
                video_file.write_bytes(b"fake video data")

        mock_ydl.download.side_effect = mock_download

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="300.0\n", stderr="", returncode=0)

            # Test download with video preservation
            result = downloader.download_audio(url, saved_media_kind="video")

            # Both audio and video should be downloaded
            assert result.path.exists()
            assert result.saved_media_path is not None
            assert result.saved_media_path.exists()
            assert result.saved_media_kind == "video"


def test_ffmpeg_video_copy_failure_emits_warning(tmp_path):
    """
    Test that ffmpeg video copy failure emits a warning.
    """
    url = "https://example.com/video.mp4"

    downloader = UrlAudioDownloader(
        download_dir=tmp_path,
        max_bytes=500 * 1024 * 1024,
        max_duration_seconds=3600,
        timeout_seconds=60,
    )

    # Mock subprocess to fail for video copy but succeed for audio extraction
    with patch("subprocess.run") as mock_run:
        def mock_subprocess(command, **kwargs):
            # Check if this is video copy (has "-c copy")
            if "-c" in command and "copy" in command:
                from subprocess import CalledProcessError

                raise CalledProcessError(1, command, stderr="Video copy failed")
            # Audio extraction succeeds
            else:
                # Create audio file
                item_dir = tmp_path / downloader._safe_id(url)
                item_dir.mkdir(parents=True, exist_ok=True)
                audio_file = item_dir / "remote-audio.m4a"
                audio_file.write_bytes(b"fake audio data")
                return Mock(stdout="300.0\n", stderr="", returncode=0)

        mock_run.side_effect = mock_subprocess

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Test download with video preservation
            result = downloader.download_audio(url, saved_media_kind="video")

            # Audio should be downloaded
            assert result.path.exists()

            # Video copy should have failed with a warning
            assert len(w) >= 1
            warning_messages = [str(warning.message) for warning in w]
            assert any("Failed to copy video file" in msg for msg in warning_messages)
