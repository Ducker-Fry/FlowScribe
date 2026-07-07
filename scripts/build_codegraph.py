"""Build the workspace-local codegraph artifacts for FlowScribe."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    from scripts.codegraph.indexer import write_index_artifacts

    index_path, summary_path, index = write_index_artifacts(REPO_ROOT)
    stats = index["stats"]
    print(f"Codegraph index written: {index_path}")
    print(f"Codegraph summary written: {summary_path}")
    print(
        "Indexed "
        f"{stats['file_count']} files, "
        f"{stats['symbol_count']} symbols, "
        f"{stats['edge_count']} edges."
    )
    if index["parse_errors"]:
        print(f"Parse errors: {len(index['parse_errors'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
