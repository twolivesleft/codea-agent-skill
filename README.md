# Codea Skill

This repo contains the `codea` agent skill for working with [Codea](https://codea.io) projects on connected iOS, iPadOS, and macOS devices.

The skill teaches agents how to use the `codea` CLI effectively across both target types:

- `Project storage = filesystem`
  Local macOS Codea / Carbide workflow. Edit files directly on disk and run by path.
- `Project storage = collections`
  iPhone / iPad workflow. Pull projects locally, edit, push changes back, then run.

The canonical workflow guidance lives in [`SKILL.md`](/Users/sim/Developer/Open/codea-skill/SKILL.md).

For the CLI itself:

- Friendly install and feature overview: [codea.io/cli](https://codea.io/cli)
- Source and development: [twolivesleft/codea-cli](https://github.com/twolivesleft/codea-cli)

## Requirements

- Codea running on an iOS, iPadOS, or macOS device with Air Code enabled
- The `codea` CLI installed locally

## Install The CLI

For end users, start here:

- [codea.io/cli](https://codea.io/cli)

If you want the direct install commands:

For macOS, Linux, or WSL:

```bash
brew install twolivesleft/tap/codea
```

For Windows via PowerShell:

```powershell
powershell -c "irm https://github.com/twolivesleft/codea-cli/releases/latest/download/codea-cli-installer.ps1 | iex"
```

After install, confirm the CLI is available:

```bash
codea --help
```

## Install The Skill

To make the skill available to supported agents:

```bash
npx skills add twolivesleft/codea-skill
```

This installs the skill globally or project-locally, depending on the agent.

## Quick Start

1. Connect to a target:

```bash
codea discover
codea configure --host 192.168.1.42 --port 18513
```

2. Check the target type:

```bash
codea status
```

3. Follow the appropriate workflow from [`SKILL.md`](/Users/sim/Developer/Open/codea-skill/SKILL.md):

- Filesystem-backed targets: work directly in the local project directory and run by path.
- Collection-backed targets: `pull`, edit locally, `push`, then `run`.

## Notes

- The CLI performs a cached once-per-day update check by default. Set `CODEA_NO_UPDATE_CHECK=1` to disable it.
- Clear a saved device profile with `codea configure --clear`.
- If `codea` is not on `PATH`, use the installed binary path or your local build directly.

## More Information

- Agent workflow guidance: [`SKILL.md`](/Users/sim/Developer/Open/codea-skill/SKILL.md)
- CLI install and overview: [codea.io/cli](https://codea.io/cli)
- CLI project and command reference: [twolivesleft/codea-cli](https://github.com/twolivesleft/codea-cli)
