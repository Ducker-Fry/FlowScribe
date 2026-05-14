"""Run the FlowScribe desktop GUI."""

from __future__ import annotations

import sys

from flowscribe.gui.qt_app import run_gui


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in args:
        return 0
    return run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
