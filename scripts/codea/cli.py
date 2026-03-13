import json
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import click

from .config import load_config, save_config, DEFAULT_PORT
from .discover import discover_devices
from .mcp_client import MCPClient, MCPError


# --- Helpers ---

def get_client(profile: str) -> MCPClient:
    config = load_config(profile)
    if not config.get("host"):
        raise click.ClickException(
            "No device configured. Run 'codea discover' or 'codea configure' first.\n"
            "Or set CODEA_HOST (and optionally CODEA_PORT) environment variables."
        )
    return MCPClient(config["host"], config.get("port", DEFAULT_PORT))


def uri_logical_path(uri: str) -> str:
    """Extract logical path from codea:// URI.

    Examples:
      codea://host/Codea/Documents/Morse       -> "Documents/Morse"
      codea://host/Codea/iCloud/Documents/Foo  -> "iCloud/Documents/Foo"
    """
    path = urlparse(uri).path  # /Codea/Documents/Morse
    parts = path.strip("/").split("/")
    return "/".join(parts[1:])  # drop leading "Codea"


def find_project_uri(client: MCPClient, name: str) -> str:
    """Find a project URI by name, with optional Collection/ or iCloud/Collection/ prefix."""
    projects = client.list_projects()
    name_lower = name.lower()

    if "/" in name:
        # Exact logical path match (e.g. "Documents/Morse" or "iCloud/Documents/Foo")
        matches = [p for p in projects if uri_logical_path(p).lower() == name_lower]
    else:
        # Match by project name only
        matches = [p for p in projects if uri_logical_path(p).split("/")[-1].lower() == name_lower]

    if not matches:
        available = [uri_logical_path(p) for p in projects]
        raise click.ClickException(
            f"Project '{name}' not found.\nAvailable projects: {', '.join(sorted(available))}"
        )
    if len(matches) > 1:
        paths = [uri_logical_path(p) for p in matches]
        raise click.ClickException(
            f"Multiple projects named '{name}':\n" + "\n".join(paths) +
            "\nUse Collection/Project notation to disambiguate (e.g. 'Documents/Morse')."
        )
    return matches[0]


def pull_project_files(client: MCPClient, project_uri: str, output_dir: Path, files: tuple = (), label: str = ""):
    """Pull files from a project URI into output_dir. If files is given, only pull those."""
    prefix = f"[{label}] " if label else ""
    try:
        all_files = client.list_files(project_uri)
    except MCPError as e:
        click.echo(f"{prefix}Warning: could not list files: {e}", err=True)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    if files:
        files_lower = {f.lower() for f in files}
        all_files = [f for f in all_files if f.rstrip("/").split("/")[-1].lower() in files_lower]

    for file_uri in all_files:
        filename = file_uri.rstrip("/").split("/")[-1]
        local_path = output_dir / filename
        try:
            content = client.read_file(file_uri)
            local_path.write_text(content, encoding="utf-8")
            click.echo(f"{prefix}  {filename}")
        except MCPError as e:
            click.echo(f"{prefix}  {filename} (error: {e})", err=True)


# --- CLI ---

@click.group()
def main():
    """Codea CLI — connect to Codea on your device.

    Run 'codea COMMAND --help' for help on a specific command.
    """
    pass


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
@click.option("--profile", default="default", help="Device profile.")
def ls(profile):
    """List all projects on the device as Collection/Project."""
    client = get_client(profile)
    for uri in client.list_projects():
        click.echo(uri_logical_path(uri))


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
    project_uri = find_project_uri(client, project)
    project_name = uri_logical_path(project_uri).split("/")[-1]

    output_dir = Path(output) if output else Path(project_name)

    if files:
        click.echo(f"Pulling {', '.join(files)} from '{project_name}' → {output_dir}/")
        pull_project_files(client, project_uri, output_dir, files=files)
        click.echo("Done.")
        return

    click.echo(f"Pulling '{project_name}' → {output_dir}/")
    pull_project_files(client, project_uri, output_dir)

    if not no_deps:
        try:
            deps = client.list_dependencies(project_uri)
        except MCPError:
            deps = []

        if deps:
            click.echo(f"Dependencies: {', '.join(deps)}")
            all_projects = client.list_projects()

            for dep in deps:
                dep_name = dep.split(":")[-1]
                dep_uri_matches = [
                    p for p in all_projects
                    if uri_logical_path(p).split("/")[-1].lower() == dep_name.lower()
                ]
                if dep_uri_matches:
                    dep_uri = dep_uri_matches[0]
                    dep_dir = output_dir / "Dependencies" / dep_name
                    click.echo(f"Pulling dependency '{dep_name}' → {dep_dir}/")
                    pull_project_files(client, dep_uri, dep_dir, label=dep_name)
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
    project_uri = find_project_uri(client, project)
    project_name = uri_logical_path(project_uri).split("/")[-1]

    source_dir = Path(input_dir) if input_dir else Path(project_name)
    if not source_dir.exists():
        raise click.ClickException(f"Directory '{source_dir}' does not exist.")

    if files:
        for filename in files:
            local_path = source_dir / filename
            if not local_path.exists():
                click.echo(f"  {filename} (not found, skipping)", err=True)
                continue
            file_uri = f"{project_uri}/{filename}"
            try:
                content = local_path.read_text(encoding="utf-8")
                client.write_file(file_uri, content)
                click.echo(f"  {filename}")
            except (MCPError, UnicodeDecodeError) as e:
                click.echo(f"  {filename} (error: {e})", err=True)
        click.echo("Done.")
        return

    click.echo(f"Pushing '{source_dir}/' → '{project_name}' on device...")

    for local_path in sorted(source_dir.rglob("*")):
        if not local_path.is_file():
            continue
        relative = local_path.relative_to(source_dir)
        parts = relative.parts

        # Route dependency files back to their project
        if len(parts) >= 3 and parts[0] == "Dependencies":
            dep_name = parts[1]
            filename = "/".join(parts[2:])
            dep_uri_matches = [
                p for p in client.list_projects()
                if uri_logical_path(p).split("/")[-1].lower() == dep_name.lower()
            ]
            if dep_uri_matches:
                file_uri = f"{dep_uri_matches[0]}/{filename}"
            else:
                click.echo(f"  Skipping {relative} (dependency not found)", err=True)
                continue
        else:
            filename = "/".join(parts)
            file_uri = f"{project_uri}/{filename}"

        try:
            content = local_path.read_text(encoding="utf-8")
            client.write_file(file_uri, content)
            click.echo(f"  {relative}")
        except (MCPError, UnicodeDecodeError) as e:
            click.echo(f"  {relative} (error: {e})", err=True)

    click.echo("Done.")


@main.command()
@click.argument("project")
@click.option("--profile", default="default", help="Device profile.")
def run(project, profile):
    """Run a Codea project on the device."""
    client = get_client(profile)
    project_uri = find_project_uri(client, project)
    result = client.run_project(project_uri)
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


@main.command("exec")
@click.argument("code")
@click.option("--profile", default="default", help="Device profile.")
def exec_lua(code, profile):
    """Execute Lua code on the running project.

    Example: codea exec "print(scene:findEntity('Player').position)"
    """
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
@click.argument("state", type=click.Choice(["on", "off"]))
@click.option("--profile", default="default", help="Device profile.")
def idle_timer(state, profile):
    """Enable or disable the device idle timer. Use 'off' to keep the screen awake."""
    client = get_client(profile)
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
@click.option("--profile", default="default", help="Device profile.")
def new(name, collection, cloud, profile):
    """Create a new Codea project on the device.

    NAME can be just a project name or Collection/Project to specify a collection.
    """
    client = get_client(profile)

    # Parse slash notation: "Documents/MyProject" or "iCloud/Documents/MyProject"
    if "/" in name and collection is None:
        parts = name.split("/")
        if parts[0].lower() == "icloud":
            cloud = True
            parts = parts[1:]
        if len(parts) >= 2:
            collection = "/".join(parts[:-1])
            name = parts[-1]

    args = {"name": name}
    if collection:
        args["collection"] = collection
    if cloud:
        args["cloud"] = True

    result = client.call_tool("createProject", args)
    click.echo(client.text(result))


@main.command()
@click.argument("project")
@click.argument("newname")
@click.option("--profile", default="default", help="Device profile.")
def rename(project, newname, profile):
    """Rename a Codea project on the device."""
    client = get_client(profile)
    project_uri = find_project_uri(client, project)
    result = client.call_tool("renameProject", {"path": project_uri, "newName": newname})
    click.echo(client.text(result))


@main.command()
@click.argument("project")
@click.option("--profile", default="default", help="Device profile.")
def delete(project, profile):
    """Delete a Codea project from the device."""
    client = get_client(profile)
    project_uri = find_project_uri(client, project)
    project_name = uri_logical_path(project_uri).split("/")[-1]
    if not click.confirm(f"Delete '{project_name}'? This cannot be undone."):
        return
    result = client.call_tool("deleteProject", {"path": project_uri})
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
    project_uri = find_project_uri(client, project)
    for dep in client.list_dependencies(project_uri):
        click.echo(dep)


@deps.command("available")
@click.argument("project")
@click.option("--profile", default="default", help="Device profile.")
def deps_available(project, profile):
    """List projects available to add as dependencies."""
    client = get_client(profile)
    project_uri = find_project_uri(client, project)
    result = client.call_tool("listAvailableDependencies", {"path": project_uri})
    for dep in client.json_result(result):
        click.echo(dep)


@deps.command("add")
@click.argument("project")
@click.argument("dependency")
@click.option("--profile", default="default", help="Device profile.")
def deps_add(project, dependency, profile):
    """Add a dependency to a project."""
    client = get_client(profile)
    project_uri = find_project_uri(client, project)
    result = client.call_tool("addDependency", {"path": project_uri, "dependency": dependency})
    click.echo(client.text(result))


@deps.command("remove")
@click.argument("project")
@click.argument("dependency")
@click.option("--profile", default="default", help="Device profile.")
def deps_remove(project, dependency, profile):
    """Remove a dependency from a project."""
    client = get_client(profile)
    project_uri = find_project_uri(client, project)
    result = client.call_tool("removeDependency", {"path": project_uri, "dependency": dependency})
    click.echo(client.text(result))
