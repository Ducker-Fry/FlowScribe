"""Tests for TranscriptionViewDialog workspace transcript loading."""

from unittest.mock import MagicMock, patch
import json
import pytest
import importlib
import importlib.util

# Skip all tests in this module if PySide6 is not available
try:
    importlib.util.find_spec("PySide6")
except ImportError:
    pytest.skip("PySide6 not available", allow_module_level=True)


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


def test_load_transcript_with_artifacts(qt_app, mock_transcript_data, tmp_path):
    """Test loading transcript with provided artifact paths."""
    from flowscribe.gui.dialogs.transcription_view_dialog import TranscriptionViewDialog

    # Create temporary transcript and artifact files
    transcript_file = tmp_path / "test_transcript.json"
    with open(transcript_file, 'w', encoding='utf-8') as f:
        json.dump(mock_transcript_data, f)

    txt_file = tmp_path / "test_transcript.txt"
    txt_file.write_text("Hello world\nThis is a test", encoding='utf-8')

    srt_file = tmp_path / "test_transcript.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:02,500\nHello world\n", encoding='utf-8')

    artifact_paths = (transcript_file, txt_file, srt_file)

    # Create dialog instance with mocked UI setup
    with patch.object(TranscriptionViewDialog, '_setup_ui'):
        dialog = TranscriptionViewDialog()
        dialog.transcript_summary = MagicMock()
        dialog.media_status_label = MagicMock()
        dialog.media_binding_label = MagicMock()
        dialog.open_media_button = MagicMock()
        dialog.search_button = MagicMock()
        dialog.search_input = MagicMock()
        dialog._populate_segments = MagicMock()
        dialog._load_artifacts = MagicMock()
        dialog._bind_media = MagicMock()

        # Mock the transcript loading functions
        with patch('flowscribe.gui.transcript_viewer.load_transcript_view') as mock_load_view, \
             patch('flowscribe.transcript.editing.load_editable_transcript') as mock_load_editable, \
             patch('flowscribe.gui.transcript_viewer.render_transcript_summary', return_value="<html>Summary</html>"), \
             patch('flowscribe.gui.transcript_viewer.resolve_transcript_media_path', return_value=None):

            mock_transcript_view = MagicMock()
            mock_load_view.return_value = mock_transcript_view
            mock_load_editable.return_value = MagicMock()

            # Call the method
            dialog._load_transcript_with_artifacts(transcript_file, artifact_paths)

            # Verify transcript was loaded
            mock_load_view.assert_called_once_with(transcript_file)
            mock_load_editable.assert_called_once_with(transcript_file)

            # Verify artifacts were loaded with provided paths (not discovered)
            dialog._load_artifacts.assert_called_once_with(artifact_paths)

            # Verify UI was updated
            dialog.transcript_summary.setHtml.assert_called_once_with("<html>Summary</html>")
            dialog._populate_segments.assert_called_once()

            # Verify controls were enabled
            dialog.open_media_button.setEnabled.assert_called_once_with(True)
            dialog.search_button.setEnabled.assert_called_once_with(True)
            dialog.search_input.setEnabled.assert_called_once_with(True)

