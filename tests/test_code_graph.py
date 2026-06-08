from __future__ import annotations

import json

from src.devtools.code_graph import build_code_graph, graph_to_json


def test_code_graph_extracts_classes_functions_and_methods(tmp_path) -> None:
    package = tmp_path / "src" / "sample"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "module.py").write_text(
        '''
class Example:
    """Example docs."""

    def method(self, value: int) -> str:
        return str(value)


def top_level(name: str) -> str:
    return name
''',
        encoding="utf-8",
    )

    graph = build_code_graph(root=tmp_path, includes=["src"])
    ids = {node["id"] for node in graph.nodes}

    assert "src.sample.module:Example" in ids
    assert "src.sample.module:Example.method" in ids
    assert "src.sample.module:top_level" in ids
    assert {
        "source": "src.sample.module:Example",
        "target": "src.sample.module:Example.method",
        "kind": "contains",
    } in graph.edges


def test_code_graph_json_is_serializable(tmp_path) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "app.py").write_text("def run() -> None:\n    return None\n", encoding="utf-8")

    graph = build_code_graph(root=tmp_path, includes=["src"])
    payload = json.loads(graph_to_json(graph))

    assert payload["symbol_count"] == 1
    assert payload["nodes"][0]["qualname"] == "run"
