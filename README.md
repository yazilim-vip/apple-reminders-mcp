# Apple Reminders MCP Server

> MCP server for Apple Reminders on macOS via EventKit (pyobjc). Zero binary installs — runs with `uv`.

## Prerequisites

- macOS with Reminders.app
- `uv` installed ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
- No manual Python dependency install needed — `uv run` handles everything

## Install

**No clone needed** — run directly from GitHub:

**Claude Code CLI:**

```bash
claude mcp add apple-reminders -- uvx --from git+https://github.com/yazilim-vip/apple-reminders-mcp apple-reminders-mcp
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "apple-reminders": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/yazilim-vip/apple-reminders-mcp",
        "apple-reminders-mcp"
      ]
    }
  }
}
```

### Pin to a specific version

```bash
uvx --from git+https://github.com/yazilim-vip/apple-reminders-mcp@v0.1.0 apple-reminders-mcp
```

### Local development

```bash
git clone git@github.com:yazilim-vip/apple-reminders-mcp.git
cd apple-reminders-mcp
uv sync --group dev
uv run apple-reminders-mcp
```

## Tools

| Tool | Description |
|------|-------------|
| `list_reminder_lists` | List all reminder lists with counts |
| `create_reminder_list` | Create a new reminder list |
| `delete_reminder_list` | Delete a reminder list and all its reminders |
| `list_reminders` | List reminders, optionally filter by list |
| `search_reminders` | Search reminders by name/notes |
| `add_reminder` | Create a new reminder with optional due date, notes, priority |
| `complete_reminder` | Mark a reminder as complete |
| `edit_reminder` | Edit reminder fields (name, due, notes, priority) |
| `move_reminder` | Move a reminder to a different list |
| `delete_reminder` | Delete a reminder by name search |

## Tech Stack

- **Python** ≥ 3.11
- **FastMCP** — MCP server framework
- **pyobjc-framework-EventKit** — Native macOS EventKit bindings (no AppleScript)
- **uv** — Fast Python package manager and runner
