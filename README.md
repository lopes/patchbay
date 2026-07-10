# patchbay

<p align="center">
  <img src="assets/patchbay-logo.svg" alt="patchbay" width="160">
</p>

A personal MCP server that exposes Spotify library operations — Liked Songs, playlists, search, add/remove — to **Claude** (Code or Desktop) over stdio.

In a studio, a *patchbay* is the front panel where every audio connection lands, so signals get rerouted with a short cable instead of by rewiring the whole rack. Same idea applied to a Spotify library: liked songs and playlists surface in one place, and each song gets "patched" into the occasion it belongs to (working, driving, coffee, party) through a conversation with Claude.

The categorization judgement lives in the conversation, using Claude's knowledge of the music. Spotify removed audio-features (energy / valence / BPM) for new apps in November 2024, so numeric mood-sorting via the API is no longer possible — patchbay doesn't need it.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) for dependency + venv management
- A Spotify account with **Premium** (Development Mode apps require Premium on the app owner)
- Either Claude Code (CLI) or Claude Desktop

Only one runtime dependency: `mcp>=1.2.0`. Everything else is standard library.

## Setup

### 1. Create a Spotify app

1. Open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. **Create app** — any name and description.
3. Add this exact **Redirect URI**: `http://127.0.0.1:8888/callback` (loopback IP `127.0.0.1`, not `localhost` — Spotify is strict).
4. Under **"Which API/SDKs are you planning to use?"**, select **Web API**.
5. Save. Copy the **Client ID**.

Development Mode allows up to 5 authorized users — enough for personal use, no verification needed.

### 2. Configure

```bash
cp .env.example .env       # then paste the Client ID
uv sync                    # creates .venv, installs the one dep
```

| Variable | Required | Purpose |
|----------|----------|---------|
| `SPOTIFY_CLIENT_ID` | yes | App's Client ID. |
| `SPOTIFY_REDIRECT_URI` | no | Defaults to `http://127.0.0.1:8888/callback`. Must match the Dashboard exactly. |
| `SPOTIFY_TOKEN_PATH` | no | Override for the cached token. Defaults to `~/.config/patchbay/token.json` (chmod 600), with a fallback to `~/.patchbay/token.json`. |

There is no client secret. PKCE authorizes with the Client ID alone; the only on-disk secret is the token cache.

### 3. Authorize (one-time)

```bash
uv run patchbay-auth
```

A browser window opens; approve access. Tokens land in the path above. Re-run only if scopes change or access is revoked.

### 4. Register with Claude

Both clients launch patchbay the same way: `uv --directory <project root> run patchbay`. Use an **absolute** path to the folder containing `pyproject.toml` (not `src/patchbay`).

**Claude Code:**

```bash
claude mcp add --scope user patchbay -- uv --directory /ABSOLUTE/PATH/patchbay run patchbay
```

`--scope user` makes patchbay available in every session on every project. Use `--scope project` only when sharing via a repo's `.mcp.json`.

Verify: `claude mcp list` (look for `patchbay ✓ Connected`).

**Claude Desktop:** open **Settings → Developer → Edit Config** and add:

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

Fully **quit and restart** Claude Desktop (not just close the window). A tools indicator appears near the message box.

## Usage

Talk to Claude in plain language:

- "Read my liked songs and propose occasion playlists — party, driving, focus, coffee — and show the plan before changing anything."
- "Create those playlists and add the songs."
- "Now remove from Liked Songs everything that got filed."

Every write asks for approval. Recommended sequence: create → populate → verify → empty Liked. patchbay keeps these as separate operations so a song is only unliked once it's safely in a playlist.

## Bundled Claude skills

Under `.claude/skills/`, the repo ships two workflows that ride on top of the MCP server:

- **`/reorg-playlists`** — full library teardown into purpose-driven, mood/occasion playlists. Discourages genre or year splits. Phased: context → discovery → planning → assignment → review → execution, with approval between phases.
- **`/audit-playlists`** — monthly hygiene check. Reports bloat, cross-remaster duplicates, over-tagged tracks, and Liked Songs accumulation. Proposes fixes; never writes without approval.

Both are picked up automatically by Claude when the session starts in this repo.

## Tools

| Tool | What it does |
|------|--------------|
| `get_liked_songs` | Read Liked Songs (paginated). Optional `dedupe=True` collapses remaster/live/version variants. |
| `get_playlists` | List playlists. |
| `get_playlist_tracks` | Read tracks in an owned/collaborated playlist. Optional `dedupe=True`. |
| `search_tracks` | Find tracks in Spotify's catalog. |
| `create_playlist` | Create a new (private by default) playlist. |
| `add_tracks` | Add tracks by URI (batches of 100). |
| `remove_tracks` | Remove tracks from a playlist by URI (batches of 100). |
| `delete_playlist` | Delete a playlist (unfollows it from the current user's library). |
| `remove_liked_songs` | Remove tracks from Liked Songs by ID (batches of 40, `DELETE /me/library`). |

Track shape returned by reads: `{id, uri, name, artists, album, isrc, release_year}`. `isrc` and `release_year` enable reliable dedup across remasters and era-aware categorization.

## Development

**Offline test suite** — stdlib `unittest`, ~11ms, no network:

```bash
uv run python -m unittest discover tests
```

Fixtures under `tests/fixtures/` are identity-scrubbed captures of real Spotify responses. If Spotify changes a shape, re-record and the shape tests flag the parts of `client.py` that need updating:

```bash
uv run python tests/record_fixtures.py
```

**Live smoke check** — hits the real API, read-only:

```bash
uv run patchbay-check
```

Prints the user's display name, 5 Liked Songs, and 5 tracks from the first owned playlist. Fastest way to notice endpoint drift before it surfaces in a live conversation.

The suite runs on every push and PR via `.github/workflows/tests.yml`.

## Troubleshooting

- **Test the server by hand first:** `uv run patchbay` should start without error. If it fails there, it fails the same way under any client — fix that first.
- **Tools don't appear (Claude Code):** `claude mcp list` health-checks each server; `claude mcp get patchbay` shows its config. stdio tools load at session start, so a new session is required after registration. If the path uses `~`, re-add with a fully absolute path. Ensure `uv` is on `PATH` (or use its absolute path).
- **Tools don't appear (Claude Desktop):** fully quit and reopen the app. Confirm the config path is absolute and the JSON has no trailing commas. Logs live in `~/Library/Logs/Claude/` (macOS) or `%APPDATA%\Claude\logs\` (Windows) — see `mcp-server-patchbay.log`.
- **`No token file` / 401:** run `uv run patchbay-auth`.
- **`remove_liked_songs` returns 403/404:** the Feb 2026 library-write consolidation retired `DELETE /me/tracks`; patchbay uses `DELETE /me/library` per Spotify's [migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide). If 403/404 persists, re-run `patchbay-auth` — Spotify occasionally requires re-consent after endpoint moves.
- **Empty playlist contents:** Spotify returns items only for playlists the current user owns or collaborates on.

## Security

- **No client secret stored.** PKCE authorizes with the Client ID alone. The only on-disk secret is the token cache, written with `600` permissions.
- **Minimal scopes:** library + playlist read/write. No playback, no email, no other users' data.
- **No autonomous decisions:** every tool takes explicit IDs/URIs. The server never chooses what to change; the client (Claude Code / Desktop) prompts for approval on each write.

Report a security issue by opening a private advisory on the repository. This project has no dedicated security contact.

## Contributing

This is a personal project, but PRs are welcome. Before submitting:

- Run the offline suite: `uv run python -m unittest discover tests`. Add or update tests for any new behavior.
- Follow the commit style: [Scoped Commits](https://scopedcommits.com/) — `<scope>: <description>`, one sentence, no Conventional Commits prefixes and no `Co-Authored-By` footers. Mirror the existing history (`git log --oneline`).
- See `CLAUDE.md` for architecture notes and non-obvious behaviors before non-trivial changes.

## License

MIT — see [LICENSE](LICENSE).
