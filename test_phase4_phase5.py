"""Test script for Phase 4 & 5 - Complete new architecture."""

import sys

from PySide6.QtWidgets import QApplication

from flowscribe.gui.new_main_window import NewMainWindow


def main():
    """Run test application with new architecture."""
    app = QApplication(sys.argv)
    window = NewMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
