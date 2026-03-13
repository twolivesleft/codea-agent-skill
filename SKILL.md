---
name: codea
description: Control Codea on a connected iOS, iPadOS, or macOS device. Use this skill when working on Codea projects — pulling code, editing files, pushing changes, running projects, capturing screenshots, and inspecting state via Lua.
---

# Codea Skill

This directory contains the `codea` CLI tool for working with Codea projects on a connected iOS, iPadOS, or macOS device.

## Setup

```bash
pip install -e .
codea discover        # find device on local network and save config
```

Or configure manually:
```bash
codea configure --host 192.168.1.42 --port 18513
```

Or via environment variables (useful in CI or when config file isn't set up):
```bash
export CODEA_HOST=192.168.1.42
export CODEA_PORT=18513
```

## Project Naming

Projects are identified as `Collection/Project` (e.g. `Documents/Morse`) or just `Project` if the name is unique across all collections. iCloud projects use `iCloud/Collection/Project`.

```bash
codea pull "Morse"                  # unique name, works as-is
codea pull "Documents/Morse"        # explicit local collection
codea pull "iCloud/Documents/Foo"   # iCloud project
```

## Typical Agent Workflow

### Editing an existing project

```bash
# 1. Pull a project and all its dependencies
codea pull "My Game"
# Files land in ./My Game/ and ./My Game/Dependencies/<name>/

# 2. Read and edit files (use standard file tools)

# 3. Push changes back — entire project or specific files
codea push "My Game"
codea push "My Game" Main.lua Player.lua

# 4. Run and observe
codea run "My Game"
sleep 3
codea screenshot --output result.png

# 5. Execute Lua to inspect state
codea exec "print(health)"

# 6. Check logs
codea logs

# 7. Iterate
```

### Creating a new project

```bash
# 1. Create the project on the device
codea new "My Game"
codea new "My Game" --collection Documents   # explicit collection
codea new "My Game" --cloud                  # iCloud

# 2. Pull it locally — gets the default template files (Main.lua etc.)
codea pull "My Game"

# 3. Edit files locally (use standard file tools)

# 4. Push back and run
codea push "My Game"
codea run "My Game"
sleep 3
codea screenshot --output result.png
```

## Commands

### Device
| Command | Description |
|---------|-------------|
| `codea discover` | Scan network for Codea devices, save config |
| `codea configure` | Manually set device host/port |

### Collections
| Command | Description |
|---------|-------------|
| `codea collections ls` | List all collections |
| `codea collections new <name>` | Create a new local collection |
| `codea collections delete <name>` | Delete a collection (prompts for confirmation) |

### Projects
| Command | Description |
|---------|-------------|
| `codea ls` | List all projects as Collection/Project |
| `codea new <name>` | Create a new project (see naming above) |
| `codea rename <project> <newname>` | Rename a project |
| `codea delete <project>` | Delete a project (prompts for confirmation) |

### Files
| Command | Description |
|---------|-------------|
| `codea pull <project> [files...]` | Pull project + dependencies locally; optionally pull specific files |
| `codea push <project> [files...]` | Push files back to device; omit files to push everything |

### Runtime
| Command | Description |
|---------|-------------|
| `codea run <project>` | Start a project |
| `codea stop` | Stop the running project |
| `codea restart` | Restart the running project |
| `codea exec "<lua>"` | Execute Lua in the running project |
| `codea screenshot` | Save screenshot as PNG |
| `codea logs` | Get log output from running project (drains buffer) |
| `codea clear-logs` | Clear the log buffer |

### Dependencies
| Command | Description |
|---------|-------------|
| `codea deps ls <project>` | List project dependencies |
| `codea deps available <project>` | List projects that can be added as dependencies |
| `codea deps add <project> <dependency>` | Add a dependency |
| `codea deps remove <project> <dependency>` | Remove a dependency |

## Pull / Push Details

`codea pull "My Game"` creates:
```
My Game/
  Main.lua
  Player.lua
  ...
  Dependencies/
    PhysicsLib/
      Physics.lua
```

`codea push "My Game"` pushes all files in `./My Game/` back, routing
`Dependencies/<name>/` files to the correct project on the device.

Use `--output <dir>` with pull and `--input <dir>` with push to specify a custom directory.

## Notes for Agents

- Always `pull` before editing to get the latest files from device
- Use `sleep 2` or similar between `run` and `screenshot` to let the project render a frame
- `exec` requires a project to already be running
- Screenshot returns a PNG — save it and use vision to inspect results; do not open it in an external app unless the user explicitly asks
- File paths on device use `codea://` URIs internally; you don't need to deal with these directly
