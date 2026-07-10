---
name: audit-playlists
description: >
  Monthly hygiene audit of a Spotify library organized as mood/occasion playlists.
  Uses the patchbay MCP server to inspect playlists and Liked Songs, then reports
  bloat, duplicate track IDs across the library, over-tagged tracks, empty
  playlists, and Liked Songs accumulation. Presents findings and proposes fixes
  before touching anything. Use this skill whenever the user asks to "audit
  playlists", "check playlist hygiene", "spot-check my library", "find duplicate
  tracks", "how bloated are my playlists", "clean up Spotify", "monthly playlist
  review", or mentions patchbay hygiene / library drift. Do NOT use for full
  reorganization (that's the /reorg-playlists skill) — this skill is for the
  ongoing case, not the from-scratch case.
---

# Audit Playlists

You are running a monthly hygiene check on a Spotify library that was organized around **mood and occasion**, not genre or year. Playlists are treated as tags — the same song can live in multiple playlists. Liked Songs is kept intentionally empty; every liked-worthy track belongs in a specific playlist instead.

Your job: detect drift from that model and propose targeted fixes. This is NOT a reorganization skill. Do not propose splitting playlists, renaming them, or reshaping the taxonomy. If a full reorg is needed, tell the user to invoke `/reorg-playlists` instead.

## Prerequisites

The patchbay MCP server must be registered and running (`claude mcp list` should show `patchbay`). If tools are missing, tell the user to run `claude mcp add patchbay -- uv --directory /path/to/patchbay run patchbay` and restart the session.

## Modes of operation

### Mode 1 — quick check (default)

Runs the mechanical checks that need no LLM judgment. Fast, low-token. Trigger this by default unless the user asks for the full audit.

Steps:

1. **Fetch the inventory.** Call `mcp__patchbay__get_playlists` (limit 50). Get the count and name of every playlist.

2. **Check Liked Songs.** Call `mcp__patchbay__get_liked_songs(limit=5)`. If `total > 0`, flag it — the user's policy is empty Liked. Fetch up to 50 with `dedupe=True` to show a sample the user can decide about.

3. **Bloat detection.** For each playlist:
   - `< 10 tracks` — probably orphaned; propose deletion or merge candidates.
   - `10–300 tracks` — healthy.
   - `300–500 tracks` — flag as "getting fat"; note that shuffle discovery degrades past this.
   - `> 500 tracks` — flag as "songs won't play"; strong candidate for slimming or splitting *if the user wants* (don't push).

4. **Dedupe across the library.** Fetch each playlist with `dedupe=True` and compare the raw count vs. deduped count. For each playlist where `raw_count > deduped_count`, report how many duplicate IDs collapsed. Also compare across playlists: build a set of `(isrc or (name, primary_artist))` across ALL playlists, count how many appear in more than 3 playlists. Over-tagging dilutes the "playlist as tag" model.

5. **Report.** Present a compact table (playlists column, counts, flag column). Do NOT propose fixes yet — the user reads the report first.

### Mode 2 — full audit (vibe drift)

Trigger only when the user explicitly asks for a "full audit", "vibe check", or "deep audit". Adds Mode-1 output plus:

1. **Sample the fattest 3 playlists.** For each: read its full track list, pick 10-15 tracks that seem tonally off (relative to the playlist's implicit charter as stated in its name / description). Present them as "does this really belong here?" candidates for the user to spot-veto.

2. **Sample all playlists with duplicate IDs.** For each song with multiple track IDs in the same playlist, show both entries. User picks the canonical, others get removed.

Full audit is slower and more token-intensive. Recommend Mode 1 for a monthly rhythm; Mode 2 for a quarterly deep clean.

## Interaction model

- **Report first, fix later.** Never modify the library until the user has seen the findings and explicitly approves.
- **One decision at a time.** For each finding category (bloat / dupes / over-tagging / Liked accumulation), ask a focused question about what to do. Don't batch everything into one giant approve-all.
- **Bias toward doing nothing.** The user's library is already well-organized. Most audits should end with "here's what I found; you don't need to act on it." Flag issues, don't force resolution.

## Fix operations

If the user approves a fix:

- **Slim bloated playlist:** ask the user which tracks to remove (or have them export a sample and mark). Then `mcp__patchbay__remove_tracks(playlist_id, uris)`.
- **Dedupe track IDs in a playlist:** identify the canonical ID (cleanest name — no "Remastered", "Live", etc. — matches `dedupe_tracks` logic), remove the others via `remove_tracks`.
- **Empty Liked Songs:** confirm the user wants them removed (not moved to a playlist first), then `mcp__patchbay__remove_liked_songs(track_ids)`.
- **Delete near-empty playlist:** `mcp__patchbay__delete_playlist(playlist_id)`.

Never `add_tracks` in this skill. Adding tracks is a reorg decision.

## What NOT to do

- Do not propose renaming playlists (that's a taxonomy call, not hygiene).
- Do not propose merging playlists (same).
- Do not propose new playlists to create (same).
- Do not push the user toward specific fixes. Present neutrally.
- Do not compute or use audio features (BPM, energy) — Spotify removed that endpoint for new apps in Nov 2024.
- Do not use genre or year as an organizational axis in your suggestions — the library is intentionally mood/occasion-based.

## Report format

Use this structure:

```
## Playlist audit — <YYYY-MM-DD>

### Summary
- Total playlists: <N>
- Total unique tracks: <N> (after dedupe)
- Liked Songs: <N> (should be 0)

### Bloat
| Playlist | Tracks | Flag |
|---|---:|---|
| ... | ... | 🟢/🟡/🔴 |

### Duplicate IDs
- <playlist>: <N> duplicates (same recording, different Spotify IDs)
- ...

### Over-tagged tracks (in > 3 playlists)
- <track> — <artist> — in: <playlist1>, <playlist2>, ...
- ...

### Liked Songs accumulation
<sample of most-recent-liked tracks; ask what to do>

### Recommendations
<neutral, prioritized. "Consider" not "should".>
```

Keep the report under 500 lines. If findings exceed that, group by severity and truncate the low-severity tail with a note.
