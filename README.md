# Codea Agent Skill

A CLI tool that lets AI agents (and humans) control [Codea](https://codea.io) remotely over the network. It connects to Codea's built-in Air Code server and exposes project management, file editing, runtime control, and dependency management as simple shell commands — the same interface whether you're a human in a terminal or an AI agent in a tool call.

## Requirements

- Python 3.10+
- Codea running on an iOS, iPadOS, or macOS device with **Air Code** enabled

## Installation

### CLI tool

```bash
git clone https://github.com/twolivesleft/codea-agent-skill.git
cd codea-agent-skill
pip install -e .
```

### Agent skill

To make the skill available to AI agents (Claude Code, Cursor, Cline, and [40+ others](https://github.com/vercel-labs/skills)):

```bash
npx skills add twolivesleft/codea-agent-skill
```

This installs the skill globally (`~/.claude/skills/codea/`) or project-locally (`.claude/skills/codea/`), where supported agents automatically discover it.

## Quick Start

### 1. Connect to your device

With Codea open and Air Code running, scan your local network:

```bash
codea discover
# Scanning for Codea devices (5s)...
#   1. My-iPad.local  (192.168.1.42:18513)
# Saved 192.168.1.42:18513 as profile 'default'.
```

Or configure manually if you know the IP:

```bash
codea configure --host 192.168.1.42 --port 18513
```

### 2. Create a new project

```bash
codea new "My Game"
# Created project 'My Game'
```

### 3. Pull it locally and edit

```bash
codea pull "My Game"
# Pulls files into ./My Game/
```

Edit the files with any text editor or let an AI agent do it.

### 4. Push changes and run

```bash
codea push "My Game"
codea run "My Game"
sleep 3
codea screenshot --output result.png
```

### 5. Inspect and iterate

```bash
codea exec "print(score)"   # execute Lua on the running project
codea logs                  # view output
codea restart               # restart without re-pushing
```

---

## Project Naming

Projects are identified by name alone if it's unique across all collections, or as `Collection/Project` to disambiguate.

### Default collections

| Path | Description |
|------|-------------|
| `Documents/MyProject` | Default local collection |
| `MyCollection/MyProject` | Custom local collection |
| `iCloud/Documents/MyProject` | iCloud |

```bash
codea pull "Morse"                  # unique name — works as-is
codea pull "Documents/Morse"        # explicit local collection
codea pull "iCloud/Documents/Foo"   # iCloud project
```

The same notation works when creating projects:

```bash
codea new "Morse"                   # creates in default collection (Documents)
codea new "Documents/Morse"         # explicit collection
codea new "iCloud/Documents/Morse"  # iCloud
codea new "Morse" --template Modern # use the Modern (Carbide) template
```

---

## Command Reference

### Global Flags

| Flag | Description |
|------|-------------|
| `codea --wait <command>` | Wait for Codea to become reachable before running the command |

`--wait` polls the Air Code server until it responds, then proceeds. Useful when issuing commands remotely while Codea is in the background — the CLI blocks until you switch back to the app on your device. Reports how long it waited.

```bash
codea --wait ls          # wait for Codea, then list projects
codea --wait run "Foo"   # wait for Codea, then run project
```

### Device Setup

| Command | Description |
|---------|-------------|
| `codea discover` | Scan the local network for Codea devices and save config |
| `codea configure --host <ip> --port <port>` | Manually set the device host and port |
| `codea status` | Show current device configuration and live state |

### Projects

| Command | Description |
|---------|-------------|
| `codea ls` | List all projects as `Collection/Project` |
| `codea new <name>` | Create a new project (supports `Collection/Project` notation); `--template <name>` selects a template |
| `codea rename <project> <newname>` | Rename a project |
| `codea move <project> <collection>` | Move a project to a different collection |
| `codea delete <project>` | Delete a project (prompts for confirmation) |

### Templates

| Command | Description |
|---------|-------------|
| `codea templates ls` | List all templates (built-in and custom) |
| `codea templates add <project>` | Copy a project into the custom templates collection; `--name <name>` to rename |
| `codea templates remove <name>` | Remove a custom template (prompts for confirmation) |

Custom templates live in the `Templates` collection and appear in `codea ls` as `Templates/<name>`. They can be edited like any project — use `codea pull "Templates/My Template"` to pull locally, edit files, then `codea push "Templates/My Template"` to update the template.

### Files

| Command | Description |
|---------|-------------|
| `codea pull <project> [files...]` | Pull a project locally; optionally pull specific files only |
| `codea push <project> [files...]` | Push files to the device; omit files to push everything |

Options for `pull`: `--output <dir>` to specify a local directory (default: `./<project>`), `--no-deps` to skip dependencies.

Options for `push`: `--input <dir>` to specify the local source directory (default: `./<project>`).

Options for `doc`: `--legacy` / `--modern` to filter to one runtime, or `--project <name>` to automatically show only docs relevant to that project's runtime. Output includes a "See also:" line listing related functions in the same group.

Options for `search-doc`: `--legacy` / `--modern` to filter to one runtime, or `--project <name>` to automatically filter based on the project's runtime. Returns a flat list of matching functions with brief descriptions and a `[modern]`, `[legacy]`, or `[both]` tag.

### Runtime

| Command | Description |
|---------|-------------|
| `codea run <project>` | Start a project on the device |
| `codea stop` | Stop the running project |
| `codea restart` | Restart the running project |
| `codea exec "<lua>"` | Execute a Lua expression in the running project |
| `codea exec --file <path>` | Execute the contents of a Lua file in the running project |
| `codea pause` | Pause the running project |
| `codea resume` | Resume the paused project |
| `codea paused [on\|off]` | Get or set the paused state; omit argument to check current state |
| `codea screenshot [--output <file>]` | Capture the device screen as a PNG (default: `screenshot.png`) |
| `codea idle-timer <on\|off>` | Enable or disable the idle timer (`off` keeps the screen awake) |
| `codea runtime <project> [legacy\|modern]` | Get or set the runtime type for a project; omit type to check current |
| `codea autocomplete <project> <code>` | Get Lua autocomplete suggestions for a code prefix |
| `codea doc <function>` | Look up Codea API documentation for a function; includes a "See also" list of related functions |
| `codea search-doc <query>` | Search API documentation by keyword across both runtimes |
| `codea logs` | Get all log output since last clear |
| `codea logs --head N` | Get first N lines (useful when an early error causes log spam) |
| `codea logs --tail N` | Get last N lines |
| `codea logs --follow` / `-f` | Stream new log lines in real time via SSE (Ctrl-C to stop) |
| `codea clear-logs` | Clear the log buffer |

### Collections

| Command | Description |
|---------|-------------|
| `codea collections ls` | List all collections on the device |
| `codea collections new <name>` | Create a new local collection |
| `codea collections delete <name>` | Delete a collection (prompts for confirmation) |

### Dependencies

| Command | Description |
|---------|-------------|
| `codea deps ls <project>` | List a project's current dependencies |
| `codea deps available <project>` | List projects that can be added as dependencies |
| `codea deps add <project> <dependency>` | Add a dependency to a project |
| `codea deps remove <project> <dependency>` | Remove a dependency from a project |

---

## Pull / Push Details

`codea pull "My Game"` creates a local mirror of the project:

```
My Game/
  Main.lua
  Player.lua
  ...
  Dependencies/
    PhysicsLib/
      Physics.lua
```

Dependencies are pulled automatically alongside the project. Use `--no-deps` to skip them.

`codea push "My Game"` pushes all files back, automatically routing `Dependencies/<name>/` files to the correct project on the device.

```bash
# Pull to a custom directory
codea pull "My Game" --output ~/projects/mygame

# Push from a custom directory
codea push "My Game" --input ~/projects/mygame

# Push only specific files (e.g. while the project is running)
codea push "My Game" Main.lua Player.lua
```

---

## Configuration

Configuration is stored in `~/.codea/config.json`. Multiple device profiles are supported:

```bash
codea discover --profile ipad
codea ls --profile ipad
```

Environment variables override the config file:

```bash
export CODEA_HOST=192.168.1.42
export CODEA_PORT=18513
```

---

## For AI Agents

This tool ships with a `SKILL.md` file that AI coding assistants (Claude Code and others) automatically pick up as an agent skill. Once installed, agents can pull projects, edit code, push changes, run projects, and inspect results — all through the `codea` CLI.

See `SKILL.md` for the agent-specific workflow documentation.

---

## MCP Server

Codea's Air Code server also speaks the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), giving AI agents direct access to Codea without the CLI. MCP tools work on individual files in-place — no pull/push cycle needed.

### Connecting via MCP

Point your MCP client at the Air Code server:

```
http://<device-ip>:18513/mcp
```

For example, in Claude Code:

```bash
claude mcp add codea --transport http http://192.168.1.42:18513/mcp
```

### Choosing Between CLI and MCP

| | CLI (`codea`) | MCP |
|---|---|---|
| **Works with** | Any terminal or agent via shell | MCP-compatible clients (Claude Code, Cursor, etc.) |
| **File editing** | Pull locally → edit → push | Read/write files directly on device |
| **Network scan** | `codea discover` | Configure host manually |
| **Streaming logs** | `codea logs --follow` | `getLogs` (poll) |
| **Best for** | Scripting, CI, bulk operations | Interactive AI agent sessions |

### MCP Tool Reference

#### Collections

| Tool | Description |
|------|-------------|
| `listCollections` | List all collections. Returns logical paths like `Documents` (local) or `iCloud/Documents` (cloud). |
| `createCollection` | Create a new local collection. |
| `deleteCollection` | Delete a local collection. |

#### Projects

| Tool | Parameters | Description |
|------|------------|-------------|
| `listProjects` | — | List all projects on the device as logical paths (e.g. `Documents/MyProject`). |
| `createProject` | `name`, `collection?`, `cloud?`, `template?` | Create a new project. `template` accepts names like `Default` or `Modern`. |
| `deleteProject` | `path` | Delete a project. |
| `renameProject` | `path`, `newName` | Rename a project. |
| `moveProject` | `path`, `collection` | Move a project to a different collection. |
| `getRuntime` | `path` | Get the runtime type (`legacy` or `modern`) for a project. |
| `setRuntime` | `path`, `runtime` | Set the runtime type for a project. |

#### Templates

| Tool | Parameters | Description |
|------|------------|-------------|
| `listTemplates` | — | List all available templates (built-in and custom). |
| `addTemplate` | `path`, `name?` | Copy a project into the custom templates collection. |
| `removeTemplate` | `name` | Remove a custom template by name. |

#### Files

| Tool | Parameters | Description |
|------|------------|-------------|
| `listFiles` | `path` | List all files in a project. |
| `readFile` | `path` | Read the contents of a file (e.g. `MyProject/Main.lua`). |
| `writeFile` | `path`, `content` | Write content to a file; creates it if it doesn't exist. |
| `deleteFile` | `path` | Delete a file from a project. |
| `renameFile` | `path`, `newName` | Rename a file within a project. |
| `copyFile` | `path`, `newName` | Copy a file within a project. |
| `findInFiles` | `path`, `text`, `caseSensitive?`, `wholeWord?`, `isRegex?` | Search for text across all files in a project. |

#### Runtime

| Tool | Parameters | Description |
|------|------------|-------------|
| `runProject` | `path` | Run a project on the device. |
| `stopProject` | — | Stop the currently running project. |
| `restartProject` | — | Restart the currently running project. |
| `executeLua` | `code` | Execute a Lua string in the running project. |
| `captureScreenshot` | — | Capture a screenshot of the device screen as a PNG. |
| `getDeviceState` | — | Get current state: running/idle, active project, idle timer, paused state. |
| `getProjectPaused` | — | Check whether the running project is paused. |
| `getIdleTimerDisabled` | — | Get the idle timer state (disabled = screen kept on). |
| `setIdleTimerDisabled` | `disabled` | Enable or disable the idle timer. |
| `getLogs` | `head?`, `tail?` | Get log output since the last `clearLogs`. Pass `head` or `tail` to limit lines. |
| `clearLogs` | — | Clear the log buffer. |

#### Dependencies

| Tool | Parameters | Description |
|------|------------|-------------|
| `listDependencies` | `path` | List a project's current dependencies. |
| `listAvailableDependencies` | `path` | List projects that can be added as dependencies. |
| `addDependency` | `path`, `dependency` | Add a dependency to a project. |
| `removeDependency` | `path`, `dependency` | Remove a dependency from a project. |

#### Documentation & Autocomplete

| Tool | Parameters | Description |
|------|------------|-------------|
| `getFunctionHelp` | `functionName` | Get full documentation for a Codea API function (e.g. `sprite`, `physics.body`). Includes legacy and modern signatures plus a `seeAlso` list. |
| `searchDocs` | `query` | Search API docs by keyword across both runtimes. |
| `getCompletions` | `path`, `code` | Get Lua autocomplete suggestions for a code prefix within a project. |
