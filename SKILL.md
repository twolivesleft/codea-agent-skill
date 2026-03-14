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

Always disable the idle timer at the start of a session so the device screen stays awake:

```bash
codea idle-timer off
```

### Editing an existing project

```bash
# 1. Pull a project and all its dependencies
codea pull "My Game"
# Files land in ./My Game/ and ./My Game/Dependencies/<name>/

# 2. Read and edit files (use standard file tools)

# 3. Push only the modified files (prefer this over pushing the entire project)
codea push "My Game" Main.lua Player.lua
# Push entire project only if you don't know which files changed
codea push "My Game"

# 4. Start log monitoring, then run
codea clear-logs
codea logs --follow >> /tmp/codea.log &
codea run "My Game"
sleep 3
codea screenshot --output result.png

# 5. Execute Lua to inspect state
codea exec "print(health)"

# 6. Check logs
cat /tmp/codea.log

# 7. Iterate (push changes, restart, check logs again)
codea push "My Game" Main.lua
codea restart
sleep 2
cat /tmp/codea.log
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
| `codea pause` | Pause the running project |
| `codea resume` | Resume the paused project |
| `codea paused` | Check whether the running project is paused |
| `codea paused <on\|off>` | Pause or unpause the running project |
| `codea screenshot` | Save screenshot as PNG |
| `codea idle-timer` | Check current idle timer state |
| `codea idle-timer <on\|off>` | Enable or disable the idle timer (`off` keeps the screen awake) |
| `codea logs` | Get all log output since last clear |
| `codea logs --head N` | Get first N lines (useful when an early error causes spam) |
| `codea logs --tail N` | Get last N lines |
| `codea logs --follow` | Stream new log lines in real time (Ctrl-C to stop) |
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

## File Loading Order (Info.plist)

Each Codea project contains an `Info.plist` file. The `Buffer Order` key in this file is an array of strings that defines the order in which Lua files are loaded by the runtime.

```xml
<key>Buffer Order</key>
<array>
    <string>Main</string>
    <string>ClassA</string>
    <string>ClassB</string>
</array>
```

Managing this order is critical in several scenarios:
- **Global Variables**: Any global variables or constants must be defined in a file that is loaded *before* they are used by other files.
- **Class Inheritance**: Base classes must be loaded before any derived classes that inherit from them.
- **Initialization**: Logic that expects certain systems to be initialized globally should be ordered appropriately.

When creating a new project with `codea new` and pulling it locally, the `Buffer Order` will typically only contain `Main`. As you add new `.lua` files to the project, you **must** update the `Buffer Order` in `Info.plist` and push the changes back to the device to ensure the project runs correctly.

## Log Monitoring with --follow

The recommended pattern for monitoring logs while working is to start a background log stream before running the project:

```bash
codea clear-logs
codea logs --follow >> /tmp/codea.log &
codea run "My Game"

# ... edit files, push changes, take screenshots ...

cat /tmp/codea.log          # check all logs at any point
tail -n 20 /tmp/codea.log   # check recent output
```

This keeps `/tmp/codea.log` continuously updated so you can inspect it at any time without missing output between polls. Kill the background process when done:

```bash
kill %1   # or: pkill -f "codea logs --follow"
```

## Codea API Documentation

Before using any Codea API, fetch the relevant documentation page first. The reference is organized by topic — always identify the right section before coding.

- **Legacy runtime index**: https://codea.io/reference/index.html
  - Animation: https://codea.io/reference/Animation.html
  - Craft (3D): https://codea.io/reference/Craft.html
  - Display & keyboard: https://codea.io/reference/Display.html
  - Graphics & assets: https://codea.io/reference/Graphics.html
  - Lua: https://codea.io/reference/Lua.html
  - Motion & location: https://codea.io/reference/Accelerometer.html
  - Network: https://codea.io/reference/Network.html
  - Parameters: https://codea.io/reference/Parameters.html
  - Physics: https://codea.io/reference/Physics.html
  - Shaders & Mesh: https://codea.io/reference/Shaders.html
  - Sounds: https://codea.io/reference/Sounds.html
  - Storage: https://codea.io/reference/Storage.html
  - Touch & input: https://codea.io/reference/Touch.html
  - Vector: https://codea.io/reference/Vector.html
- **Modern runtime (Carbide)**: https://twolivesleft.github.io/Codea4-Docs/

## Best Practices & Gotchas

### Asset Strings
Asset strings using the `Project:Asset` format (e.g., `readImage("Blobbo:empty")`) are **deprecated**. You should use static assets instead:
- **Correct**: `asset.empty` or `asset.wall`
- **Deprecated**: `readImage("Project:empty")`

### Missing `roundRect`
The `roundRect` function is not built-in to the Codea runtime. If your project requires rounded rectangles, you must implement the function yourself (e.g., using `mesh` or drawing multiple `rect` and `ellipse` calls).

## Notes for Agents

- Always `pull` before editing to get the latest files from device
- Use `sleep 2` or similar between `run` and `screenshot` to let the project render a frame
- `exec` requires a project to already be running
- Screenshot returns a PNG — save it and use vision to inspect results; do not open it in an external app unless the user explicitly asks
- `codea logs` accumulates all output since last `clear-logs`; use `--head 20` when Codea is spamming a repeated error to find the original cause
- File paths on device use `codea://` URIs internally; you don't need to deal with these directly
