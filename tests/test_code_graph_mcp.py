from __future__ import annotations

from pathlib import Path

from src.devtools.code_graph_mcp import CodeGraphStore, call_tool, handle_request


def test_mcp_lists_symbols(tmp_path) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "module.py").write_text(
        "class Service:\n    def handle(self):\n        return None\n",
        encoding="utf-8",
    )
    store = CodeGraphStore(root=tmp_path, includes=("src",), interval_seconds=10.0)
    store.refresh(reason="test")

    result = call_tool(store, "list_symbols", {"name_contains": "Service"})
    text = result["content"][0]["text"]

    assert "Service" in str(text)


def test_mcp_initialize_and_tools_list() -> None:
    store = CodeGraphStore(root=Path("."), includes=("src",), interval_seconds=10.0)

    init_response = handle_request(store, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    tools_response = handle_request(store, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    assert init_response is not None
    assert init_response["result"]["serverInfo"]["name"] == "game-intelligence-code-graph"
    assert tools_response is not None
    assert tools_response["result"]["tools"]
