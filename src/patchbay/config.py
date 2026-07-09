"""Configuration, loaded from environment variables (and a local .env file)."""

import os
from pathlib import Path


def _load_env_file(path: Path = Path(".env")) -> None:
    """Load KEY=value pairs from a .env file in the working directory, if present.

    Real environment variables always win — this only fills in what's unset.
    When Claude launches the server via `uv --directory <proj> run patchbay`, the
    working directory is the project root, so the project's .env is picked up.
    """
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip("\"'"))


_load_env_file()

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()  # unused with PKCE
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")


def _resolve_token_path() -> Path:
    """Where to cache tokens.

    Order of preference:
      1. SPOTIFY_TOKEN_PATH, if set (explicit override).
      2. ~/.config/patchbay/token.json  (respects XDG_CONFIG_HOME) — the default.
      3. ~/.patchbay/token.json         (fallback).

    An existing token file takes precedence over the default so that anyone who
    authorized under an older path keeps working without re-authorizing. On a
    fresh install we prefer the ~/.config location, dropping to ~/.patchbay only
    if that directory can't be created.
    """
    override = os.environ.get("SPOTIFY_TOKEN_PATH")
    if override:
        return Path(override).expanduser()

    xdg = os.environ.get("XDG_CONFIG_HOME")
    primary = (Path(xdg).expanduser() if xdg else Path.home() / ".config") / "patchbay" / "token.json"
    fallback = Path.home() / ".patchbay" / "token.json"

    if primary.exists():
        return primary
    if fallback.exists():
        return fallback

    try:  # fresh install: prefer ~/.config, fall back if it isn't usable
        primary.parent.mkdir(parents=True, exist_ok=True)
        return primary
    except OSError:
        return fallback


TOKEN_PATH = _resolve_token_path()

# Only the scopes patchbay actually uses — nothing more.
SCOPES = (
    "user-library-read "
    "user-library-modify "
    "playlist-read-private "
    "playlist-modify-private "
    "playlist-modify-public"
)

API = "https://api.spotify.com/v1"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
