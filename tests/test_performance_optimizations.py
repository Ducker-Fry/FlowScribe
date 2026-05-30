"""Tests for performance optimizations: dynamic workers and speed preset."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flowscribe.config.settings import AppSettings
from flowscribe.core.models import PreparedAudio
from flowscribe.core.progressive.executor import ProgressiveTranscriptionExecutor
from flowscribe.transcription.local_whisper import LocalWhisperTranscriber


class TestDynamicWorkerCalculation:
    """Test dynamic worker calculation based on available memory."""

    def test_resolve_max_workers_respects_cpu_count(self):
        """Test that worker count respects CPU count."""
        transcriber = MagicMock()
        transcriber.fork_for_worker = MagicMock()
        transcriber._model_name = "small"

        executor = ProgressiveTranscriptionExecutor(transcriber=transcriber)

        # Mock psutil at import time
        mock_psutil = MagicMock()
        mock_psutil.virtual_memory.return_value.available = 16 * 1024 ** 3

        with patch("os.cpu_count", return_value=4):
            with patch.dict("sys.modules", {"psutil": mock_psutil}):
                result = executor._resolve_max_workers(max_workers=20)
                # Should be capped by CPU count (4)
                assert result == 4

    def test_resolve_max_workers_respects_memory_limit(self):
        """Test that worker count respects memory limit."""
        transcriber = MagicMock()
        transcriber.fork_for_worker = MagicMock()
        transcriber._model_name = "large-v3"  # ~2.5GB per worker

        executor = ProgressiveTranscriptionExecutor(transcriber=transcriber)

        # Mock psutil at import time
        mock_psutil = MagicMock()
        mock_psutil.virtual_memory.return_value.available = 8 * 1024 ** 3

        with patch("os.cpu_count", return_value=16):
            with patch.dict("sys.modules", {"psutil": mock_psutil}):
                result = executor._resolve_max_workers(max_workers=16)
                # Should be capped by memory (2-3 workers)
                assert result <= 3

    def test_resolve_max_workers_without_psutil(self):
        """Test fallback when psutil not available."""
        transcriber = MagicMock()
        transcriber.fork_for_worker = MagicMock()
        transcriber._model_name = "small"

        executor = ProgressiveTranscriptionExecutor(transcriber=transcriber)

        with patch("os.cpu_count", return_value=8):
            # Simulate ImportError when trying to import psutil
            with patch.dict("sys.modules", {"psutil": None}):
                result = executor._resolve_max_workers(max_workers=8)
                # Should use conservative default (2)
                assert result == 2

    def test_resolve_max_workers_without_fork_support(self):
        """Test that worker count is 1 when transcriber doesn't support forking."""
        transcriber = MagicMock()
        # No fork_for_worker method
        delattr(transcriber, "fork_for_worker")

        executor = ProgressiveTranscriptionExecutor(transcriber=transcriber)

        with patch("os.cpu_count", return_value=8):
            result = executor._resolve_max_workers(max_workers=8)
            assert result == 1

    def test_estimate_model_memory(self):
        """Test model memory estimation."""
        transcriber = MagicMock()
        transcriber.fork_for_worker = MagicMock()

        executor = ProgressiveTranscriptionExecutor(transcriber=transcriber)

        # Test known models
        assert executor._estimate_model_memory("tiny") == 0.5
        assert executor._estimate_model_memory("small") == 1.0
        assert executor._estimate_model_memory("medium") == 1.5
        assert executor._estimate_model_memory("large-v3") == 2.5

        # Test unknown model (should use default)
        assert executor._estimate_model_memory("unknown") == 1.5


class TestSpeedPreset:
    """Test speed preset functionality."""

    def test_speed_preset_applies_beam_size(self):
        """Test that speed preset sets beam_size=1."""
        settings = AppSettings.from_options(
            output_dir=Path("outputs"),
            work_dir=None,
            model_name="small",
            language=None,
            preset="speed",
            task="transcribe",
            beam_size=5,  # Default
            vad_filter=False,
            no_vad_filter=False,
            initial_prompt=None,
            word_timestamps=False,
            recursive=False,
            overwrite=False,
            keep_audio=False,
        )
        assert settings.beam_size == 1

    def test_speed_preset_enables_vad_filter(self):
        """Test that speed preset enables VAD filter."""
        settings = AppSettings.from_options(
            output_dir=Path("outputs"),
            work_dir=None,
            model_name="small",
            language=None,
            preset="speed",
            task="transcribe",
            beam_size=5,
            vad_filter=False,  # Default
            no_vad_filter=False,
            initial_prompt=None,
            word_timestamps=False,
            recursive=False,
            overwrite=False,
            keep_audio=False,
        )
        assert settings.vad_filter is True

    def test_quality_preset_applies_settings(self):
        """Test that quality preset sets beam_size=5 and vad_filter=False."""
        settings = AppSettings.from_options(
            output_dir=Path("outputs"),
            work_dir=None,
            model_name="small",
            language=None,
            preset="quality",
            task="transcribe",
            beam_size=1,  # Override
            vad_filter=True,  # Override
            no_vad_filter=False,
            initial_prompt=None,
            word_timestamps=False,
            recursive=False,
            overwrite=False,
            keep_audio=False,
        )
        assert settings.beam_size == 5
        assert settings.vad_filter is False

    def test_speed_preset_compute_type_int8(self):
        """Test that speed preset forces int8 compute type."""
        transcriber = LocalWhisperTranscriber(
            model_name="small",
            preset="speed",
        )

        with patch("faster_whisper.WhisperModel") as mock_model:
            transcriber._load_model()

            # Verify WhisperModel called with int8
            mock_model.assert_called_once()
            call_kwargs = mock_model.call_args[1]
            assert call_kwargs["compute_type"] == "int8"
            assert call_kwargs["device"] == "cpu"

    def test_no_preset_uses_auto_detection(self):
        """Test that without preset, auto-detection is used."""
        transcriber = LocalWhisperTranscriber(
            model_name="small",
            preset=None,
        )

        with patch("faster_whisper.WhisperModel") as mock_model:
            with patch("ctranslate2.get_cuda_device_count", return_value=0):
                transcriber._load_model()

                # Verify auto-detection logic
                call_kwargs = mock_model.call_args[1]
                assert call_kwargs["device"] == "cpu"
                assert call_kwargs["compute_type"] == "int8"

    def test_zh_preset_unchanged(self):
        """Test that zh preset still works as before."""
        settings = AppSettings.from_options(
            output_dir=Path("outputs"),
            work_dir=None,
            model_name="small",
            language=None,
            preset="zh",
            task="transcribe",
            beam_size=5,
            vad_filter=False,
            no_vad_filter=False,
            initial_prompt=None,
            word_timestamps=False,
            recursive=False,
            overwrite=False,
            keep_audio=False,
        )
        assert settings.language == "zh"
        assert settings.initial_prompt is not None
        # zh preset doesn't change beam_size or vad_filter
        assert settings.beam_size == 5
        assert settings.vad_filter is False
