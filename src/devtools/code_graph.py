"""Build and optionally watch a Python code graph for the project."""

from __future__ import annotations

import argparse
import ast
import json
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_EXCLUDES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "data",
    "data_packs",
    "mlruns",
}


@dataclass(frozen=True, slots=True)
class CodeSymbol:
    id: str
    name: str
    qualname: str
    kind: str
    module: str
    path: str
    line: int
    end_line: int | None
    parent_id: str | None = None
    docstring: str | None = None
    decorators: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    returns: str | None = None


@dataclass(frozen=True, slots=True)
class CodeEdge:
    source: str
    target: str
    kind: str


@dataclass(frozen=True, slots=True)
class CodeGraph:
    root: str
    generated_at: float
    file_count: int
    symbol_count: int
    edge_count: int
    nodes: list[dict[str, Any]]
    edges: list[dict[str, str]]


def module_name_for_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    return ".".join(part for part in relative.parts if part != "__init__")


def expression_to_string(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def argument_names(args: ast.arguments) -> list[str]:
    names = [arg.arg for arg in args.posonlyargs]
    names.extend(arg.arg for arg in args.args)
    if args.vararg is not None:
        names.append(f"*{args.vararg.arg}")
    names.extend(arg.arg for arg in args.kwonlyargs)
    if args.kwarg is not None:
        names.append(f"**{args.kwarg.arg}")
    return names


class SymbolVisitor(ast.NodeVisitor):
    def __init__(self, *, root: Path, path: Path, module: str) -> None:
        self.root = root
        self.path = path
        self.module = module
        self.nodes: list[CodeSymbol] = []
        self.edges: list[CodeEdge] = []
        self.stack: list[CodeSymbol] = []

    def symbol_id(self, qualname: str) -> str:
        return f"{self.module}:{qualname}"

    def parent(self) -> CodeSymbol | None:
        return self.stack[-1] if self.stack else None

    def add_symbol(self, symbol: CodeSymbol) -> None:
        self.nodes.append(symbol)
        parent = self.parent()
        if parent is not None:
            self.edges.append(CodeEdge(source=parent.id, target=symbol.id, kind="contains"))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        parent_qualname = self.parent().qualname if self.parent() is not None else ""
        qualname = f"{parent_qualname}.{node.name}" if parent_qualname else node.name
        symbol = CodeSymbol(
            id=self.symbol_id(qualname),
            name=node.name,
            qualname=qualname,
            kind="class",
            module=self.module,
            path=str(self.path.relative_to(self.root)),
            line=node.lineno,
            end_line=getattr(node, "end_lineno", None),
            parent_id=self.parent().id if self.parent() is not None else None,
            docstring=ast.get_docstring(node),
            decorators=[
                value
                for value in (expression_to_string(decorator) for decorator in node.decorator_list)
                if value
            ],
            bases=[value for value in (expression_to_string(base) for base in node.bases) if value],
        )
        self.add_symbol(symbol)
        self.stack.append(symbol)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, kind="method" if self.parent_kind() == "class" else "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        kind = "async_method" if self.parent_kind() == "class" else "async_function"
        self._visit_function(node, kind=kind)

    def parent_kind(self) -> str | None:
        parent = self.parent()
        return parent.kind if parent is not None else None

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, kind: str) -> None:
        parent_qualname = self.parent().qualname if self.parent() is not None else ""
        qualname = f"{parent_qualname}.{node.name}" if parent_qualname else node.name
        symbol = CodeSymbol(
            id=self.symbol_id(qualname),
            name=node.name,
            qualname=qualname,
            kind=kind,
            module=self.module,
            path=str(self.path.relative_to(self.root)),
            line=node.lineno,
            end_line=getattr(node, "end_lineno", None),
            parent_id=self.parent().id if self.parent() is not None else None,
            docstring=ast.get_docstring(node),
            decorators=[
                value
                for value in (expression_to_string(decorator) for decorator in node.decorator_list)
                if value
            ],
            args=argument_names(node.args),
            returns=expression_to_string(node.returns),
        )
        self.add_symbol(symbol)
        self.stack.append(symbol)
        self.generic_visit(node)
        self.stack.pop()


def iter_python_files(root: Path, includes: Iterable[str], excludes: set[str]) -> list[Path]:
    files: list[Path] = []
    for include in includes:
        base = root / include
        if not base.exists():
            continue
        if base.is_file() and base.suffix == ".py":
            files.append(base)
            continue
        for path in base.rglob("*.py"):
            if any(part in excludes for part in path.relative_to(root).parts):
                continue
            files.append(path)
    return sorted(set(files))


def build_code_graph(
    *,
    root: Path | str = ".",
    includes: Iterable[str] = ("src",),
    excludes: set[str] | None = None,
) -> CodeGraph:
    root_path = Path(root).resolve()
    exclude_names = set(DEFAULT_EXCLUDES if excludes is None else excludes)
    nodes: list[CodeSymbol] = []
    edges: list[CodeEdge] = []
    files = iter_python_files(root_path, includes, exclude_names)
    for path in files:
        module = module_name_for_path(path, root_path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        visitor = SymbolVisitor(root=root_path, path=path, module=module)
        visitor.visit(tree)
        nodes.extend(visitor.nodes)
        edges.extend(visitor.edges)
    return CodeGraph(
        root=str(root_path),
        generated_at=time.time(),
        file_count=len(files),
        symbol_count=len(nodes),
        edge_count=len(edges),
        nodes=[asdict(node) for node in nodes],
        edges=[asdict(edge) for edge in edges],
    )


def graph_to_json(graph: CodeGraph) -> str:
    return json.dumps(asdict(graph), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_graph(graph: CodeGraph, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(graph_to_json(graph), encoding="utf-8")


def snapshot_mtimes(files: Iterable[Path]) -> dict[str, int]:
    return {str(path): path.stat().st_mtime_ns for path in files if path.exists()}


def watch_code_graph(
    *,
    root: Path,
    output_path: Path,
    includes: Iterable[str],
    interval_seconds: float,
    once: bool = False,
) -> None:
    previous: dict[str, int] = {}
    while True:
        files = iter_python_files(root, includes, set(DEFAULT_EXCLUDES))
        current = snapshot_mtimes(files)
        if current != previous:
            graph = build_code_graph(root=root, includes=includes)
            write_graph(graph, output_path)
            print(
                {
                    "output_path": str(output_path),
                    "file_count": graph.file_count,
                    "symbol_count": graph.symbol_count,
                    "edge_count": graph.edge_count,
                },
                flush=True,
            )
            previous = current
        if once:
            return
        time.sleep(interval_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Python project code graph.")
    parser.add_argument("--root", default=".", help="Project root.")
    parser.add_argument(
        "--include",
        action="append",
        default=None,
        help="Directory or file to include. Can be repeated. Defaults to src.",
    )
    parser.add_argument(
        "--output",
        default="data/artifacts/code_graph/project_code_graph.json",
        help="Output JSON path.",
    )
    parser.add_argument("--watch", action="store_true", help="Watch files and rebuild on changes.")
    parser.add_argument("--once", action="store_true", help="Build once and exit.")
    parser.add_argument("--interval", type=float, default=2.0, help="Watch polling interval.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    includes = tuple(args.include or ["src"])
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    watch_code_graph(
        root=root,
        output_path=output_path,
        includes=includes,
        interval_seconds=args.interval,
        once=args.once or not args.watch,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
