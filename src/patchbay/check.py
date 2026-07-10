"""Read-only smoke check for the Spotify client.

Run with:  uv run patchbay-check

Exercises the read paths (`/me`, liked songs, playlists, playlist items) against
the live Spotify API using the cached token, and prints a compact summary. No
writes, no side effects. Exits 1 if any call fails so it's usable in shell
pipelines.

This is the fastest way to notice endpoint drift (e.g. the Nov 2024
`/tracks` -> `/items` rename) without going through Claude Desktop.
"""

import sys

from .client import Spotify, SpotifyError


def _print_track(idx: int, track: dict) -> None:
    print(f"    {idx:>2}. {track['name']} — {track['artists']}")


def main() -> int:
    try:
        sp = Spotify()

        me = sp.request("GET", "/me")
        me_id = me.get("id") or me.get("account_id")
        print(f"Authenticated as {me.get('display_name')!r} (id={me_id})")

        liked = sp.get_liked_songs(limit=5)
        print(f"\nLiked songs — {liked['total']} total, showing {liked['count']}:")
        for i, t in enumerate(liked["items"], 1):
            _print_track(i, t)

        pls = sp.get_playlists(limit=10)
        owned = next((p for p in pls["items"] if p["owner"] == me_id), None)
        if not owned:
            print("\nNo owned playlists found; skipping playlist-items check.")
            return 0

        print(f"\nPlaylist {owned['name']!r} — {owned['tracks_total']} total:")
        tracks = sp.get_playlist_tracks(owned["id"], limit=5)
        for i, t in enumerate(tracks["items"], 1):
            _print_track(i, t)

        print("\nAll checks passed.")
        return 0

    except SpotifyError as e:
        print(f"patchbay-check failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
