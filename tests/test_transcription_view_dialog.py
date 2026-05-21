"""Tests for TranscriptionViewDialog workspace transcript loading."""

from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import json
import pytest


@pytest.fixture
def mock_transcript_data():
    """Create mock transcript JSON data."""
    return {
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 2.5,
                "text": "Hello world"
            },
            {
                "id": 1,
                "start": 2.5,
                "end": 5.0,
                "text": "This is a test"
            }
        ],
        "language": "en",
        "duration": 5.0
    }


@pytest.fixture
def qt_app():
    """Create a real Qt application for testing."""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    yield app

    # Cleanup is handled by pytest-qt or manual cleanup if needed


def test_open_transcript_file_valid_json(qt_app, mock_transcript_data, tmp_path):
    """Test opening a valid transcript JSON file."""
    from flowscribe.gui.dialogs.transcription_view_dialog import TranscriptionViewDialog

    # Create a temporary transcript file
    transcript_file = tmp_path / "test_transcript.json"
    with open(transcript_file, 'w', encoding='utf-8') as f:
        json.dump(mock_transcript_data, f)

    # Create dialog instance with mocked UI setup
    with patch.object(TranscriptionViewDialog, '_setup_ui'):
        dialog = TranscriptionViewDialog()
        dialog.artifact_status_label = MagicMock()
        dialog._load_transcript = MagicMock()

        # Mock QFileDialog to return our test file
        with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(str(transcript_file), "")):
            dialog._open_transcript_file()

        # Verify _load_transcript was called with the correct path
        dialog._load_transcript.assert_called_once()
        call_args = dialog._load_transcript.call_args[0]
        assert call_args[0] == transcript_file

        # Verify status message
        dialog.artifact_status_label.setText.assert_called_with(f"Loaded transcript: {transcript_file.name}")


def test_open_transcript_file_invalid_json(qt_app, tmp_path):
    """Test opening an invalid transcript JSON file (missing segments)."""
    from flowscribe.gui.dialogs.transcription_view_dialog import TranscriptionViewDialog

    # Create a temporary invalid transcript file
    transcript_file = tmp_path / "invalid_transcript.json"
    with open(transcript_file, 'w', encoding='utf-8') as f:
        json.dump({"language": "en"}, f)  # Missing 'segments' key

    # Create dialog instance with mocked UI setup
    with patch.object(TranscriptionViewDialog, '_setup_ui'):
        dialog = TranscriptionViewDialog()
        dialog.artifact_status_label = MagicMock()
        dialog._load_transcript = MagicMock()

        # Mock QFileDialog to return our test file
        with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(str(transcript_file), "")):
            dialog._open_transcript_file()

        # Verify _load_transcript was NOT called
        dialog._load_transcript.assert_not_called()

        # Verify error message
        dialog.artifact_status_label.setText.assert_called_with("Invalid transcript format - missing segments")


def test_open_transcript_file_cancelled(qt_app):
    """Test cancelling the file dialog."""
    from flowscribe.gui.dialogs.transcription_view_dialog import TranscriptionViewDialog

    # Create dialog instance with mocked UI setup
    with patch.object(TranscriptionViewDialog, '_setup_ui'):
        dialog = TranscriptionViewDialog()
        dialog.artifact_status_label = MagicMock()
        dialog._load_transcript = MagicMock()

        # Mock QFileDialog to return empty (cancelled)
        with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=("", "")):
            dialog._open_transcript_file()

        # Verify _load_transcript was NOT called
        dialog._load_transcript.assert_not_called()

        # Verify no status message was set
        dialog.artifact_status_label.setText.assert_not_called()


def test_open_transcript_file_read_error(qt_app, tmp_path):
    """Test handling file read errors."""
    from flowscribe.gui.dialogs.transcription_view_dialog import TranscriptionViewDialog

    # Create a file path that doesn't exist
    transcript_file = tmp_path / "nonexistent.json"

    # Create dialog instance with mocked UI setup
    with patch.object(TranscriptionViewDialog, '_setup_ui'):
        dialog = TranscriptionViewDialog()
        dialog.artifact_status_label = MagicMock()
        dialog._load_transcript = MagicMock()

        # Mock QFileDialog to return the nonexistent file
        with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(str(transcript_file), "")):
            dialog._open_transcript_file()

        # Verify _load_transcript was NOT called
        dialog._load_transcript.assert_not_called()

        # Verify error message contains "Error loading transcript"
        call_args = dialog.artifact_status_label.setText.call_args[0][0]
        assert "Error loading transcript" in call_args
