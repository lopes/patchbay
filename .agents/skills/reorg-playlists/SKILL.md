---
name: reorg-playlists
description: >
  Full-teardown reorganization of a Spotify library into purpose-driven,
  mood/occasion-based playlists. Uses the patchbay MCP server to read every
  playlist and Liked Songs, then guides a phased workflow (context → discovery
  → planning → assignment → review → execution) with user approval between
  phases. Discourages genre-based or year-based playlists — overlapping metadata
  buckets get dissolved in favor of "when would I want to hear this" as the
  organizing axis. Use this skill whenever the user asks to "reorganize
  playlists", "rebuild my library", "reorg Spotify", "restructure playlists",
  "start over on my playlists", "consolidate playlists", "playlists are too
  bloated let's redo", or mentions a from-scratch library rebuild. For ongoing
  hygiene, use the /audit-playlists skill instead — this one is for the
  from-scratch case.
---

# Reorganize Playlists

You are running a **full library reorganization** for a user who wants to move away from bloated, genre-adjacent playlists toward tight, purpose-driven, mood/occasion-based ones. This is a phased workflow with mandatory pause points. Every write happens only after explicit approval.

## Philosophy — non-negotiable

- **Organize by "when would I hear this", not by "what kind of song is this".** Occasions and moods (Reading, Driving, Coffee Night, Churrasco, Rain, Party Hard) are the axes. Genres, years, decades, and moods-as-genres are not.
- **Playlists are tags, not folders.** A track can live in multiple playlists if it genuinely fits multiple occasions. Aim for average 1.3–1.5 playlist assignments per track; cap at 3.
- **Liked Songs is not storage.** By the end, Liked Songs is empty. If a song is worth keeping, it's in a specific playlist.
- **Reject overlap-with-metadata splits.** If a playlist could be reproduced with a Spotify smart filter (genre = X, year > Y), it does not belong in this scheme.
- **Reject bloat.** > 300 tracks in one playlist means songs will never play. If a real occasion has more, split it by sub-context (e.g., Driving BR / Driving Intl) — but only when that sub-context is a real distinct listening moment, not a language filter.

If the user pushes toward a genre-based structure, push back once with the reasoning above. If they insist, comply but note it.

## Prerequisites

Verify `mcp__patchbay__` tools are available. If not, tell the user to register patchbay (`claude mcp add ...`) and restart the session. All MCP writes and reads flow through this server.

## Phase 1 — context gathering (user input driven)

Ask these questions before touching data. Do NOT skip. The answers drive every downstream phase.

1. **What kind of organization?** Confirm mood/occasion axis. If the user proposes genre or year splits, push back with the philosophy above.
2. **Tell me about yourself.** What do you like to listen to? What are you known for musically? Any languages / cultural contexts to preserve (e.g., "keep BR sertanejo in its own thing", "I'm bilingual — split Intl / BR where the vibe changes")?
3. **What's not working now?** What made the current library feel wrong? (Common: "some playlists are so big I never hear the good songs", "I keep liking things and forgetting to sort them", "my genre-based playlists don't match how I actually listen".)
4. **How do you want things to work?** What occasions do you regularly listen for? Prompt with a menu — Working, Reading, Coffee (day/night), Wine, Cooking, Cleaning, Gardening, BBQ, Driving, Workout, Party, Rain, Nostalgia, Cozy home — and let them add/remove.
5. **Any anchor tracks?** For playlists that are ambiguous by name (e.g., "Good Vibes"), ask for 2–3 anchor tracks that define the vibe. Those anchors constrain the category during assignment.
6. **Target count.** Fine-grained (19+), moderate (13–18), or tight (8–12). Bigger is not better — every added playlist is a maintenance cost.
7. **Naming convention.** Which language for which playlist? (User in this repo uses English defaults with Portuguese names for BR-flavored variants: Driving/Dirigindo, Nostalgia/Saudade, Party Hard/Rockão, Modão, Carnaval, Aconchego, Churrasco.)

Persist the context in a scratch file at `/tmp/patchbay-reorg-<timestamp>/context.md` so subsequent phases can reference it.

## Phase 2 — discovery

**Fan out subagents.** For each existing playlist + Liked Songs, dispatch a subagent in parallel that returns a compact vibe sketch (under 250 words): vibe, top artists, sample tracks, genre/language mix, occasion fit, outliers. Do NOT hold every track in main context — that blows out the token budget on any library over ~1000 tracks.

For Liked Songs specifically: it's usually too big to inline. If the raw tool response exceeds message limits, the harness saves it to disk — one subagent reads that file in chunks. Every track must be seen at least once.

## Phase 3 — planning

1. Draft a playlist set from the discovery sketches + user context.
2. Each playlist gets a **charter** — one line: what belongs here, what doesn't. Charters are strict; "kind of fits" doesn't count.
3. Present the set in a compact table: name, charter, feed sources (which existing playlists / how much of Liked feeds into it).
4. Ask user for:
   - Add / remove / rename
   - Reframes on ambiguous ones
   - Final go-ahead
5. Persist the approved plan at `/tmp/patchbay-reorg-<timestamp>/plan.md`.

## Phase 4 — assignment

The failure mode from past runs: **rule-based categorization dumps low-confidence tracks into a fallback bucket** (e.g., "coffee_day" ends up with 173 unmatched tracks). Do not do this.

Approach:

1. **Build the pool.** Fetch every playlist with `dedupe=True` (uses the ISRC-first `dedupe_tracks` helper in `client.py`). Combine with Liked Songs. Deduplicate again across the full set (same-song-different-playlist). Store as a JSONL file under `/tmp/patchbay-reorg-<timestamp>/pool.jsonl` with `{id, uri, name, artists, album, isrc, release_year, sources:[...]}`.
2. **Categorize with LLM judgment per track, not a rule engine.** Dispatch a categorization subagent with the pool file + all 22 (or however many) charters. It reads each track and assigns 1–3 playlists based on the track's actual character, using its knowledge of artists/albums. It flags low-confidence assignments with a `?` suffix on the URI.
3. **Enforce "no fallback bucket".** If more than ~5% of tracks are `?`-marked in any single playlist, that's the fallback smell. Run a targeted cleanup pass that re-classifies just those `?` tracks with tighter prompts.
4. **Slim pre-emptively.** If any playlist exceeds 300 tracks, propose a slim pass before showing the user. It's cheaper than making them spot-veto 400 lines during review.
5. Persist assignments to `/tmp/patchbay-reorg-<timestamp>/assignments/<slug>.txt` (one file per playlist, `uri | name | artist | album | sources:...` per line).

## Phase 5 — review

Generate a compact review sheet: for each playlist, list count, top 6 artists, 10–12 sample tracks (evenly spread across the list). Present to the user with a single question: *approve, run another cleanup pass, or inspect specific playlist files first*.

Do NOT ask for line-by-line approval — that's impractical at library scale. Trust the user's spot-check + the cleanup pass loop.

## Phase 6 — execution

Write a Python execution script under `/tmp/patchbay-reorg-<timestamp>/execute.py` that:

1. Creates all N new playlists (`sp.create_playlist(name, description, public=True)`), stores each `{slug: playlist_id}` in a state file.
2. Populates each with `sp.add_tracks(playlist_id, uris)` (batches of 100 internally).
3. Empties Liked Songs with `sp.remove_liked_songs(track_ids)` — uses the Feb 2026 `DELETE /me/library` endpoint, query-param URIs, 40 per batch.
4. Deletes old playlists with `sp.delete_playlist(playlist_id)`.

**Idempotency is mandatory.** The script must load state and skip completed steps on restart. Phase 6 can fail on rate limits, endpoint drift, or network — the user must be able to re-run and pick up where it left off.

Run the script in the foreground with visible logs so the user sees each write happening. On failure, diagnose the specific step, fix if it's a known drift (like the Feb 2026 issue), and resume.

## Gotchas learned from real runs

- **`_slim_track` includes `isrc` and `release_year`.** Use both for dedup during pool building.
- **Response-too-large on Liked Songs (>500 tracks).** Read the file the harness saved rather than re-fetching. Chunk the read.
- **Old playlist names may collide with new ones** (e.g., old "Focus" vs new "Focus"). Create new ones first, delete old ones last — Spotify uses IDs, names can collide freely.
- **MCP tools load once per session.** If patchbay's `client.py` changes mid-session (as it did in the origin run when `delete_playlist` was added), the new tool won't be visible via MCP until session restart. Import the Python module directly if you need the new behavior now.
- **Feb 2026 library-write consolidation.** `DELETE /me/tracks` is gone; `remove_liked_songs` uses `DELETE /me/library` with URIs as a comma-separated query param, batches of 40. Already fixed in this repo; guard covered by `tests/test_writes.py`.
- **Duplicate track IDs.** Same recording can appear under 2+ Spotify IDs (remaster, live, region). ISRC-primary dedup catches them; `(name, primary_artist)` fallback catches the rest. Both are baked into `dedupe_tracks`.

## What NOT to do

- Do not skip the context-gathering phase. The user's specific taste is what makes a good reorg vs. a generic one.
- Do not propose genre-based, year-based, or decade-based playlists — even if the user's current library has some. Convert them to occasion-based.
- Do not batch every phase transition into one big approve-all. Each phase gets its own confirmation.
- Do not use LLM-inferred BPM / energy / valence. That data was in Spotify's audio-features endpoint, which was removed for new apps in Nov 2024. Categorize on artist / song / album / release_year alone.
- Do not create playlists on Spotify before the user approves the plan. Every MCP write is a phase-6 decision.
- Do not delete old playlists before new ones are populated and confirmed. Sequence: create → populate → verify → empty liked → delete old.
