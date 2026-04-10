# Apple Reminders MCP Server

## Identity

MCP server for Apple Reminders on macOS. Exposes Reminders.app via native EventKit bindings (pyobjc) — no AppleScript, no binary installs.

**Tech Stack:** Python 3.11+, FastMCP, pyobjc-framework-EventKit, uv

## Module Map

| Module | Path | Purpose |
|--------|------|---------|
| server | `src/apple_reminders_mcp/server.py` | All MCP tools — reminder and list CRUD |

## Build & Run

```bash
# Install dependencies
uv sync --group dev

# Run server locally
uv run apple-reminders-mcp

# Run directly from GitHub (no clone)
uvx --from git+https://github.com/yazilim-vip/apple-reminders-mcp apple-reminders-mcp

# Lint
uv run ruff check .
uv run ruff format --check .

# Build distributable
uv build
```

## Key Paths

| Path | Purpose |
|------|---------|
| `src/apple_reminders_mcp/server.py` | MCP tool definitions and EventKit bridge |
| `pyproject.toml` | Project metadata, dependencies, ruff config |
| `.github/workflows/ci.yml` | CI: lint, build, version check, GitHub release |

## Project Rules

- **macOS only** — EventKit requires macOS with Reminders.app
- **Version bump required** — CI blocks PRs that don't bump `version` in `pyproject.toml`
- **Single-file server** — all tools live in `server.py`; split only when complexity demands it
- **No AppleScript** — use pyobjc EventKit bindings exclusively

## Dependencies

| Dependency | Relationship |
|-----------|-------------|
| FastMCP | MCP server framework |
| pyobjc-framework-EventKit | Native macOS Reminders access |
| uv | Package management and execution |
