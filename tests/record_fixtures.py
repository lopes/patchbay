"""Regenerate tests/fixtures/*.json from the live Spotify API.

Run with:  uv run python tests/record_fixtures.py

Uses the same cached token as patchbay itself. Applies an identity-scrub before
writing so the fixtures are safe to commit: user identifiers become "test_user",
personal URLs get rewritten, but track/album/artist metadata (Spotify's global
catalog) stays real so the fixtures reflect a genuine response shape.

Re-run whenever Spotify moves an endpoint or changes a response shape.
"""

import json
import re
from pathlib import Path

from patchbay import _http, config
from patchbay.client import Spotify

FIXTURES = Path(__file__).parent / "fixtures"


def _get(sp: Spotify, path: str, params: dict | None = None) -> dict:
    """Raw GET returning parsed JSON, bypassing client-side slimming."""
    tok = sp._access_token()
    status, _h, raw = _http.request(
        "GET",
        f"{config.API}{path}",
        headers={"Authorization": f"Bearer {tok}"},
        params=params,
    )
    if status != 200:
        raise SystemExit(f"GET {path} -> {status}: {raw.decode(errors='replace')}")
    return json.loads(raw)


def _scrub(text: str, real_ids: list[str]) -> str:
    """Blanket string replace on the serialized JSON — simple and predictable."""
    for real in real_ids:
        if real:
            text = text.replace(real, "test_user")
    # Also rewrite any leftover user-endpoint URLs that used the real id in path.
    text = re.sub(
        r'"https://open\.spotify\.com/user/[^"]+"',
        '"https://open.spotify.com/user/test_user"',
        text,
    )
    text = re.sub(
        r'"https://api\.spotify\.com/v1/users/[^"]+"',
        '"https://api.spotify.com/v1/users/test_user"',
        text,
    )
    text = re.sub(r'"spotify:user:[^"]+"', '"spotify:user:test_user"', text)
    return text


def _write(name: str, blob: dict, real_ids: list[str]) -> None:
    text = _scrub(json.dumps(blob, indent=2), real_ids)
    (FIXTURES / name).write_text(text)
    print(f"  wrote {name}")


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    sp = Spotify()

    me = _get(sp, "/me")
    uid = me.get("id")
    account_id = me.get("account_id")
    display_name = me.get("display_name")
    real_ids = [uid, account_id, display_name]
    print(f"Recording as {display_name!r} (id={uid}, account_id={account_id}) — will be scrubbed to 'test_user'.")

    pls_list = _get(sp, "/me/playlists", params={"limit": 2})
    if not pls_list.get("items"):
        raise SystemExit("No playlists on this account — cannot record playlist_items fixture.")
    first_id = pls_list["items"][0]["id"]

    playlist_items = _get(sp, f"/playlists/{first_id}/items", params={"limit": 5})
    liked = _get(sp, "/me/tracks", params={"limit": 5})
    search = _get(sp, "/search", params={"q": "canned heat", "type": "track", "limit": 2})

    _write("me.json", me, real_ids)
    _write("playlists_list.json", pls_list, real_ids)
    _write("playlist_items.json", playlist_items, real_ids)
    _write("liked_songs.json", liked, real_ids)
    _write("search.json", search, real_ids)
    print("Done.")


if __name__ == "__main__":
    main()
