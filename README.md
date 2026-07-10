# patchbay

<p align="center">
  <img src="assets/patchbay-logo.svg" alt="patchbay" width="160">
</p>

Route your Spotify library like a studio signal chain: one place to send liked songs into the right playlists, without digging through the app.

## Why "patchbay"?

In a studio, a **patchbay** is a central panel that consolidates all your audio connections — instruments, synths, preamps, effects — into one front panel. Instead of reaching behind heavy racks to rewire cables, you route any signal by plugging a short patch cable into the front. This project is that idea applied to your Spotify library: your Liked Songs and playlists surface in one place, and you "patch" each song into the playlist where it belongs (party, roadtrip, focus, coffee…) with quick, deliberate moves instead of rewiring by hand in the app.

Concretely, it's a small, self-authored MCP server that lets **Claude** (Claude Code or the Claude Desktop app) do the routing: read your Liked Songs and playlists, create playlists, add and remove tracks, and clear songs out of Liked Songs. Built with **uv** and modern Python, ~300 lines you can read top to bottom before trusting it.

The "smart" part — deciding which song belongs in *focus* vs *party* vs *roadtrip* — happens in your conversation with Claude, using its knowledge of the actual music. Spotify removed the audio-features / energy / valence endpoints for new apps in November 2024, so numeric mood-sorting via the API is no longer possible; patchbay doesn't need it.

## Project structure

```text
patchbay/
├── pyproject.toml          # uv project + dependencies + entry points
├── .python-version         # pins Python 3.14
├── .env.example            # copy to .env and add your Client ID
├── .gitignore
├── README.md
└── src/
    └── patchbay/
        ├── __init__.py
        ├── config.py       # loads env vars / .env, holds constants
        ├── _http.py        # tiny urllib-based HTTP helper (stdlib only)
        ├── auth.py         # `patchbay-auth`: one-time browser login (PKCE)
        ├── client.py       # Spotify API client: tokens, HTTP calls, library ops
        └── server.py       # `patchbay`: the MCP server Claude Desktop runs
```

Two entry points are defined in `pyproject.toml`:

- `patchbay-auth` → `patchbay.auth:main` — run once to authorize.
- `patchbay` → `patchbay.server:main` — the MCP server (launched by Claude Desktop).

## Credentials & environment variables

patchbay reads configuration from environment variables, loaded from a local `.env` file (parsed by a small standard-library loader — no third-party dependency). Copy the template and fill in one value:

```bash
cp .env.example .env
```

| Variable | Required | Purpose |
|----------|----------|---------|
| `SPOTIFY_CLIENT_ID` | yes | Your app's Client ID — Spotify's equivalent of an "API key". |
| `SPOTIFY_REDIRECT_URI` | no | Defaults to `http://127.0.0.1:8888/callback`. Must match the Dashboard exactly. |
| `SPOTIFY_TOKEN_PATH` | no | Override where tokens are cached. Defaults to `~/.config/patchbay/token.json`, falling back to `~/.patchbay/token.json` (chmod 600). |
| `SPOTIFY_CLIENT_SECRET` | no | Unused — PKCE needs no secret. Present only if you switch flows. |

`.env` and the token file are git-ignored. There is **no client secret** to store: the PKCE flow authorizes using only your Client ID.

## Setup

### 1. Create your Spotify app (one-time, free)

1. Open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create app** and give it any name and description.
3. Add this exact **Redirect URI**: `http://127.0.0.1:8888/callback` (loopback IP `127.0.0.1`, not `localhost` — Spotify is strict here).
4. Under **"Which API/SDKs are you planning to use?"**, select **Web API**.
5. Save, then copy the **Client ID** into your `.env`.

> Development Mode requires the app owner to have **Premium** (you do) and allows up to 5 authorized users — fine for personal use.

### 2. Install with uv

From the project root:

```bash
uv sync
```

That creates `.venv` and installs the one dependency, `mcp` (the MCP SDK); everything else is standard library. (Install uv itself from https://docs.astral.sh/uv/ if you don't have it.)

### 3. Authorize once

```bash
uv run patchbay-auth
```

Your browser opens; approve access. Tokens land in `~/.config/patchbay/token.json` (or `~/.patchbay/token.json` as a fallback). Repeat only if you change scopes or revoke access.

### 4. Register patchbay with your Claude client

Both clients launch patchbay the same way — `uv --directory <project root> run patchbay`. The `<project root>` is the folder containing `pyproject.toml` (where this README lives), **not** `src/patchbay`. Using `uv --directory` means uv manages the virtual environment and loads your `.env` automatically. Use an **absolute** path.

If `uv` isn't on the client's PATH, use its absolute path instead (find it with `which uv` / `where uv`).

#### Claude Code (CLI)

Register the server with a single command. Flags like `--scope` go *before* the name; everything after `--` is the command used to start the server:

```bash
claude mcp add --scope user patchbay -- uv --directory /ABSOLUTE/PATH/patchbay run patchbay
```

`--scope user` makes patchbay available in every Claude Code session, on any project — the right choice for a personal tool. (Use `--scope project` only if you want it committed to a repo's `.mcp.json` and shared with a team.)

Verify and use:

```bash
claude mcp list          # health-checks servers; look for: patchbay ✓ Connected
claude mcp get patchbay    # shows its config and which scope file it lives in
```

Inside a session, `/mcp` shows server status. stdio tools are discovered at session start, so if you added patchbay mid-session, start a new session to pick up its tools. If `list` shows a failure, run `uv run patchbay` by hand first — it will fail the same way there, so fix that first. Some shells don't expand `~` in the stored config, so if the connection fails, re-add using a fully absolute path (e.g. `/Users/you/projects/patchbay`) rather than `~/...`.

#### Claude Desktop (app)

Open Claude Desktop → **Settings → Developer → Edit Config**. This opens `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`).

Add a `patchbay` server:

```json
{
  "mcpServers": {
    "patchbay": {
      "command": "uv",
      "args": ["--directory", "/ABSOLUTE/PATH/patchbay", "run", "patchbay"]
    }
  }
}
```

You can also pass credentials inline instead of via `.env`:

```json
      "env": { "SPOTIFY_CLIENT_ID": "your_client_id_here" }
```

Fully **quit and restart** Claude Desktop (not just close the window). A tools indicator appears near the message box; click it to see patchbay's nine tools.

## Using it

Talk to Claude in plain language:

- "Read my liked songs and propose occasion playlists — party, roadtrip, focus, coffee, work — and show me the plan before changing anything."
- "Create those playlists and add the songs."
- "Now remove from Liked Songs everything you just filed away."

Each write asks for your approval in Claude Desktop. Recommended order: build and fill playlists, confirm they look right, *then* remove from Liked Songs — patchbay keeps those as separate steps so a song is only unliked once it's safely in a playlist.

## Tools

| Tool | What it does |
|------|--------------|
| `get_liked_songs` | Read Liked Songs (paginated). |
| `get_playlists` | List your playlists. |
| `get_playlist_tracks` | Read tracks in a playlist you own/collaborate on. |
| `search_tracks` | Find tracks in Spotify's catalog. |
| `create_playlist` | Create a new (private by default) playlist. |
| `add_tracks` | Add tracks by URI (batches of 100). |
| `remove_tracks` | Remove tracks from a playlist by URI. |
| `delete_playlist` | Delete a playlist you own (unfollows it from your library). |
| `remove_liked_songs` | Remove tracks from Liked Songs by ID (batches of 50). |

## Testing

Two ways to sanity-check patchbay without going through Claude:

**Live smoke check** — hits the real Spotify API, read-only, no writes:

```bash
uv run patchbay-check
```

Prints your display name, 5 liked songs, and 5 tracks from your first owned playlist. Exits non-zero on any API error. Fastest way to notice endpoint drift (e.g. the Nov 2024 `/tracks` → `/items` rename) before it surfaces in a live conversation.

**Offline unit + fixture suite** — no network needed:

```bash
uv run python -m unittest discover tests
```

Under `tests/fixtures/` are identity-scrubbed captures of real Spotify responses. If Spotify changes a shape, re-record and the shape tests will flag the parts of `client.py` that need updating:

```bash
uv run python tests/record_fixtures.py
```

The suite also runs on every push and PR via `.github/workflows/tests.yml`.

## Troubleshooting

- **Test the server by hand first:** `uv run patchbay` should start without error. If it fails there, it will fail the same way under any client — fix that first.
- **Tools don't appear (Claude Code):** run `claude mcp list` from any directory to health-check it, and `claude mcp get patchbay` to see its scope/config. stdio tools load at session start, so start a new session after adding it. If the path uses `~`, re-add with a fully absolute path. Make sure `uv` is on PATH (or use its absolute path in the command).
- **Tools don't appear (Claude Desktop):** fully quit and reopen the app. Confirm the config path is absolute and the JSON has no trailing commas. Logs live in `~/Library/Logs/Claude/` (macOS) or `%APPDATA%\Claude\logs\` (Windows) — see `mcp-server-patchbay.log`.
- **`No token file` / 401:** run `uv run patchbay-auth`.
- **`remove_liked_songs` returns 403/404:** Spotify began consolidating library writes in Feb 2026. If a newly created app rejects `DELETE /me/tracks`, edit `src/patchbay/client.py` → `remove_liked_songs` and switch that one call to Spotify's current library-removal endpoint per the [Feb 2026 migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide). The batching logic is unchanged; everything else uses stable endpoints.
- **Empty playlist contents:** Spotify returns items only for playlists you own or collaborate on.

## Security notes

- No client secret stored (PKCE). The only on-disk secret is the token cache at `~/.config/patchbay/token.json` (or the `~/.patchbay` fallback), written with `600` permissions.
- Scopes are limited to library + playlist read/write. No playback, no email, no other users' data.
- Every tool takes explicit IDs/URIs — the server never decides what to change on its own, and Claude Desktop prompts you to approve each action.
