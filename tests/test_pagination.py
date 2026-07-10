import unittest
from unittest.mock import patch

from patchbay.client import Spotify


def _liked_item(name):
    return {"track": {
        "id": name, "uri": f"spotify:track:{name}", "name": name,
        "artists": [{"name": "A"}], "album": {"name": "X"},
    }}


def _playlist_item(name):
    return {"item": {
        "id": name, "uri": f"spotify:track:{name}", "name": name,
        "artists": [{"name": "A"}], "album": {"name": "X"},
    }}


def _page(items, total):
    return {"total": total, "items": items}


class LikedSongsPaginationTest(unittest.TestCase):
    def setUp(self):
        self.sp = Spotify()

    def test_single_page_within_limit(self):
        page = _page([_liked_item(f"t{i}") for i in range(3)], total=3)
        with patch.object(Spotify, "request", return_value=page) as m:
            got = self.sp.get_liked_songs(limit=10)
        self.assertEqual(got["total"], 3)
        self.assertEqual(got["count"], 3)
        self.assertEqual([i["name"] for i in got["items"]], ["t0", "t1", "t2"])
        self.assertEqual(m.call_count, 1)

    def test_pagination_across_multiple_pages(self):
        pages = [
            _page([_liked_item(f"t{50 * p + i}") for i in range(50)], total=250)
            for p in range(4)
        ]
        with patch.object(Spotify, "request", side_effect=pages) as m:
            got = self.sp.get_liked_songs(limit=200)
        self.assertEqual(got["count"], 200)
        self.assertEqual(m.call_count, 4)
        offsets = [c.kwargs["params"]["offset"] for c in m.call_args_list]
        self.assertEqual(offsets, [0, 50, 100, 150])

    def test_termination_on_empty_batch(self):
        pages = [
            _page([_liked_item("a")], total=999),
            _page([], total=999),
        ]
        with patch.object(Spotify, "request", side_effect=pages):
            got = self.sp.get_liked_songs(limit=500)
        self.assertEqual(got["count"], 1)

    def test_stops_when_total_reached(self):
        # total=1, but the caller asks for 500 — should stop after 1.
        page = _page([_liked_item("only")], total=1)
        with patch.object(Spotify, "request", return_value=page) as m:
            got = self.sp.get_liked_songs(limit=500)
        self.assertEqual(got["count"], 1)
        self.assertEqual(m.call_count, 1)

    def test_offset_threaded_through(self):
        page = _page([_liked_item("t")], total=100)
        with patch.object(Spotify, "request", return_value=page) as m:
            self.sp.get_liked_songs(limit=1, offset=42)
        self.assertEqual(m.call_args.kwargs["params"]["offset"], 42)


class PlaylistTracksPaginationTest(unittest.TestCase):
    def setUp(self):
        self.sp = Spotify()

    def test_uses_item_key_not_track_key(self):
        # The /tracks -> /items migration: per-row wrapper is "item".
        page = _page([_playlist_item(f"t{i}") for i in range(3)], total=3)
        with patch.object(Spotify, "request", return_value=page):
            got = self.sp.get_playlist_tracks("PID", limit=10)
        self.assertEqual([i["name"] for i in got["items"]], ["t0", "t1", "t2"])

    def test_batches_of_100(self):
        pages = [
            _page([_playlist_item(f"t{100 * p + i}") for i in range(100)], total=300)
            for p in range(3)
        ]
        with patch.object(Spotify, "request", side_effect=pages) as m:
            got = self.sp.get_playlist_tracks("PID", limit=300)
        self.assertEqual(got["count"], 300)
        self.assertEqual(m.call_count, 3)
        offsets = [c.kwargs["params"]["offset"] for c in m.call_args_list]
        self.assertEqual(offsets, [0, 100, 200])

    def test_hits_the_items_endpoint(self):
        page = _page([_playlist_item("t")], total=1)
        with patch.object(Spotify, "request", return_value=page) as m:
            self.sp.get_playlist_tracks("PID42", limit=1)
        # First positional after "GET" should be the /items path — guard against
        # a regression to /tracks.
        called_url = m.call_args.args[1]
        self.assertIn("/items", called_url)
        self.assertNotIn("/tracks", called_url)

    def test_offset_threaded_through(self):
        page = _page([_playlist_item("t")], total=1000)
        with patch.object(Spotify, "request", return_value=page) as m:
            got = self.sp.get_playlist_tracks("PID", limit=1, offset=200)
        self.assertEqual(m.call_args.kwargs["params"]["offset"], 200)
        self.assertEqual(got["offset"], 200)


class PlaylistsListTest(unittest.TestCase):
    def setUp(self):
        self.sp = Spotify()

    def test_tracks_total_reads_from_items_total(self):
        # After the /tracks -> /items migration, /me/playlists no longer exposes
        # a tracks sub-object — the count is on items.total.
        page = {"total": 1, "items": [{
            "id": "PID",
            "name": "My Playlist",
            "owner": {"id": "user1"},
            "items": {"total": 42, "href": "..."},
            "public": True,
            "collaborative": False,
        }]}
        with patch.object(Spotify, "request", return_value=page):
            got = self.sp.get_playlists(limit=1)
        self.assertEqual(got["items"][0]["tracks_total"], 42)


if __name__ == "__main__":
    unittest.main()
