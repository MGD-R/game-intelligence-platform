# Code Graph MCP

The project includes a lightweight Python AST graph builder and a stdio MCP server for
tracking the hierarchy of modules, classes, functions, async functions, and methods.

## Build Once

```bash
make code-graph
```

Default output:

```text
data/artifacts/code_graph/project_code_graph.json
```

The JSON graph contains:

- `nodes`: classes/functions/methods with module, path, line, docstring, args, bases, decorators.
- `edges`: `contains` edges from class/function parents to nested children.
- counters: `file_count`, `symbol_count`, `edge_count`.

## Watch Mode

```bash
make code-graph-watch
```

The watcher polls Python source mtimes and rewrites the graph whenever files change.

Direct command:

```bash
python -m src.devtools.code_graph \
  --root . \
  --include src \
  --watch \
  --interval 2 \
  --output data/artifacts/code_graph/project_code_graph.json
```

When running through Codex shell, prepend commands with `rtk`.

## MCP Server

```bash
make code-graph-mcp
```

Direct command:

```bash
python -m src.devtools.code_graph_mcp --root . --include src --interval 2
```

Suggested MCP config:

```json
{
  "mcpServers": {
    "game-intelligence-code-graph": {
      "command": "python",
      "args": [
        "-m",
        "src.devtools.code_graph_mcp",
        "--root",
        "/Users/mgdr/Documents/Projects/game-intelligence-platform",
        "--include",
        "src",
        "--interval",
        "2"
      ],
      "cwd": "/Users/mgdr/Documents/Projects/game-intelligence-platform"
    }
  }
}
```

## MCP Tools

- `get_code_graph`: return the current graph, optionally filtered by `module_prefix` and `kind`.
- `list_symbols`: list symbols with optional `module_prefix`, `kind`, `name_contains`, `limit`.
- `get_symbol`: return one symbol and its direct children by `symbol_id`.
- `refresh_code_graph`: force a rebuild.
- `watch_status`: return graph counters and last refresh reason.
