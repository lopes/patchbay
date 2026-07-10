# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal MCP server that exposes Spotify library operations (Liked Songs, playlists, search, add/remove) to Claude over stdio. Python 3.14, one runtime dependency (`mcp>=1.2.0`); everything else is standard library. ~330 lines of Python across six files — read it top to bottom before making non-trivial changes.

## Common commands

```bash
uv sync                                        # install (creates .venv, pulls the one dep)
uv run patchbay-auth                           # one-time browser PKCE authorization; re-run after any change to config.SCOPES
uv run patchbay                                # start the MCP server on stdio
uv run patchbay-check                          # read-only smoke check against the live API — the fastest way to notice endpoint drift
uv run python -m unittest discover tests       # offline unit + fixture-based shape tests, sub-second
uv run python tests/record_fixtures.py         # re-baseline tests/fixtures/*.json against the live API (scrubs identity)
claude mcp list                                # health-check the registered patchbay server
claude mcp get patchbay                        # show current registration and scope
```

No linter, no build step. Tests use stdlib `unittest` — no dev dependencies.

If the server misbehaves under a Claude client, run `uv run patchbay` directly first, then `uv run patchbay-check` — both fail the same way as under any client, and are easier to debug.

## Architecture

Three layers, top-down:

- `server.py` — MCP tool wrappers. Every `@mcp.tool` is a one-liner that forwards to a `Spotify` method. **Design invariant: tools stay thin.** No pagination, batching, or response shaping here.
- `client.py` — `Spotify` class holds all domain logic: token refresh, rate-limit retry, pagination loops, 100-item batching, and `_slim_track` response compaction. All new Spotify calls go through `Spotify.request`, never `_http` directly.
- `_http.py` — a ~30-line `urllib` wrapper. Returns `(status, headers, body)` for both success and 4xx/5xx — errors are *returned*, not raised, so callers branch on `status` uniformly.

Support modules:

- `config.py` — hand-rolled `.env` parser (no `python-dotenv`), constants (`API`, `AUTH_URL`, `TOKEN_URL`, `SCOPES`), and `TOKEN_PATH` resolution. Token path prefers `~/.config/patchbay/token.json` (XDG), falls back to `~/.patchbay/token.json` for legacy installs, and honors `SPOTIFY_TOKEN_PATH` as an override. `SCOPES` is the single source of truth — changing it means re-running `patchbay-auth`.
- `auth.py` — self-contained one-shot: opens the browser, spins up a localhost HTTP handler for exactly one callback, completes PKCE, writes the token file at `0600`. No client secret is involved (PKCE), so the only on-disk secret is the token cache itself.
- `check.py` — read-only smoke check for the client. `patchbay-check` entry point. Hits `/me`, liked songs, playlists, and playlist items and prints a compact summary. Deliberately touches all read paths so endpoint drift surfaces immediately.

Tests:

- `tests/test_*.py` — stdlib `unittest`, no dev dependencies. `test_pagination.py` includes explicit guards against the `/tracks` → `/items` regression.
- `tests/fixtures/*.json` — identity-scrubbed captures of real Spotify responses. `tests/test_shapes.py` reloads them and asserts the client's slim output matches expected keys.
- `tests/record_fixtures.py` — re-baselines fixtures against the live API. Uses the same cached token as the server. Applies the identity scrub before writing (user id/name → `test_user`).

## Non-obvious behaviors

- **`_slim_track` compacts tracks to `{id, uri, name, artists, album}` deliberately** — full Spotify track objects are noisy and expensive in-conversation. Don't widen it without a reason.
- **`Spotify.request` centralizes cross-cutting concerns:** token refresh (via `_access_token`), 429 rate-limit retry (5 attempts, honors `Retry-After`), error normalization to `SpotifyError`. Always call through it.
- **Refresh-token rotation is real** — Spotify occasionally issues a new refresh token during refresh; `_access_token` writes the file back every time.
- **Access tokens live inside the token file** with a computed `expires_at` (60 s safety margin). Deleting the file forces re-auth; corrupting it will 401 on next call and require re-auth.
- **`.env` values do not override real environment variables** — the loader uses `setdefault`. Env vars set by Claude Desktop (`env` block) win.

## Spotify API drift — read before touching playlist code

Spotify has been moving endpoints. Current state of this codebase:

- **Playlist contents endpoint renamed:** `/v1/playlists/{id}/tracks` → `/v1/playlists/{id}/items` for all methods (GET/POST/DELETE). The old path returns 403 for every playlist, including public ones. On GET responses, the per-row wrapper key changed from `track` to `item`. `client.py` is on the new endpoints — if a diff introduces `/tracks` back, that's a regression.
- **`/me/playlists` no longer includes a `tracks` sub-object** — the count is on `items.total` instead. `get_playlists` reads `tracks_total` from there.
- **February 2026 library-write consolidation** retired `DELETE /me/tracks`. `remove_liked_songs` now uses `DELETE /me/library` with URIs in the body (converted from the caller's IDs). See Spotify's [migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide) for the broader context.
- **Audio-features / energy / valence endpoints were removed for new apps in Nov 2024.** Mood/energy scoring is intentionally *not* done via the API — Claude does it from its own knowledge of the tracks. Don't try to re-add it.

## Commits

Repo follows [Scoped Commits](https://scopedcommits.com/): `<scope>: <description>`, one sentence, no Conventional Commits prefixes (`feat:`, `fix:`, `chore:`), and no `Co-Authored-By` / "Generated with" footers. Mirror the existing history (`git log --oneline`).
