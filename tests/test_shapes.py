"""Reload captured Spotify JSON and check the client's slim shape.

This is the regression net for Spotify-side response drift. When Spotify
changes an endpoint (as with /tracks -> /items), re-record the fixtures with
`uv run python tests/record_fixtures.py`; if the client can no longer parse
them, these tests fail before the change hits a live conversation.

Assertions target keys and shape, not values — the value data was captured
from Spotify's global catalog and may change between recordings.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from patchbay.client import Spotify

FIXTURES = Path(__file__).parent / "fixtures"

SLIM_TRACK_KEYS = {"id", "uri", "name", "artists", "album", "isrc", "release_year"}


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class ShapeTest(unittest.TestCase):
    def setUp(self):
        self.sp = Spotify()

    def test_liked_songs_shape(self):
        with patch.object(Spotify, "request", return_value=_load("liked_songs.json")):
            got = self.sp.get_liked_songs(limit=5)
        self.assertIsInstance(got["total"], int)
        self.assertEqual(got["count"], len(got["items"]))
        self.assertGreater(got["count"], 0)
        for t in got["items"]:
            self.assertEqual(set(t.keys()), SLIM_TRACK_KEYS)
            self.assertTrue(t["uri"].startswith("spotify:track:"))
            self.assertIsNotNone(t["name"])

    def test_playlists_list_shape(self):
        with patch.object(Spotify, "request", return_value=_load("playlists_list.json")):
            got = self.sp.get_playlists(limit=5)
        self.assertGreater(got["count"], 0)
        for p in got["items"]:
            self.assertEqual(
                set(p.keys()),
                {"id", "name", "owner", "tracks_total", "public", "collaborative"},
            )
            # Guards against the regression where tracks_total came from the
            # removed p["tracks"] object and always ended up None.
            self.assertIsInstance(p["tracks_total"], int)

    def test_playlist_items_shape(self):
        with patch.object(Spotify, "request", return_value=_load("playlist_items.json")):
            got = self.sp.get_playlist_tracks("PID", limit=5)
        self.assertGreater(got["count"], 0)
        for t in got["items"]:
            self.assertEqual(set(t.keys()), SLIM_TRACK_KEYS)
            self.assertTrue(t["uri"].startswith("spotify:track:"))

    def test_search_shape(self):
        with patch.object(Spotify, "request", return_value=_load("search.json")):
            got = self.sp.search_tracks("anything", limit=2)
        self.assertGreater(got["count"], 0)
        for t in got["items"]:
            self.assertEqual(set(t.keys()), SLIM_TRACK_KEYS)

    def test_me_fixture_is_scrubbed(self):
        # Guard against accidentally committing an un-scrubbed fixture.
        me = _load("me.json")
        self.assertEqual(me["id"], "test_user")
        self.assertEqual(me["display_name"], "test_user")


if __name__ == "__main__":
    unittest.main()
