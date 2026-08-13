# MCP-Memory: OKF-Backed Agent Memory Server

**MCP-Memory** is a Model Context Protocol (MCP) server that equips AI agents (such as Claude Desktop, Cursor, Antigravity, Windsurf, or Codex) with persistent, long-term memory capabilities.

Memory records are formatted using the [**Open Knowledge Format (OKF v0.2)**](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) standard and indexed with a local **SQLite** instance (supporting FTS5 full-text search) for fast key-value lookups, tag filtering, and content search.

> **Fast Track:** [Jump directly to Quick Start](#quick-start)

---

## Key Features

* **Persistent State Across Sessions:** Enables AI agents to read, store, search, and delete stateful memory snippets that persist across chat turns and sessions.
* **OKF Standard Compliance:** Stores every memory item formatted as an OKF v0.2 Markdown document with YAML frontmatter (`type`, `key`, `namespace`, `tags`, `generated`, `sources`, `verified`, `status`, `stale_after`), adhering strictly to [`SPEC.md`](SPEC.md) and [`OKF_RULES.md`](OKF_RULES.md).
* **Dual-Layer Architecture:**
  - **Human-Browseable OKF Directory**: Automatically dumps and syncs every memory to disk as a raw `.md` file inside the `memory/` bundle directory with hierarchical `index.md` progressive disclosure files (root `index.md` versioned with `okf_version: "0.2"`) and `log.md` update history tracking.
  - **High-Performance SQLite Indexing**: SQLite FTS5 (Full-Text Search) and automatic triggers for sub-20ms key lookups and instant keyword searches.
* **Namespace Isolation:** Supports contextual separation (e.g. `user/preferences`, `project/architecture`, `default`).
* **Zero Boilerplate Setup:** Quick setup wizard (`python3 setup.py`) auto-configures installed MCP tools (Antigravity, Claude, Cursor, Windsurf, Codex).

---

## MCP Tools

The server exposes four primary MCP tools to interacting agents:

### 1. `memory_store`
Stores or updates a memory record in OKF v0.2 format.
* **Parameters:**
  - `key` *(string, required)*: Unique identifier or path for the memory (e.g. `user/preferences/coding_style` or `project/architecture`).
  - `content` *(string or object, required)*: Core information to store.
  - `project_root` *(string, required)*: Absolute path to the active project root directory (e.g. `/Users/user/Projects/my-app`).
  - `tags` *(array of strings, optional)*: Classification tags for filtering.
  - `namespace` *(string, optional, default: `"default"`)*: Scope/namespace.
  - `concept_type` *(string, optional, default: `"Agent Memory"`)*: OKF concept type (e.g. `Metric`, `Playbook`, `Attested Computation`).
  - `title` *(string, optional)*: Display name.
  - `description` *(string, optional)*: One-line summary.
  - `resource` *(string, optional)*: Canonical URI of underlying asset.
  - `status` *(string, optional, default: `"stable"`)*: Lifecycle state (`draft` | `stable` | `deprecated`).
  - `stale_after` *(string, optional)*: ISO date (`YYYY-MM-DD`).
  - `sources` *(array of objects, optional)*: Provenance sources `[{resource, id, title, author, usage_count, last_modified}]`.
  - `verified` *(array of objects or object, optional)*: Verification events `[{by, at}]`.
  - `generated_by` *(string, optional)*: Actor identifier following actor convention (`<producer>/<version>`, `human:<id>`, `process:<id>`).

### 2. `memory_retrieve`
Retrieves a specific memory by its key and namespace.
* **Parameters:**
  - `key` *(string, required)*: The memory key to look up.
  - `project_root` *(string, required)*: Absolute path to the active project root directory.
  - `namespace` *(string, optional, default: `"default"`)*: Scope/namespace.

### 3. `memory_search`
Finds memories matching keywords, tags, or namespace filters.
* **Parameters:**
  - `project_root` *(string, required)*: Absolute path to the active project root directory.
  - `query` *(string, optional)*: Keyword search query across keys, frontmatter, and content.
  - `tags` *(array of strings, optional)*: Filter by specific tags.
  - `namespace` *(string, optional)*: Scope search to a namespace.
  - `limit` *(integer, optional, default: 10)*: Maximum number of results.

### 5. `memory_get_last`
**AGENT DIRECTIVE (Session Start):** Retrieves the last recorded session checkpoint (`system/last_memory`) so the AI agent immediately knows where work was left off when opening a project or starting a session.
* **Parameters:**
  - `project_root` *(string, required)*: Absolute path to active project root directory.
  - `namespace` *(string, optional, default: `"default"`)*: Scope/namespace.

### 6. `memory_update_last`
**AGENT DIRECTIVE (Milestones & Progress):** Updates the canonical session checkpoint (`system/last_memory`) whenever completing a milestone, making key changes, or pausing work.
* **Parameters:**
  - `content` *(string or object, required)*: Brief note or structured dictionary summarizing progress and referencing key memory files.
  - `project_root` *(string, required)*: Absolute path to active project root directory.
  - `namespace` *(string, optional, default: `"default"`)*: Scope/namespace.
  - `summary` *(string, optional)*: One-sentence description of the milestone achieved.

---

## OKF (Open Knowledge Format) Structure

Every stored memory strictly adheres to the OKF v0.2 specification ([`SPEC.md`](SPEC.md) & [`OKF_RULES.md`](OKF_RULES.md)):

```markdown
---
type: Agent Memory
title: Coding Style
key: user/preferences/coding_style
namespace: default
tags:
- preferences
- style
status: stable
generated:
  by: mcp-memory/0.2.0
  at: '2026-08-12T19:23:35Z'
created_at: '2026-08-12T19:23:35Z'
updated_at: '2026-08-12T19:23:35Z'
---

User prefers functional programming style with explicit type annotations.
```

---

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/fellowgeek/mcp-memory
cd mcp-memory
```

### 2. Interactive Setup Wizard
Run `setup.py` to auto-detect and register `mcp-memory` with your AI tools:

```bash
python3 setup.py
```

> **Note:** Once `setup.py` finishes configuring your tools, your AI client will launch `mcp-memory` automatically in the background whenever needed. You do not need to manually start or keep a server process running in your terminal.

### 3. Run Manually via CLI (Optional / Debugging)
If you want to manually verify startup, inspect stdio output, or pre-initialize the virtual environment (`.venv`), you can run `run.sh` directly:

```bash
./run.sh
```

---

## Manual Client Configuration

If you prefer to configure your MCP client manually, add the `"memory"` server entry pointing to `run.sh`:

### JSON Configuration (Antigravity, Claude Desktop, Cursor, Windsurf)
Add to your client's `mcp_config.json` or `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "/ABSOLUTE/PATH/TO/run.sh"
    }
  }
}
```

### TOML Configuration (Codex Desktop)
Add to `~/.codex/config.toml`:

```toml
[mcp_servers.memory]
command = "/ABSOLUTE/PATH/TO/run.sh"
```

### CLI Configuration

- **Claude Code CLI:**
  ```bash
  claude mcp add --scope user memory -- /ABSOLUTE/PATH/TO/run.sh
  ```
- **Codex CLI:**
  ```bash
  codex mcp add memory -- /ABSOLUTE/PATH/TO/run.sh
  ```

---

## Testing

Run the automated test suite to verify OKF serialization, SQLite database operations, and FastMCP tool execution:

```bash
python3 test_memory.py
```

## Storage & Environment Variables

By default, `mcp-memory` creates project-isolated memory stores inside each project's root directory:
- **OKF Markdown Files (Human-readable)**: `memory/` folder in project root.
- **SQLite Database (Hidden index)**: `.mcp_memory/memories.db` in project root.

You can customize this behavior using environment variables:

- `MCP_MEMORY_PROJECT_ROOT`: Project root directory (default: process current working directory `cwd`).
- `MCP_MEMORY_DB_PATH`: SQLite database file path (default: `.mcp_memory/memories.db` relative to project root).
- `MCP_MEMORY_DIR`: Directory for Open Knowledge Format (OKF) `.md` files (default: `memory` relative to project root).

> **Tip:** If you prefer a single global memory store shared across all projects, set `MCP_MEMORY_DB_PATH=~/.mcp_memory/memories.db` and `MCP_MEMORY_DIR=~/.mcp_memory/memory` in your client's MCP configuration.
