"""Thin Spotify Web API client: token refresh, requests, and library ops.

All domain logic (pagination, batching, response slimming) lives here so the
MCP tools in server.py stay tiny and readable.
"""

import json
import os
import re
import time

from . import _http, config


class SpotifyError(RuntimeError):
    """Raised for auth problems and non-2xx API responses."""


def _slim_track(track: dict | None) -> dict | None:
    """Compact track shape, so conversations stay cheap and readable.

    `isrc` and `release_year` are included because they let downstream code
    dedupe reliably (same recording across remasters/regions shares an ISRC)
    and place tracks in time without a per-track lookup.
    """
    if not track:
        return None
    album = track.get("album") or {}
    release_date = album.get("release_date") or ""
    return {
        "id": track.get("id"),
        "uri": track.get("uri"),
        "name": track.get("name"),
        "artists": ", ".join(a["name"] for a in track.get("artists", [])),
        "album": album.get("name"),
        "isrc": (track.get("external_ids") or {}).get("isrc"),
        "release_year": int(release_date[:4]) if release_date[:4].isdigit() else None,
    }


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


# Matches trailing edition markers like " - Remastered 2011", " (Live at Wembley)",
# " - Acoustic", " (2020 Remaster)". Used to normalize track names for fallback dedup.
_VERSION_SUFFIX = re.compile(
    r"\s*[-(]\s*("
    r"remaster(ed)?|live|acoustic|karaoke|radio edit|extended|demo|mono|stereo|"
    r"version|deluxe|edit|bonus track"
    r")\b.*$",
    re.IGNORECASE,
)


def _dedupe_key(track: dict) -> tuple:
    """Grouping key: ISRC when present, otherwise normalized name + primary artist."""
    if track.get("isrc"):
        return ("isrc", track["isrc"])
    name = _VERSION_SUFFIX.sub("", (track.get("name") or "")).strip().lower()
    primary = (track.get("artists") or "").split(",", 1)[0].strip().lower()
    return ("na", name, primary)


def dedupe_tracks(tracks: list[dict]) -> list[dict]:
    """Collapse remaster/live/version duplicates while preserving first-seen order.

    Groups by ISRC (guaranteed same recording) when available, else by a
    normalized (name, primary_artist) key. Within a group, prefers the entry
    with the cleanest name — no "- Remastered YYYY", "- Live" suffix — and
    breaks ties by shorter name. Only operates on the tracks passed in; when
    paginating, dedupe the fully-collected list rather than per-page.
    """
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for t in tracks:
        if not t:
            continue
        k = _dedupe_key(t)
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(t)

    def _penalty(t: dict) -> tuple:
        n = t.get("name") or ""
        return (1 if _VERSION_SUFFIX.search(n) else 0, len(n))

    return [sorted(groups[k], key=_penalty)[0] for k in order]


class Spotify:
    """Holds no long-lived secrets in memory beyond the cached token file."""

    # --- token handling ----------------------------------------------------
    def _load_tokens(self) -> dict:
        if not config.TOKEN_PATH.exists():
            raise SpotifyError(
                f"No token file at {config.TOKEN_PATH}. "
                "Run `uv run patchbay-auth` once to authorize."
            )
        return json.loads(config.TOKEN_PATH.read_text())

    def _save_tokens(self, data: dict) -> None:
        config.TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.TOKEN_PATH.write_text(json.dumps(data, indent=2))
        try:
            os.chmod(config.TOKEN_PATH, 0o600)  # readable only by you
        except OSError:
            pass

    def _access_token(self) -> str:
        tokens = self._load_tokens()
        if time.time() < tokens.get("expires_at", 0):
            return tokens["access_token"]

        status, _headers, raw = _http.request(
            "POST",
            config.TOKEN_URL,
            form={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": tokens.get("client_id") or config.CLIENT_ID,
            },
        )
        if status != 200:
            raise SpotifyError(
                f"Token refresh failed ({status}): {raw.decode(errors='replace')}. "
                "Re-run `uv run patchbay-auth`."
            )
        payload = json.loads(raw)
        tokens["access_token"] = payload["access_token"]
        tokens["expires_at"] = time.time() + int(payload.get("expires_in", 3600)) - 60
        if payload.get("refresh_token"):  # Spotify may rotate the refresh token
            tokens["refresh_token"] = payload["refresh_token"]
        self._save_tokens(tokens)
        return tokens["access_token"]

    def request(self, method: str, path: str, params=None, body=None):
        """One HTTP call with auth and polite rate-limit handling."""
        url = path if path.startswith("http") else f"{config.API}{path}"
        for _ in range(5):
            status, headers, raw = _http.request(
                method,
                url,
                headers={"Authorization": f"Bearer {self._access_token()}"},
                params=params,
                json_body=body,
            )
            if status == 429:  # rate limited
                time.sleep(int(headers.get("Retry-After", "1")) + 1)
                continue
            if status >= 400:
                raise SpotifyError(f"{method} {url} -> {status}: {raw.decode(errors='replace')}")
            if status == 204 or not raw:
                return {}
            return json.loads(raw)
        raise SpotifyError("Rate limited repeatedly; try again later.")

    # --- reads -------------------------------------------------------------
    def get_liked_songs(self, limit: int = 200, offset: int = 0, dedupe: bool = False) -> dict:
        limit = max(1, min(limit, 1000))
        items, total = [], None
        while len(items) < limit:
            page = self.request(
                "GET",
                "/me/tracks",
                params={"limit": min(50, limit - len(items)), "offset": offset + len(items)},
            )
            total = page.get("total", total)
            batch = page.get("items", [])
            if not batch:
                break
            items.extend(_slim_track(it.get("track")) for it in batch)
            if len(items) >= (total or 0):
                break
        if dedupe:
            items = dedupe_tracks(items)
        return {"total": total, "count": len(items), "offset": offset, "items": items}

    def get_playlists(self, limit: int = 50, offset: int = 0) -> dict:
        limit = max(1, min(limit, 50))
        page = self.request("GET", "/me/playlists", params={"limit": limit, "offset": offset})
        items = [
            {
                "id": p["id"],
                "name": p["name"],
                "owner": (p.get("owner") or {}).get("id"),
                "tracks_total": (p.get("items") or {}).get("total"),
                "public": p.get("public"),
                "collaborative": p.get("collaborative"),
            }
            for p in page.get("items", [])
        ]
        return {"total": page.get("total"), "count": len(items), "items": items}

    def get_playlist_tracks(
        self, playlist_id: str, limit: int = 300, offset: int = 0, dedupe: bool = False
    ) -> dict:
        # Spotify renamed the endpoint from /tracks to /items and the per-row
        # wrapper key from "track" to "item"; the old URL now 403s for every
        # playlist, including public ones.
        limit = max(1, min(limit, 1000))
        items, total = [], None
        while len(items) < limit:
            page = self.request(
                "GET",
                f"/playlists/{playlist_id}/items",
                params={"limit": min(100, limit - len(items)), "offset": offset + len(items)},
            )
            total = page.get("total", total)
            batch = page.get("items", [])
            if not batch:
                break
            items.extend(_slim_track(it.get("item")) for it in batch)
            if len(items) >= (total or 0):
                break
        if dedupe:
            items = dedupe_tracks(items)
        return {"total": total, "count": len(items), "offset": offset, "items": items}

    def search_tracks(self, query: str, limit: int = 10) -> dict:
        limit = max(1, min(limit, 50))
        page = self.request(
            "GET", "/search", params={"q": query, "type": "track", "limit": limit}
        )
        tracks = (page.get("tracks") or {}).get("items", [])
        return {"count": len(tracks), "items": [_slim_track(t) for t in tracks]}

    # --- writes ------------------------------------------------------------
    def create_playlist(self, name: str, description: str = "", public: bool = False) -> dict:
        me = self.request("GET", "/me")
        pl = self.request(
            "POST",
            "/me/playlists",
            body={"name": name, "description": description, "public": public},
        )
        return {
            "id": pl["id"],
            "name": pl["name"],
            "url": (pl.get("external_urls") or {}).get("spotify"),
            "owner": me.get("id"),
        }

    def add_tracks(self, playlist_id: str, track_uris: list[str]) -> dict:
        for batch in _chunks(track_uris, 100):
            self.request("POST", f"/playlists/{playlist_id}/items", body={"uris": batch})
        return {"added": len(track_uris)}

    def remove_tracks(self, playlist_id: str, track_uris: list[str]) -> dict:
        for batch in _chunks(track_uris, 100):
            self.request(
                "DELETE",
                f"/playlists/{playlist_id}/items",
                body={"tracks": [{"uri": u} for u in batch]},
            )
        return {"removed": len(track_uris)}

    def delete_playlist(self, playlist_id: str) -> dict:
        # Spotify has no true "delete playlist" endpoint; unfollowing your own
        # playlist removes it from your library, which is what users expect.
        self.request("DELETE", f"/playlists/{playlist_id}/followers")
        return {"deleted": playlist_id}

    def remove_liked_songs(self, track_ids: list[str]) -> dict:
        # Spotify's Feb 2026 consolidation retired `DELETE /me/tracks` and moved
        # library removals to `DELETE /me/library` — URIs as a comma-separated
        # query param, capped at 40 per call. Callers still pass IDs so the tool
        # surface doesn't change.
        uris = [f"spotify:track:{tid}" for tid in track_ids]
        for batch in _chunks(uris, 40):
            self.request("DELETE", "/me/library", params={"uris": ",".join(batch)})
        return {"removed": len(track_ids)}
