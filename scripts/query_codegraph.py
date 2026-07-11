"""Query the workspace-local codegraph artifacts for FlowScribe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_INDEX_PATH = Path(".codex") / "codegraph" / "index.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query the FlowScribe codegraph index.")
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX_PATH,
        help="Path to the generated codegraph index.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search symbols by name or qualname.")
    search_parser.add_argument("term")
    search_parser.add_argument("--type", dest="symbol_type")
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.add_argument("--json", action="store_true")

    show_parser = subparsers.add_parser("show", help="Show one symbol and its immediate edges.")
    show_parser.add_argument("qualname")
    show_parser.add_argument("--json", action="store_true")

    neighbors_parser = subparsers.add_parser("neighbors", help="Show inbound/outbound edges.")
    neighbors_parser.add_argument("qualname")
    neighbors_parser.add_argument("--direction", choices=("in", "out", "both"), default="both")
    neighbors_parser.add_argument("--kind")
    neighbors_parser.add_argument("--limit", type=int, default=40)
    neighbors_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    index = _load_index(args.index)

    if args.command == "search":
        return _handle_search(index, args.term, args.symbol_type, args.limit, args.json)
    if args.command == "show":
        return _handle_show(index, args.qualname, args.json)
    return _handle_neighbors(index, args.qualname, args.direction, args.kind, args.limit, args.json)


def _load_index(index_path: Path) -> dict[str, Any]:
    resolved = index_path.resolve()
    if not resolved.exists():
        raise SystemExit(
            f"Codegraph index not found: {resolved}\n"
            "Run `python scripts/build_codegraph.py` first."
        )
    return json.loads(resolved.read_text(encoding="utf-8"))


def _handle_search(
    index: dict[str, Any],
    term: str,
    symbol_type: str | None,
    limit: int,
    as_json: bool,
) -> int:
    lowered = term.lower()
    matches = []
    for symbol in index["symbols"]:
        if symbol_type and symbol["symbol_type"] != symbol_type:
            continue
        haystack = " ".join(
            [
                symbol["name"],
                symbol["qualname"],
                symbol["module"],
                symbol["file"],
                symbol.get("doc", ""),
            ]
        ).lower()
        if lowered in haystack:
            matches.append(symbol)

    matches.sort(key=lambda item: (item["symbol_type"], item["qualname"]))
    matches = matches[:limit]
    if as_json:
        print(json.dumps(matches, ensure_ascii=False, indent=2))
        return 0

    if not matches:
        print("No symbols matched.")
        return 1

    for symbol in matches:
        print(
            f"[{symbol['symbol_type']}] {symbol['qualname']} "
            f"({symbol['file']}:{symbol['line_start']})"
        )
        if symbol.get("doc"):
            print(f"  {symbol['doc']}")
    return 0


def _handle_show(index: dict[str, Any], qualname: str, as_json: bool) -> int:
    symbol = _resolve_symbol(index["symbols"], qualname)
    if symbol is None:
        print(f"Symbol not found: {qualname}")
        return 1

    inbound, outbound = _partition_edges(index["edges"], symbol["qualname"])
    payload = {
        "symbol": symbol,
        "inbound_edges": inbound,
        "outbound_edges": outbound,
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"{symbol['qualname']} [{symbol['symbol_type']}]")
    print(f"File: {symbol['file']}:{symbol['line_start']}-{symbol['line_end']}")
    print(f"Module: {symbol['module']}")
    if symbol.get("parent"):
        print(f"Parent: {symbol['parent']}")
    if symbol.get("bases"):
        print(f"Bases: {', '.join(symbol['bases'])}")
    if symbol.get("args"):
        print(f"Args: {', '.join(symbol['args'])}")
    if symbol.get("doc"):
        print(f"Doc: {symbol['doc']}")
    print("Outbound:")
    for edge in outbound[:20]:
        print(f"  - {edge['kind']} -> {edge['target']}")
    print("Inbound:")
    for edge in inbound[:20]:
        print(f"  - {edge['kind']} <- {edge['source']}")
    return 0


def _handle_neighbors(
    index: dict[str, Any],
    qualname: str,
    direction: str,
    kind: str | None,
    limit: int,
    as_json: bool,
) -> int:
    symbol = _resolve_symbol(index["symbols"], qualname)
    if symbol is None:
        print(f"Symbol not found: {qualname}")
        return 1

    inbound, outbound = _partition_edges(index["edges"], symbol["qualname"], kind=kind)
    if direction == "in":
        payload: Any = inbound[:limit]
    elif direction == "out":
        payload = outbound[:limit]
    else:
        payload = {
            "inbound": inbound[:limit],
            "outbound": outbound[:limit],
        }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if direction in {"out", "both"}:
        print("Outbound:")
        for edge in outbound[:limit]:
            print(f"  - {edge['kind']} -> {edge['target']}")
    if direction in {"in", "both"}:
        print("Inbound:")
        for edge in inbound[:limit]:
            print(f"  - {edge['kind']} <- {edge['source']}")
    return 0


def _resolve_symbol(symbols: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    for symbol in symbols:
        if symbol["qualname"] == query:
            return symbol

    exact_name_matches = [symbol for symbol in symbols if symbol["name"] == query]
    if len(exact_name_matches) == 1:
        return exact_name_matches[0]
    return None


def _partition_edges(
    edges: list[dict[str, Any]],
    qualname: str,
    *,
    kind: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inbound = []
    outbound = []
    for edge in edges:
        if kind and edge["kind"] != kind:
            continue
        if edge["target"] == qualname:
            inbound.append(edge)
        if edge["source"] == qualname:
            outbound.append(edge)
    return inbound, outbound


if __name__ == "__main__":
    raise SystemExit(main())

