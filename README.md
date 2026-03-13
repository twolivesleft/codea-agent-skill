# Codea Agent Skill

A CLI tool that lets AI agents (and humans) control [Codea](https://codea.io) remotely over the network. It connects to Codea's built-in Air Code server and exposes project management, file editing, runtime control, and dependency management as simple shell commands — the same interface whether you're a human in a terminal or an AI agent in a tool call.

## Requirements

- Python 3.10+
- Codea running on an iOS, iPadOS, or macOS device with **Air Code** enabled

## Installation

```bash
git clone https://github.com/twolivesleft/codea-agent-skill.git
cd codea-agent-skill
pip install -e .
```

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
```

---

## Command Reference

### Device Setup

| Command | Description |
|---------|-------------|
| `codea discover` | Scan the local network for Codea devices and save config |
| `codea configure --host <ip> --port <port>` | Manually set the device host and port |

### Projects

| Command | Description |
|---------|-------------|
| `codea ls` | List all projects as `Collection/Project` |
| `codea new <name>` | Create a new project (supports `Collection/Project` notation) |
| `codea rename <project> <newname>` | Rename a project |
| `codea delete <project>` | Delete a project (prompts for confirmation) |

### Files

| Command | Description |
|---------|-------------|
| `codea pull <project> [files...]` | Pull a project locally; optionally pull specific files only |
| `codea push <project> [files...]` | Push files to the device; omit files to push everything |

Options for `pull`: `--output <dir>` to specify a local directory (default: `./<project>`), `--no-deps` to skip dependencies.

Options for `push`: `--input <dir>` to specify the local source directory (default: `./<project>`).

### Runtime

| Command | Description |
|---------|-------------|
| `codea run <project>` | Start a project on the device |
| `codea stop` | Stop the running project |
| `codea restart` | Restart the running project |
| `codea exec "<lua>"` | Execute a Lua expression in the running project |
| `codea screenshot [--output <file>]` | Capture the device screen as a PNG (default: `screenshot.png`) |
| `codea logs` | Get log output from the running project |
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
