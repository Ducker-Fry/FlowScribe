"""Regression tests for custom queue item card rendering."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from flowscribe.tasks.models import SourceSpec
from flowscribe.gui.views.queue_view import QueueItemCard, QueueView
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings


def test_refresh_queue_uses_card_widget_without_duplicate_item_text():
    """The QListWidgetItem should not render its own text under the custom card."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    item = QueueItem(
        item_id="local-1",
        source=SourceSpec(kind="local", value=str(Path("samples") / "english_test.wav")),
        settings=QueueItemSettings(output_dir=Path("outputs")),
        status="pending",
    )

    view = QueueView({})
    view.refresh_queue([item])

    list_item = view._queue_list.item(0)
    card = view._queue_list.itemWidget(list_item)

    assert list_item is not None
    assert card is not None
    assert list_item.text() == ""
    assert "english_test.wav" in list_item.toolTip()


def test_card_checkbox_click_updates_backing_queue_item():
    """Clicking the visible checkbox should update queue selection state."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    item = QueueItem(
        item_id="local-2",
        source=SourceSpec(kind="local", value=str(Path("samples") / "chinese_test.wav")),
        settings=QueueItemSettings(output_dir=Path("outputs")),
        status="pending",
    )

    view = QueueView({})
    view.refresh_queue([item])
    view.show()

    list_item = view._queue_list.item(0)
    card = view._queue_list.itemWidget(list_item)

    assert isinstance(card, QueueItemCard)
    checkbox = card.findChild(QPushButton)
    assert checkbox is not None
    assert checkbox.property("queueCheck") is True

    QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton)

    assert "local-2" in view._checked_item_ids


def test_select_all_syncs_card_checkbox():
    """Select-all should update the visible checkbox state."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    item = QueueItem(
        item_id="local-3",
        source=SourceSpec(kind="local", value=str(Path("samples") / "english_test.wav")),
        settings=QueueItemSettings(output_dir=Path("outputs")),
        status="pending",
    )

    view = QueueView({})
    view.refresh_queue([item])

    list_item = view._queue_list.item(0)
    card = view._queue_list.itemWidget(list_item)

    assert isinstance(card, QueueItemCard)

    view._on_select_all()

    checkbox = card.findChild(QPushButton)
    assert checkbox is not None
    assert checkbox.isChecked()


def test_remove_button_emits_only_target_item_after_reorder():
    """Remove action should follow the visible row order without drag side effects."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    items = [
        QueueItem(
            item_id="item-a",
            source=SourceSpec(kind="local", value=str(Path("samples") / "a.wav")),
            settings=QueueItemSettings(output_dir=Path("outputs")),
            status="pending",
        ),
        QueueItem(
            item_id="item-b",
            source=SourceSpec(kind="local", value=str(Path("samples") / "b.wav")),
            settings=QueueItemSettings(output_dir=Path("outputs")),
            status="pending",
        ),
    ]

    view = QueueView({})
    view.refresh_queue(items)

    second_item = view._queue_list.item(1)
    assert second_item is not None
    card = view._queue_list.itemWidget(second_item)
    assert isinstance(card, QueueItemCard)
    moved_item = view._queue_list.takeItem(1)
    assert moved_item is second_item
    view._queue_list.insertItem(0, moved_item)
    view._queue_list.setItemWidget(moved_item, card)
    view._on_rows_moved(None, 1, 1, None, 0)

    emitted: list[list[str]] = []
    view.remove_items_requested.connect(lambda item_ids: emitted.append(item_ids))

    buttons = card.findChildren(QPushButton)
    remove_button = next(button for button in buttons if button.text() == "Remove")
    QTest.mouseClick(remove_button, Qt.MouseButton.LeftButton)

    assert emitted == [["item-b"]]
