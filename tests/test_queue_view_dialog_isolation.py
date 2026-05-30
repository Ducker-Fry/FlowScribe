"""Test that QueueView properly isolates TranscriptionViewDialog content per QueueItem."""

from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from PySide6.QtWidgets import QApplication
from flowscribe.gui.views.queue_view import QueueView
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings
from flowscribe.tasks.models import SourceSpec


@pytest.fixture
def qt_app():
    """Ensure QApplication exists for Qt widgets."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def queue_view(qt_app):
    """Create QueueView instance."""
    settings = {}  # Empty settings dict for testing
    view = QueueView(settings)
    yield view
    view.deleteLater()


def test_dialog_content_cleared_between_items(queue_view):
    """Test that dialog content is cleared when switching between queue items."""
    from unittest.mock import MagicMock

    mock_path1 = MagicMock(spec=Path)
    mock_path1.name = "transcript1.json"
    mock_path1.is_file.return_value = True

    mock_path2 = MagicMock(spec=Path)
    mock_path2.name = "transcript2.json"
    mock_path2.is_file.return_value = True

    item1 = QueueItem(
        item_id="item1",
        source=SourceSpec(kind="local", value="/test1.mp4"),
        settings=QueueItemSettings(),
        status="completed",
        transcript_path=mock_path1,
        run_detail="Run details for item 1"
    )

    item2 = QueueItem(
        item_id="item2",
        source=SourceSpec(kind="local", value="/test2.mp4"),
        settings=QueueItemSettings(),
        status="completed",
        transcript_path=mock_path2,
        run_detail="Run details for item 2"
    )

    mock_items = [item1, item2]

    # Populate queue with items
    queue_view.refresh_queue(mock_items)

    # Select first item by checking its checkbox
    queue_view._checked_item_ids.add("item1")
    queue_view._sync_all_card_check_states()

    # Mock the dialog creation and methods
    with patch.object(queue_view, '_create_view_dialog'):
        mock_dialog = Mock()
        mock_dialog.isVisible.return_value = False
        queue_view._view_dialog = mock_dialog

        # Open first item
        queue_view._on_open_view()

        # Verify clear_content was called
        assert mock_dialog.clear_content.called

        # Verify _load_transcript was called with first item's path
        mock_dialog._load_transcript.assert_called_once()
        first_call_path = mock_dialog._load_transcript.call_args[0][0]
        assert first_call_path == mock_items[0].transcript_path

        # Reset mock
        mock_dialog.reset_mock()

        # Select second item by checking its checkbox
        queue_view._checked_item_ids.discard("item1")
        queue_view._checked_item_ids.add("item2")
        queue_view._sync_all_card_check_states()

        # Open second item
        queue_view._on_open_view()

        # Verify clear_content was called again
        assert mock_dialog.clear_content.called

        # Verify _load_transcript was called with second item's path
        mock_dialog._load_transcript.assert_called_once()
        second_call_path = mock_dialog._load_transcript.call_args[0][0]
        assert second_call_path == mock_items[1].transcript_path

        # Verify paths are different
        assert first_call_path != second_call_path


def test_dialog_content_cleared_for_running_item(queue_view):
    """Test that dialog content is cleared when opening a running item."""
    # Create a running item
    running_item = QueueItem(
        item_id="running1",
        source=SourceSpec(kind="local", value="/test.mp4"),
        settings=QueueItemSettings(),
        status="running"
    )

    # Populate queue
    queue_view.refresh_queue([running_item])
    queue_view._current_running_item_id = "running1"
    queue_view._current_run_output = "Running transcription..."

    # Select the item by checking its checkbox
    queue_view._checked_item_ids.add("running1")
    queue_view._sync_all_card_check_states()

    # Mock the dialog
    mock_dialog = Mock()
    mock_dialog.isVisible.return_value = False
    queue_view._view_dialog = mock_dialog

    # Open the running item
    queue_view._on_open_view()

    # Verify clear_content was called before update_run_output
    assert mock_dialog.clear_content.called
    assert mock_dialog.update_run_output.called

    # Verify call order: clear_content should be called before update_run_output
    call_order = [call[0] for call in mock_dialog.method_calls]
    clear_index = call_order.index('clear_content')
    update_index = call_order.index('update_run_output')
    assert clear_index < update_index


def test_dialog_clear_content_resets_all_state(qt_app):
    """Test that clear_content method resets all dialog state."""
    from flowscribe.gui.dialogs import TranscriptionViewDialog

    # Create dialog
    dialog = TranscriptionViewDialog()

    # Set some state
    dialog._transcript_path = Path("/fake/path.json")
    dialog._transcript_view = Mock()
    dialog._editable_transcript = Mock()
    dialog._search_hits = (Mock(), Mock())
    dialog._workspace_artifact_paths = (Path("/fake/artifact.txt"),)
    dialog._last_chunk_index = 5
    dialog._current_segment_index = 3
    dialog._segment_modified = True
    dialog._active_segment_row = 2

    # Set some UI state
    dialog.preview_output.setPlainText("Some output")
    dialog.transcript_summary.setPlainText("Some summary")
    dialog.segment_editor.setPlainText("Some text")
    dialog.segment_editor.setEnabled(True)

    # Call clear_content
    dialog.clear_content()

    # Verify all state is cleared
    assert dialog._transcript_path is None
    assert dialog._transcript_view is None
    assert dialog._editable_transcript is None
    assert dialog._search_hits == ()
    assert dialog._workspace_artifact_paths == ()
    assert dialog._last_chunk_index == 0
    assert dialog._current_segment_index == -1
    assert dialog._segment_modified is False
    assert dialog._active_segment_row == -1

    # Verify UI is cleared
    assert dialog.preview_output.toPlainText() == ""
    assert dialog.transcript_segments.count() == 0
    assert dialog.segment_editor.toPlainText() == ""
    assert not dialog.segment_editor.isEnabled()
    assert dialog.search_results.count() == 0
    assert dialog.artifact_selector.count() == 0

    # Verify controls are disabled
    assert not dialog.open_media_button.isEnabled()
    assert not dialog.play_media_button.isEnabled()
    assert not dialog.media_position_slider.isEnabled()
    assert not dialog.search_button.isEnabled()
    assert not dialog.search_input.isEnabled()
    assert not dialog.segment_revert_button.isEnabled()
    assert not dialog.save_transcript_button.isEnabled()
    assert not dialog.save_transcript_copy_button.isEnabled()
    assert not dialog.reexport_transcript_button.isEnabled()

    # Clean up
    dialog.deleteLater()
