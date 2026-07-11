"""Run the FlowScribe desktop GUI."""

from __future__ import annotations

import os
import sys

from flowscribe.gui.qt_app import run_gui


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in args:
        args = [arg for arg in args if arg != "--self-test"]
        os.environ.setdefault("FLOWSCRIBE_GUI_AUTOCLOSE_MS", "300")
    return run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
