"""Thin Spotify Web API client: token refresh, requests, and library ops.

All domain logic (pagination, batching, response slimming) lives here so the
MCP tools in server.py stay tiny and readable.
"""

import json
import os
import time

from . import _http, config


class SpotifyError(RuntimeError):
    """Raised for auth problems and non-2xx API responses."""


def _slim_track(track: dict | None) -> dict | None:
    """Compact track shape, so conversations stay cheap and readable."""
    if not track:
        return None
    return {
        "id": track.get("id"),
        "uri": track.get("uri"),
        "name": track.get("name"),
        "artists": ", ".join(a["name"] for a in track.get("artists", [])),
        "album": (track.get("album") or {}).get("name"),
    }


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


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
    def get_liked_songs(self, limit: int = 200, offset: int = 0) -> dict:
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
        return {"total": total, "count": len(items), "offset": offset, "items": items}

    def get_playlists(self, limit: int = 50, offset: int = 0) -> dict:
        limit = max(1, min(limit, 50))
        page = self.request("GET", "/me/playlists", params={"limit": limit, "offset": offset})
        items = [
            {
                "id": p["id"],
                "name": p["name"],
                "owner": (p.get("owner") or {}).get("id"),
                "tracks_total": (p.get("tracks") or {}).get("total"),
                "public": p.get("public"),
                "collaborative": p.get("collaborative"),
            }
            for p in page.get("items", [])
        ]
        return {"total": page.get("total"), "count": len(items), "items": items}

    def get_playlist_tracks(self, playlist_id: str, limit: int = 300) -> dict:
        limit = max(1, min(limit, 1000))
        items, total = [], None
        while len(items) < limit:
            page = self.request(
                "GET",
                f"/playlists/{playlist_id}/tracks",
                params={"limit": min(100, limit - len(items)), "offset": len(items)},
            )
            total = page.get("total", total)
            batch = page.get("items", [])
            if not batch:
                break
            items.extend(_slim_track(it.get("track")) for it in batch)
            if len(items) >= (total or 0):
                break
        return {"total": total, "count": len(items), "items": items}

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
            self.request("POST", f"/playlists/{playlist_id}/tracks", body={"uris": batch})
        return {"added": len(track_uris)}

    def remove_tracks(self, playlist_id: str, track_uris: list[str]) -> dict:
        for batch in _chunks(track_uris, 100):
            self.request(
                "DELETE",
                f"/playlists/{playlist_id}/tracks",
                body={"tracks": [{"uri": u} for u in batch]},
            )
        return {"removed": len(track_uris)}

    def remove_liked_songs(self, track_ids: list[str]) -> dict:
        # NOTE: Spotify began consolidating library writes in Feb 2026. If a
        # newly created app rejects `DELETE /me/tracks` with 403/404, switch
        # this one call to the current library endpoint (see README). The
        # batching stays the same.
        for batch in _chunks(track_ids, 50):
            self.request("DELETE", "/me/tracks", body={"ids": batch})
        return {"removed": len(track_ids)}
