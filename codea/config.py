import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".codea"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_PORT = 18513


def load_config(profile: str = "default") -> dict:
    """Load config with precedence: env vars > config file."""
    host = os.environ.get("CODEA_HOST")
    port = os.environ.get("CODEA_PORT")

    if host:
        return {"host": host, "port": int(port) if port else DEFAULT_PORT}

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        profiles = config.get("profiles", {})
        if profile in profiles:
            return profiles[profile]

    return {}


def save_config(host: str, port: int, profile: str = "default"):
    CONFIG_DIR.mkdir(exist_ok=True)

    config = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = json.load(f)

    config.setdefault("profiles", {})[profile] = {"host": host, "port": port}

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_connection(profile: str = "default") -> tuple[str, int]:
    """Return (host, port) or raise if not configured."""
    config = load_config(profile)
    if not config.get("host"):
        raise click_error(
            "No device configured. Run 'codea discover' or 'codea configure' first.\n"
            "Or set CODEA_HOST environment variable."
        )
    return config["host"], config.get("port", DEFAULT_PORT)


def click_error(message: str):
    import click
    raise click.ClickException(message)
