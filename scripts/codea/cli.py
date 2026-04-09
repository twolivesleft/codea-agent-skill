import base64
import json
import os
import plistlib
import sys
import time
from pathlib import Path
from typing import Optional

import click

from .config import load_config, save_config, DEFAULT_PORT, CONFIG_FILE
from .discover import discover_devices
from .mcp_client import MCPClient, MCPError


# --- Helpers ---

def _wait_for_device(host: str, port: int, poll_interval: float = 1.0) -> None:
    """Poll until the Air Code server at host:port responds."""
    click.echo("Waiting for Codea...", err=True)
    start = time.time()
    while True:
        try:
            probe = MCPClient(host, port, timeout=3)
            probe.initialize()
            click.echo(f"Codea ready (waited {time.time() - start:.1f}s).", err=True)
            return
        except MCPError:
            # Server responded with an MCP-level error — still reachable
            click.echo(f"Codea ready (waited {time.time() - start:.1f}s).", err=True)
            return
        except Exception:
            time.sleep(poll_interval)


def get_client(profile: str) -> MCPClient:
    config = load_config(profile)
    if not config.get("host"):
        raise click.ClickException(
            "No device configured. Run 'codea discover' or 'codea configure' first.\n"
            "Or set CODEA_HOST (and optionally CODEA_PORT) environment variables."
        )
    host = config["host"]
    port = config.get("port", DEFAULT_PORT)
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.find_root().obj and ctx.find_root().obj.get("wait"):
        _wait_for_device(host, port)
    return MCPClient(host, port)


def project_name(path: str) -> str:
    """Get the bare project name from a logical path like 'Documents/Morse' or 'iCloud/Documents/Foo'."""
    return path.split("/")[-1]


def pull_project_files(client: MCPClient, project_path: str, output_dir: Path, files: tuple = (), label: str = ""):
    """Pull files from a project path into output_dir. If files is given, only pull those."""
    prefix = f"[{label}] " if label else ""
    try:
        all_files = client.list_files(project_path)
    except MCPError as e:
        click.echo(f"{prefix}Warning: could not list files: {e}", err=True)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    if files:
        files_lower = {f.lower() for f in files}
        all_files = [f for f in all_files if f.rstrip("/").split("/")[-1].lower() in files_lower]

    for file_path in all_files:
        filename = file_path.rstrip("/").split("/")[-1]
        local_path = output_dir / filename
        try:
            content = client.read_file(file_path)
            local_path.write_text(content, encoding="utf-8")
            click.echo(f"{prefix}  {filename}")
        except MCPError as e:
            click.echo(f"{prefix}  {filename} (error: {e})", err=True)


MODERN_MAIN_LUA = """-- Modern\n\n-- Use this function to perform your initial setup\nfunction setup()\n    print(\"Hello World!\")\nend\n\n-- This function gets called once every frame\nfunction draw()\n    -- This sets a dark background color \n    background(40, 40, 50)\n\n    -- This sets the line thickness\n    style.strokeWidth(5)\n\n    -- Do your drawing here\n    \nend\n"""

MODERN_INFO_PLIST = {
    "Buffer Order": ["Main"],
    "Runtime Type": "modern",
}


def _resolve_project_storage(profile: str) -> str:
    config = load_config(profile)
    if not config.get("host"):
        return "filesystem"

    try:
        return get_client(profile).get_device_state().get("projectStorage", "collections")
    except Exception:
        return "filesystem"


def _resolve_local_project_path(name: str, folder: bool) -> Path:
    path = Path(name).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path

    resolved = path.resolve()
    if folder or resolved.suffix.lower() == ".codea":
        return resolved
    return resolved.with_suffix(".codea")


def _ensure_empty_project_directory(destination: Path) -> None:
    if destination.exists():
        if not destination.is_dir():
            raise click.ClickException(f"Destination already exists and is not a directory: {destination}")
        visible_contents = [child for child in destination.iterdir() if child.name not in {".DS_Store"}]
        if visible_contents:
            raise click.ClickException(f"Destination already exists and is not empty: {destination}")
    else:
        destination.mkdir(parents=True, exist_ok=True)


def _validate_local_template(template: Optional[str]) -> None:
    if template and template.strip().lower() != "modern":
        raise click.ClickException("Only the Modern template is supported for local project creation.")


def _create_local_project(name: str, template: Optional[str], folder: bool) -> Path:
    _validate_local_template(template)
    destination = _resolve_local_project_path(name, folder)
    _ensure_empty_project_directory(destination)

    (destination / "Main.lua").write_text(MODERN_MAIN_LUA, encoding="utf-8")
    with (destination / "Info.plist").open("wb") as f:
        plistlib.dump(MODERN_INFO_PLIST, f)

    return destination


# --- CLI ---

class _Group(click.Group):
    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except MCPError as e:
            raise click.ClickException(str(e))


@click.group(cls=_Group)
@click.option("--wait", is_flag=True, default=False,
              help="Wait for Codea to become reachable before running the command. "
                   "Useful when Codea is backgrounded on your device.")
@click.pass_context
def main(ctx, wait):
    """Codea CLI — connect to Codea on your device.

    Run 'codea COMMAND --help' for help on a specific command.

    Use --wait to block until Codea's Air Code server responds. Handy when
    issuing commands remotely while Codea is in the background — the CLI will
    poll until you switch back to the app.
    """
    ctx.ensure_object(dict)
    ctx.obj["wait"] = wait


@main.command()
@click.option("--timeout", default=5.0, show_default=True, help="Scan duration in seconds.")
@click.option("--profile", default="default", help="Profile name to save as.")
def discover(timeout, profile):
    """Scan the local network for Codea devices and save config."""
    click.echo(f"Scanning for Codea devices ({timeout:.0f}s)...")
    devices = discover_devices(timeout)

    if not devices:
        click.echo("No devices found. Make sure Codea Air Code server is running on your device.")
        return

    for i, d in enumerate(devices, 1):
        click.echo(f"  {i}. {d['name']}  ({d['host']}:{d['port']})")

    if len(devices) == 1:
        choice = 1
    else:
        choice = click.prompt("Select device", type=click.IntRange(1, len(devices)), default=1)

    device = devices[choice - 1]
    save_config(device["host"], device["port"], profile)
    click.echo(f"Saved {device['host']}:{device['port']} as profile '{profile}'.")


@main.command()
@click.option("--host", prompt="Device host/IP", help="Device IP address or hostname.")
@click.option("--port", default=DEFAULT_PORT, prompt="Port", show_default=True)
@click.option("--profile", default="default", help="Profile name.")
def configure(host, port, profile):
    """Manually configure device connection."""
    save_config(host, port, profile)
    click.echo(f"Saved {host}:{port} as profile '{profile}'.")


@main.command()
@click.option("--profile", default="default", help="Profile name.")
def status(profile):
    """Show current device configuration and state."""
    import os, json as _json
    host_env = os.environ.get("CODEA_HOST")
    port_env = os.environ.get("CODEA_PORT")

    # Resolve host/port and source label
    host = port = source = None
    if host_env:
        host = host_env
        port = int(port_env) if port_env else DEFAULT_PORT
        source = "environment variables"
    elif CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = _json.load(f)
        profiles = config.get("profiles", {})
        if profile in profiles:
            p = profiles[profile]
            host = p["host"]
            port = p.get("port", DEFAULT_PORT)
            source = str(CONFIG_FILE)
        elif profiles:
            click.echo(f"Profile '{profile}' not found. Available profiles: {', '.join(profiles)}")
            return

    if host is None:
        click.echo("Not configured. Run 'codea discover' or 'codea configure'.")
        return

    click.echo(f"Host:    {host}")
    click.echo(f"Port:    {port}")
    click.echo(f"Profile: {profile}")
    click.echo(f"Source:  {source}")

    # Fetch live device state
    try:
        client = MCPClient(host, port)
        state = client.get_device_state()
        project_state = state.get("state", "none")
        project_name = state.get("project")
        local_path = state.get("localPath")
        idle_disabled = state.get("idleTimerDisabled", False)
        paused = state.get("paused")

        click.echo("")
        if project_state == "running":
            label = f"Running: {project_name}" if project_name else "Running"
            if paused:
                label += " (paused)"
            click.echo(f"State:   {label}")
        else:
            click.echo("State:   No project running")

        if local_path:
            click.echo(f"Local path: {local_path}")

        click.echo(f"Idle timer: {'off (screen stays on)' if idle_disabled else 'on'}")
    except Exception:
        click.echo("\nState:   (device unreachable)")


@main.command()
@click.option("--profile", default="default", help="Device profile.")
def ls(profile):
    """List all projects on the device as Collection/Project."""
    client = get_client(profile)
    for path in client.list_projects():
        click.echo(path)


@main.command()
@click.argument("project")
@click.argument("files", nargs=-1)
@click.option("--output", "-o", default=None, help="Local output directory (default: ./<project>).")
@click.option("--no-deps", is_flag=True, help="Skip pulling dependencies.")
@click.option("--profile", default="default", help="Device profile.")
def pull(project, files, output, profile, no_deps):
    """Pull a project from the device.

    PROJECT is the project name or Collection/Project.
    Optionally specify individual FILES to pull (e.g. Main.lua Player.lua).
    """
    client = get_client(profile)
    pname = project_name(project)

    output_dir = Path(output) if output else Path(pname)

    if files:
        click.echo(f"Pulling {', '.join(files)} from '{pname}' → {output_dir}/")
        pull_project_files(client, project, output_dir, files=files)
        click.echo("Done.")
        return

    click.echo(f"Pulling '{pname}' → {output_dir}/")
    pull_project_files(client, project, output_dir)

    if not no_deps:
        try:
            deps = client.list_dependencies(project)
        except MCPError:
            deps = []

        if deps:
            click.echo(f"Dependencies: {', '.join(deps)}")
            all_projects = client.list_projects()

            for dep in deps:
                dep_name = dep.split(":")[-1]
                dep_matches = [
                    p for p in all_projects
                    if p.split("/")[-1].lower() == dep_name.lower()
                ]
                if dep_matches:
                    dep_dir = output_dir / "Dependencies" / dep_name
                    click.echo(f"Pulling dependency '{dep_name}' → {dep_dir}/")
                    pull_project_files(client, dep_matches[0], dep_dir, label=dep_name)
                else:
                    click.echo(f"  Dependency '{dep_name}' not found on device.", err=True)

    click.echo("Done.")


@main.command()
@click.argument("project")
@click.argument("files", nargs=-1)
@click.option("--input", "-i", "input_dir", default=None, help="Local directory to push (default: ./<project>).")
@click.option("--profile", default="default", help="Device profile.")
def push(project, files, input_dir, profile):
    """Push local files back to a project on the device.

    PROJECT is the project name or Collection/Project.
    Optionally specify individual FILES to push (e.g. Main.lua Player.lua).
    """
    client = get_client(profile)
    pname = project_name(project)

    source_dir = Path(input_dir) if input_dir else Path(pname)
    if not source_dir.exists():
        raise click.ClickException(f"Directory '{source_dir}' does not exist.")

    def push_file(local_path, file_path, label):
        try:
            try:
                content = local_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Binary file: send as base64
                content = base64.b64encode(local_path.read_bytes()).decode("ascii")
            client.write_file(file_path, content)
            click.echo(f"  {label}")
        except MCPError as e:
            click.echo(f"  {label} (error: {e})", err=True)

    if files:
        for filename in files:
            local_path = source_dir / filename
            if not local_path.exists():
                click.echo(f"  {filename} (not found, skipping)", err=True)
                continue
            file_path = f"{project}/{filename}"
            push_file(local_path, file_path, filename)
        click.echo("Done.")
        return

    click.echo(f"Pushing '{source_dir}/' → '{pname}' on device...")

    for local_path in sorted(source_dir.rglob("*")):
        if not local_path.is_file():
            continue
        relative = local_path.relative_to(source_dir)
        parts = relative.parts

        # Route dependency files back to their project
        if len(parts) >= 3 and parts[0] == "Dependencies":
            dep_name = parts[1]
            filename = "/".join(parts[2:])
            dep_matches = [
                p for p in client.list_projects()
                if p.split("/")[-1].lower() == dep_name.lower()
            ]
            if dep_matches:
                file_path = f"{dep_matches[0]}/{filename}"
            else:
                click.echo(f"  Skipping {relative} (dependency not found)", err=True)
                continue
        else:
            filename = "/".join(parts)
            file_path = f"{project}/{filename}"

        push_file(local_path, file_path, str(relative))

    click.echo("Done.")


@main.command()
@click.argument("project")
@click.option("--profile", default="default", help="Device profile.")
def run(project, profile):
    """Run a Codea project on the device."""
    client = get_client(profile)
    result = client.run_project(project)
    click.echo(result)


@main.command()
@click.option("--profile", default="default", help="Device profile.")
def stop(profile):
    """Stop the running Codea project."""
    client = get_client(profile)
    click.echo(client.stop_project())


@main.command()
@click.option("--profile", default="default", help="Device profile.")
def restart(profile):
    """Restart the running Codea project."""
    client = get_client(profile)
    click.echo(client.text(client.call_tool("restartProject")))


@main.command()
@click.option("--profile", default="default", help="Device profile.")
def pause(profile):
    """Pause the running Codea project."""
    client = get_client(profile)
    client.execute_lua("viewer.paused = true")
    click.echo("Project paused")


@main.command()
@click.option("--profile", default="default", help="Device profile.")
def resume(profile):
    """Resume the paused Codea project."""
    client = get_client(profile)
    client.execute_lua("viewer.paused = false")
    click.echo("Project resumed")


@main.command()
@click.argument("state", type=click.Choice(["on", "off"]), required=False, default=None)
@click.option("--profile", default="default", help="Device profile.")
def paused(state, profile):
    """Get or set the paused state of the running project. Omit to check current state."""
    client = get_client(profile)
    if state is None:
        click.echo(client.text(client.call_tool("getProjectPaused")))
    else:
        client.execute_lua(f"viewer.paused = {'true' if state == 'on' else 'false'}")
        click.echo("paused" if state == "on" else "not paused")


@main.command("exec")
@click.argument("code", required=False)
@click.option("--file", "lua_file", default=None, type=click.Path(exists=True), help="Execute the contents of a Lua file.")
@click.option("--profile", default="default", help="Device profile.")
def exec_lua(code, lua_file, profile):
    """Execute Lua code on the running project.

    Pass code directly as an argument, or use --file to execute a file.

    Examples:
      codea exec "print(scene:findEntity('Player').position)"
      codea exec --file debug.lua
    """
    if lua_file and code:
        raise click.UsageError("Provide either CODE or --file, not both.")
    if not lua_file and not code:
        raise click.UsageError("Provide either CODE or --file.")
    if lua_file:
        code = click.open_file(lua_file).read()
    client = get_client(profile)
    result = client.execute_lua(code)
    if result:
        click.echo(result)


@main.command()
@click.option("--output", "-o", default="screenshot.png", show_default=True, help="Output file path.")
@click.option("--profile", default="default", help="Device profile.")
def screenshot(output, profile):
    """Capture a screenshot of the device screen."""
    client = get_client(profile)
    data = client.capture_screenshot()
    if data is None:
        raise click.ClickException("Screenshot capture failed or not supported.")

    out_path = Path(output)
    out_path.write_bytes(data)
    click.echo(f"Screenshot saved to {out_path} ({len(data):,} bytes)")


@main.command("idle-timer")
@click.argument("state", type=click.Choice(["on", "off"]), required=False, default=None)
@click.option("--profile", default="default", help="Device profile.")
def idle_timer(state, profile):
    """Get or set the device idle timer. Use 'off' to keep the screen awake, 'on' to re-enable it. Omit to check current state."""
    client = get_client(profile)
    if state is None:
        result = client.call_tool("getIdleTimerDisabled")
        click.echo(client.text(result))
    else:
        disabled = state == "off"
        result = client.call_tool("setIdleTimerDisabled", {"disabled": disabled})
        click.echo(client.text(result))


@main.command()
@click.option("--tail", "tail", default=None, type=int, metavar="N", help="Show only the last N lines.")
@click.option("--head", "head", default=None, type=int, metavar="N", help="Show only the first N lines (useful to find the original error in a spammy log).")
@click.option("--follow", "-f", is_flag=True, help="Stream new log lines as they arrive (SSE).")
@click.option("--profile", default="default", help="Device profile.")
def logs(tail, head, follow, profile):
    """Get log output from the running project."""
    client = get_client(profile)
    if follow:
        try:
            for line in client.stream_logs():
                click.echo(line)
        except KeyboardInterrupt:
            pass
        return
    args = {}
    if tail is not None:
        args["tail"] = tail
    if head is not None:
        args["head"] = head
    click.echo(client.text(client.call_tool("getLogs", args or None)))


@main.command("clear-logs")
@click.option("--profile", default="default", help="Device profile.")
def clear_logs(profile):
    """Clear the log buffer."""
    client = get_client(profile)
    click.echo(client.text(client.call_tool("clearLogs")))


@main.command()
@click.argument("name")
@click.option("--collection", default=None, help="Collection to create in (default: first available).")
@click.option("--cloud", is_flag=True, help="Create in iCloud.")
@click.option("--template", default=None, help="Template name for the new project (e.g. Default, Modern).")
@click.option("--folder", is_flag=True, help="For local creation, create a plain folder instead of a .codea bundle.")
@click.option("--profile", default="default", help="Device profile.")
def new(name, collection, cloud, template, folder, profile):
    """Create a new Codea project.

    NAME can be a local project path or Collection/Project for collection-backed targets.
    """
    project_storage = _resolve_project_storage(profile)

    if project_storage == "filesystem":
        if collection:
            raise click.ClickException("--collection is only supported for collection-backed targets.")
        if cloud:
            raise click.ClickException("--cloud is only supported for collection-backed targets.")

        destination = _create_local_project(name, template, folder)
        click.echo(f"Created project '{destination.stem}'. Path: {destination}")
        return

    client = get_client(profile)
    args = {"name": name}
    if template is not None:
        args["template"] = template

    # Parse slash notation: "Documents/MyProject" or "iCloud/Documents/MyProject"
    if "/" in name and collection is None:
        parts = name.split("/")
        if parts[0].lower() == "icloud":
            cloud = True
            parts = parts[1:]
        if len(parts) >= 2:
            collection = "/".join(parts[:-1])
            name = parts[-1]
            args["name"] = name

    if collection:
        args["collection"] = collection
    if cloud:
        args["cloud"] = True
    if folder:
        raise click.ClickException("--folder is only supported for local filesystem-backed targets.")

    result = client.call_tool("createProject", args)
    click.echo(client.text(result))


@main.command()
@click.argument("project")
@click.argument("newname")
@click.option("--profile", default="default", help="Device profile.")
def rename(project, newname, profile):
    """Rename a Codea project on the device."""
    client = get_client(profile)
    result = client.call_tool("renameProject", {"path": project, "newName": newname})
    click.echo(client.text(result))


@main.command()
@click.argument("project")
@click.argument("collection")
@click.option("--profile", default="default", help="Device profile.")
def move(project, collection, profile):
    """Move a Codea project to a different collection.

    PROJECT is the project name or Collection/Project.
    COLLECTION is the destination collection name.

    Example: codea move "Documents/MyGame" Examples
    """
    client = get_client(profile)
    result = client.call_tool("moveProject", {"path": project, "collection": collection})
    click.echo(client.text(result))


@main.command()
@click.argument("project")
@click.option("--profile", default="default", help="Device profile.")
def delete(project, profile):
    """Delete a Codea project from the device."""
    client = get_client(profile)
    pname = project_name(project)
    if not click.confirm(f"Delete '{pname}'? This cannot be undone."):
        return
    result = client.call_tool("deleteProject", {"path": project})
    click.echo(client.text(result))


# --- Collections subgroup ---

@main.group()
def collections():
    """Manage Codea collections."""
    pass


@collections.command("ls")
@click.option("--profile", default="default", help="Device profile.")
def collections_ls(profile):
    """List all collections on the device."""
    client = get_client(profile)
    result = client.call_tool("listCollections")
    for name in client.json_result(result):
        click.echo(name)


@collections.command("new")
@click.argument("name")
@click.option("--profile", default="default", help="Device profile.")
def collections_new(name, profile):
    """Create a new local collection."""
    client = get_client(profile)
    result = client.call_tool("createCollection", {"name": name})
    click.echo(client.text(result))


@collections.command("delete")
@click.argument("name")
@click.option("--profile", default="default", help="Device profile.")
def collections_delete(name, profile):
    """Delete a local collection."""
    client = get_client(profile)
    if not click.confirm(f"Delete collection '{name}'? This cannot be undone."):
        return
    result = client.call_tool("deleteCollection", {"name": name})
    click.echo(client.text(result))


# --- Templates subgroup ---

@main.group()
def templates():
    """Manage Codea project templates."""
    pass


@templates.command("ls")
@click.option("--profile", default="default", help="Device profile.")
def templates_ls(profile):
    """List all available templates (built-in and custom)."""
    client = get_client(profile)
    result = client.call_tool("listTemplates")
    for entry in client.json_result(result):
        click.echo(entry)


@templates.command("add")
@click.argument("project")
@click.option("--name", default=None, help="Name for the template (defaults to the project name).")
@click.option("--profile", default="default", help="Device profile.")
def templates_add(project, name, profile):
    """Copy a project into the custom templates collection."""
    client = get_client(profile)
    args = {"path": project}
    if name:
        args["name"] = name
    result = client.call_tool("addTemplate", args)
    click.echo(client.text(result))


@templates.command("remove")
@click.argument("name")
@click.option("--profile", default="default", help="Device profile.")
def templates_remove(name, profile):
    """Remove a custom template by name."""
    client = get_client(profile)
    if not click.confirm(f"Remove template '{name}'? This cannot be undone."):
        return
    result = client.call_tool("removeTemplate", {"name": name})
    click.echo(client.text(result))


# --- Dependencies subgroup ---

@main.group()
def deps():
    """Manage Codea project dependencies."""
    pass


@deps.command("ls")
@click.argument("project")
@click.option("--profile", default="default", help="Device profile.")
def deps_ls(project, profile):
    """List dependencies of a project."""
    client = get_client(profile)
    for dep in client.list_dependencies(project):
        click.echo(dep)


@deps.command("available")
@click.argument("project")
@click.option("--profile", default="default", help="Device profile.")
def deps_available(project, profile):
    """List projects available to add as dependencies."""
    client = get_client(profile)
    result = client.call_tool("listAvailableDependencies", {"path": project})
    for dep in client.json_result(result):
        click.echo(dep)


@deps.command("add")
@click.argument("project")
@click.argument("dependency")
@click.option("--profile", default="default", help="Device profile.")
def deps_add(project, dependency, profile):
    """Add a dependency to a project."""
    client = get_client(profile)
    result = client.call_tool("addDependency", {"path": project, "dependency": dependency})
    click.echo(client.text(result))


@deps.command("remove")
@click.argument("project")
@click.argument("dependency")
@click.option("--profile", default="default", help="Device profile.")
def deps_remove(project, dependency, profile):
    """Remove a dependency from a project."""
    client = get_client(profile)
    result = client.call_tool("removeDependency", {"path": project, "dependency": dependency})
    click.echo(client.text(result))


@main.command()
@click.argument("project")
@click.argument("code")
@click.option("--profile", default="default", help="Device profile.")
def autocomplete(project, code, profile):
    """Get Lua autocomplete suggestions for a code prefix.

    PROJECT is the project name or Collection/Project.
    CODE is the Lua prefix to complete, e.g. 'asset.' or 'vec2'.

    Example: codea autocomplete "My Game" "asset."
    """
    client = get_client(profile)
    result = client.get_completions(project, code)
    items = result.get("items", [])
    if not items:
        click.echo("(no completions)")
        return

    kind_names = {
        1: "text", 2: "method", 3: "function", 4: "constructor",
        5: "field", 6: "variable", 7: "class", 12: "value",
        14: "keyword", 15: "snippet", 21: "constant",
    }
    for item in items:
        label = item.get("label", "")
        kind = kind_names.get(item.get("kind"), "")
        if kind:
            click.echo(f"{label} ({kind})")
        else:
            click.echo(label)


@main.command()
@click.argument("project")
@click.argument("type", required=False)
@click.option("--profile", default="default", help="Device profile.")
def runtime(project, type, profile):
    """Get or set the runtime type for a project.

    PROJECT is the project name or Collection/Project.
    TYPE is optional: 'legacy' or 'modern'. If omitted, shows the current runtime.

    Examples:
      codea runtime "My Game"           # show current runtime
      codea runtime "My Game" modern    # switch to modern (Carbide)
      codea runtime "My Game" legacy    # switch to legacy
    """
    client = get_client(profile)
    if type is None:
        click.echo(client.get_runtime(project))
    else:
        if type not in ("legacy", "modern"):
            raise click.ClickException("Runtime type must be 'legacy' or 'modern'.")
        click.echo(client.set_runtime(project, type))


def _print_doc_section(title, doc):
    """Print one runtime section (Modern or Legacy) of function documentation."""
    if title:
        click.echo(title)
        click.echo("-" * len(title))

    signatures = doc.get("signatures", [])

    # Show shared description once at the top if all signatures share the same one
    descs = [s.get("description") for s in signatures if s.get("description")]
    shared_desc = descs[0] if descs and all(d == descs[0] for d in descs) else None
    if shared_desc:
        click.echo(shared_desc)
        click.echo()

    for sig in signatures:
        label = sig.get("label", "")
        description = sig.get("description") if not shared_desc else None
        params = sig.get("parameters", [])
        returns = sig.get("returns", [])

        click.echo(f"  {label}")

        if description:
            click.echo(f"    {description}")

        for param in params:
            name = param.get("name", "")
            ptype = param.get("type")
            desc = param.get("description")
            optional = param.get("optional", False)
            parts = [f"    {name}"]
            if ptype:
                parts.append(ptype)
            if desc:
                parts.append(f"– {desc}")
            elif optional:
                parts.append("(optional)")
            click.echo("  ".join(parts))

        for ret in returns:
            rtype = ret.get("type")
            rdesc = ret.get("description")
            if rtype or rdesc:
                parts = ["→"]
                if rtype:
                    parts.append(rtype)
                if rdesc:
                    parts.append(f"– {rdesc}")
                click.echo("    " + " ".join(parts))

        click.echo()

    examples = doc.get("examples", [])
    if examples:
        click.echo("Example:" if len(examples) == 1 else "Examples:")
        for ex in examples:
            if ex.get("title"):
                click.echo(f"  {ex['title']}")
            for line in ex.get("code", "").splitlines():
                click.echo(f"    {line}")
            click.echo()


@main.command()
@click.argument("function_name")
@click.option("--legacy", "filter_runtime", flag_value="legacy", help="Show only legacy documentation.")
@click.option("--modern", "filter_runtime", flag_value="modern", help="Show only modern (Carbide) documentation.")
@click.option("--project", default=None, help="Auto-select docs based on the project's runtime type.")
@click.option("--profile", default="default", help="Device profile.")
def doc(function_name, filter_runtime, project, profile):
    """Look up Codea API documentation for a function.

    Shows both legacy and modern (Carbide) documentation by default.
    Use --legacy or --modern to filter to one runtime, or use --project
    to automatically show only the docs relevant to a project's runtime.

    Examples:
      codea doc background
      codea doc background --modern
      codea doc background --project "My Game"
      codea doc sprite --legacy
    """
    client = get_client(profile)

    # Resolve --project to a runtime filter (only if not already explicitly set)
    if project and not filter_runtime:
        filter_runtime = client.get_runtime(project)

    result = client.get_function_help(function_name)
    modern = result.get("modern")
    legacy = result.get("legacy")

    if filter_runtime == "modern":
        legacy = None
    elif filter_runtime == "legacy":
        modern = None

    if not modern and not legacy:
        if filter_runtime:
            raise click.ClickException(
                f"No {filter_runtime} documentation found for '{function_name}'."
            )
        raise click.ClickException(f"No documentation found for '{function_name}'.")

    name = result.get("name", function_name)
    click.echo(name)
    click.echo("=" * len(name))

    if modern and legacy:
        click.echo()
        _print_doc_section("Modern", modern)
        _print_doc_section("Legacy", legacy)
    elif modern:
        click.echo()
        _print_doc_section(None, modern)
    else:
        click.echo()
        _print_doc_section(None, legacy)

    see_also = result.get("seeAlso", [])
    if see_also:
        click.echo("See also: " + ", ".join(see_also))

    modern_url = result.get("modernDocUrl")
    legacy_url = result.get("legacyDocUrl")
    if modern_url and legacy_url:
        click.echo(f"\nDocs:\n  Modern: {modern_url}\n  Legacy: {legacy_url}")
    elif modern_url:
        click.echo(f"\nDocs: {modern_url}")
    elif legacy_url:
        click.echo(f"\nDocs: {legacy_url}")


@main.command("search-doc")
@click.argument("query")
@click.option("--legacy", "filter_runtime", flag_value="legacy", help="Show only legacy results.")
@click.option("--modern", "filter_runtime", flag_value="modern", help="Show only modern (Carbide) results.")
@click.option("--project", default=None, help="Auto-select runtime based on the project's runtime type.")
@click.option("--profile", default="default", help="Device profile.")
def search_doc(query, filter_runtime, project, profile):
    """Search Codea API documentation by keyword.

    Searches function names, descriptions, and help text across both legacy
    and modern (Carbide) runtimes.

    Examples:
      codea search-doc storage
      codea search-doc "draw sprite"
      codea search-doc physics --modern
      codea search-doc physics --project "My Game"
    """
    client = get_client(profile)

    if project and not filter_runtime:
        filter_runtime = client.get_runtime(project)

    results = client.search_docs(query)

    if filter_runtime:
        results = [r for r in results if r.get("runtime") in (filter_runtime, "both")]

    if not results:
        if filter_runtime:
            click.echo(f"No {filter_runtime} documentation found matching '{query}'.")
        else:
            click.echo(f"No documentation found matching '{query}'.")
        return

    for item in results:
        name = item.get("name", "")
        raw_desc = item.get("description", "").replace("\n", " ")
        desc = (raw_desc[:80] + "…") if len(raw_desc) > 80 else raw_desc
        runtime = item.get("runtime", "")
        tag = f"[{runtime}]" if runtime else ""
        if desc:
            click.echo(f"  {name}  – {desc}  {tag}")
        else:
            click.echo(f"  {name}  {tag}")

    click.echo("\nUse 'codea doc <function>' for complete documentation.")
