"""Test TranscriptionViewDialog."""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from flowscribe.gui.dialogs import TranscriptionViewDialog

app = QApplication(sys.argv)

# Test with a sample transcript path (will fail gracefully if not exists)
test_path = Path("outputs/test.json")
dialog = TranscriptionViewDialog(
    None,
    transcript_path=test_path if test_path.exists() else None,
    run_output="Test run output\nLine 2\nLine 3"
)

dialog.show()
print("Dialog created successfully")
sys.exit(app.exec())
