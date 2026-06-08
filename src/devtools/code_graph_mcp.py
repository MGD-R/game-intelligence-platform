"""Minimal stdio MCP server for project code graph access."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.devtools.code_graph import (
    DEFAULT_EXCLUDES,
    CodeGraph,
    build_code_graph,
    iter_python_files,
    snapshot_mtimes,
)


class CodeGraphStore:
    def __init__(self, *, root: Path, includes: tuple[str, ...], interval_seconds: float) -> None:
        self.root = root
        self.includes = includes
        self.interval_seconds = interval_seconds
        self._lock = threading.Lock()
        self._graph: CodeGraph | None = None
        self._mtimes: dict[str, int] = {}
        self._last_refresh_reason = "initial"

    def refresh(self, *, reason: str = "manual") -> CodeGraph:
        graph = build_code_graph(root=self.root, includes=self.includes)
        files = iter_python_files(self.root, self.includes, excludes=set(DEFAULT_EXCLUDES))
        with self._lock:
            self._graph = graph
            self._mtimes = snapshot_mtimes(files)
            self._last_refresh_reason = reason
        return graph

    def current_graph(self) -> CodeGraph:
        with self._lock:
            graph = self._graph
        if graph is None:
            return self.refresh(reason="initial")
        return graph

    def watch_forever(self) -> None:
        while True:
            files = iter_python_files(self.root, self.includes, excludes=set(DEFAULT_EXCLUDES))
            current = snapshot_mtimes(files)
            with self._lock:
                changed = current != self._mtimes
            if changed:
                self.refresh(reason="file_change")
            time.sleep(self.interval_seconds)

    def status(self) -> dict[str, Any]:
        graph = self.current_graph()
        with self._lock:
            reason = self._last_refresh_reason
        return {
            "root": str(self.root),
            "includes": list(self.includes),
            "generated_at": graph.generated_at,
            "file_count": graph.file_count,
            "symbol_count": graph.symbol_count,
            "edge_count": graph.edge_count,
            "last_refresh_reason": reason,
        }


def json_rpc_result(request_id: object, result: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def json_rpc_error(request_id: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def mcp_text(content: object) -> dict[str, object]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True),
            }
        ]
    }


def tool_definitions() -> list[dict[str, object]]:
    return [
        {
            "name": "get_code_graph",
            "description": "Return the current Python function/class hierarchy graph.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "module_prefix": {"type": "string"},
                    "kind": {"type": "string"},
                },
            },
        },
        {
            "name": "list_symbols",
            "description": "List symbols with optional module/name/kind filters.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "module_prefix": {"type": "string"},
                    "name_contains": {"type": "string"},
                    "kind": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                },
            },
        },
        {
            "name": "get_symbol",
            "description": "Return one symbol and its direct children by symbol id.",
            "inputSchema": {
                "type": "object",
                "properties": {"symbol_id": {"type": "string"}},
                "required": ["symbol_id"],
            },
        },
        {
            "name": "refresh_code_graph",
            "description": "Force a code graph rebuild.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "watch_status",
            "description": "Return watch status and current graph counters.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def filter_nodes(
    nodes: list[dict[str, Any]],
    *,
    module_prefix: str | None = None,
    kind: str | None = None,
    name_contains: str | None = None,
) -> list[dict[str, Any]]:
    filtered = nodes
    if module_prefix:
        filtered = [node for node in filtered if str(node["module"]).startswith(module_prefix)]
    if kind:
        filtered = [node for node in filtered if node["kind"] == kind]
    if name_contains:
        needle = name_contains.lower()
        filtered = [node for node in filtered if needle in str(node["qualname"]).lower()]
    return filtered


def call_tool(store: CodeGraphStore, name: str, arguments: dict[str, Any]) -> dict[str, object]:
    graph = store.current_graph()
    if name == "get_code_graph":
        nodes = filter_nodes(
            graph.nodes,
            module_prefix=arguments.get("module_prefix"),
            kind=arguments.get("kind"),
        )
        node_ids = {node["id"] for node in nodes}
        edges = [
            edge
            for edge in graph.edges
            if edge["source"] in node_ids and edge["target"] in node_ids
        ]
        return mcp_text({**asdict(graph), "nodes": nodes, "edges": edges})
    if name == "list_symbols":
        limit = int(arguments.get("limit") or 200)
        nodes = filter_nodes(
            graph.nodes,
            module_prefix=arguments.get("module_prefix"),
            kind=arguments.get("kind"),
            name_contains=arguments.get("name_contains"),
        )
        return mcp_text({"symbols": nodes[:limit], "total": len(nodes)})
    if name == "get_symbol":
        symbol_id = str(arguments["symbol_id"])
        node = next((item for item in graph.nodes if item["id"] == symbol_id), None)
        if node is None:
            return mcp_text({"error": f"symbol not found: {symbol_id}"})
        child_ids = {
            edge["target"]
            for edge in graph.edges
            if edge["source"] == symbol_id and edge["kind"] == "contains"
        }
        children = [item for item in graph.nodes if item["id"] in child_ids]
        return mcp_text({"symbol": node, "children": children})
    if name == "refresh_code_graph":
        refreshed = store.refresh(reason="manual")
        return mcp_text(store.status() | {"generated_at": refreshed.generated_at})
    if name == "watch_status":
        return mcp_text(store.status())
    return mcp_text({"error": f"unknown tool: {name}"})


def handle_request(store: CodeGraphStore, request: dict[str, Any]) -> dict[str, object] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        return json_rpc_result(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "game-intelligence-code-graph", "version": "0.1.0"},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return json_rpc_result(request_id, {"tools": tool_definitions()})
    if method == "tools/call":
        params = request.get("params") or {}
        name = str(params.get("name"))
        arguments = params.get("arguments") or {}
        return json_rpc_result(request_id, call_tool(store, name, arguments))
    return json_rpc_error(request_id, -32601, f"method not found: {method}")


def serve_stdio(store: CodeGraphStore) -> None:
    store.refresh(reason="startup")
    watcher = threading.Thread(target=store.watch_forever, daemon=True)
    watcher.start()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_request(store, request)
        except Exception as exc:
            response = json_rpc_error(None, -32603, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the code graph MCP stdio server.")
    parser.add_argument("--root", default=".", help="Project root.")
    parser.add_argument(
        "--include",
        action="append",
        default=None,
        help="Directory or file to include. Can be repeated. Defaults to src.",
    )
    parser.add_argument("--interval", type=float, default=2.0, help="Watch polling interval.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = CodeGraphStore(
        root=Path(args.root).resolve(),
        includes=tuple(args.include or ["src"]),
        interval_seconds=args.interval,
    )
    serve_stdio(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
