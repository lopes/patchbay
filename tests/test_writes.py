"""Regression tests for write endpoints — the surface Spotify keeps moving.

Guards against silent endpoint drift (like the Feb 2026 library-write
consolidation) by asserting each write method calls `Spotify.request` with the
exact HTTP method, path, and body/params shape Spotify currently expects.
"""

import unittest
from unittest.mock import patch

from patchbay.client import Spotify


class CreatePlaylistTest(unittest.TestCase):
    def setUp(self):
        self.sp = Spotify()

    def test_calls_me_then_playlists(self):
        # First call fetches /me for owner id; second creates the playlist.
        responses = [
            {"id": "user1"},
            {"id": "PID", "name": "N", "external_urls": {"spotify": "https://..."}},
        ]
        with patch.object(Spotify, "request", side_effect=responses) as m:
            got = self.sp.create_playlist("N", description="d", public=True)
        self.assertEqual(m.call_count, 2)
        self.assertEqual(m.call_args_list[0].args, ("GET", "/me"))
        self.assertEqual(m.call_args_list[1].args, ("POST", "/me/playlists"))
        self.assertEqual(
            m.call_args_list[1].kwargs["body"],
            {"name": "N", "description": "d", "public": True},
        )
        self.assertEqual(got["id"], "PID")
        self.assertEqual(got["owner"], "user1")


class AddTracksTest(unittest.TestCase):
    def setUp(self):
        self.sp = Spotify()

    def test_single_batch(self):
        uris = [f"spotify:track:{i:04d}" for i in range(10)]
        with patch.object(Spotify, "request", return_value={}) as m:
            got = self.sp.add_tracks("PID", uris)
        self.assertEqual(m.call_count, 1)
        self.assertEqual(m.call_args.args, ("POST", "/playlists/PID/items"))
        self.assertEqual(m.call_args.kwargs["body"], {"uris": uris})
        self.assertEqual(got, {"added": 10})

    def test_batches_at_100(self):
        # 250 URIs → 3 batches of size 100/100/50.
        uris = [f"spotify:track:{i:04d}" for i in range(250)]
        with patch.object(Spotify, "request", return_value={}) as m:
            self.sp.add_tracks("PID", uris)
        self.assertEqual(m.call_count, 3)
        sizes = [len(c.kwargs["body"]["uris"]) for c in m.call_args_list]
        self.assertEqual(sizes, [100, 100, 50])


class RemoveTracksTest(unittest.TestCase):
    def setUp(self):
        self.sp = Spotify()

    def test_body_shape_is_tracks_uri_objects(self):
        # Spotify expects DELETE /playlists/{id}/items with body {tracks:[{uri}...]},
        # not just {uris:[...]} — this is the shape that keeps working.
        uris = ["spotify:track:a", "spotify:track:b"]
        with patch.object(Spotify, "request", return_value={}) as m:
            self.sp.remove_tracks("PID", uris)
        self.assertEqual(m.call_args.args, ("DELETE", "/playlists/PID/items"))
        self.assertEqual(
            m.call_args.kwargs["body"],
            {"tracks": [{"uri": "spotify:track:a"}, {"uri": "spotify:track:b"}]},
        )

    def test_batches_at_100(self):
        uris = [f"spotify:track:{i:04d}" for i in range(150)]
        with patch.object(Spotify, "request", return_value={}) as m:
            self.sp.remove_tracks("PID", uris)
        self.assertEqual(m.call_count, 2)
        sizes = [len(c.kwargs["body"]["tracks"]) for c in m.call_args_list]
        self.assertEqual(sizes, [100, 50])


class RemoveLikedSongsTest(unittest.TestCase):
    """Feb 2026 migration: DELETE /me/library, query-param URIs, batch 40."""

    def setUp(self):
        self.sp = Spotify()

    def test_hits_new_library_endpoint_not_me_tracks(self):
        with patch.object(Spotify, "request", return_value={}) as m:
            self.sp.remove_liked_songs(["a", "b"])
        called_url = m.call_args.args[1]
        self.assertEqual(m.call_args.args[0], "DELETE")
        self.assertEqual(called_url, "/me/library")
        # Guard: the retired endpoint must NOT reappear.
        self.assertNotEqual(called_url, "/me/tracks")

    def test_ids_converted_to_uris_in_query_param(self):
        # Old endpoint took IDs as body {ids:[...]}. New one takes URIs as a
        # comma-separated query param. Both changes must land.
        with patch.object(Spotify, "request", return_value={}) as m:
            self.sp.remove_liked_songs(["abc123", "def456"])
        self.assertIn("params", m.call_args.kwargs)
        self.assertNotIn("body", m.call_args.kwargs)
        uris_param = m.call_args.kwargs["params"]["uris"]
        self.assertEqual(uris_param, "spotify:track:abc123,spotify:track:def456")

    def test_batches_at_40(self):
        # Spotify caps DELETE /me/library at 40 URIs per call.
        ids = [f"id{i:04d}" for i in range(95)]
        with patch.object(Spotify, "request", return_value={}) as m:
            got = self.sp.remove_liked_songs(ids)
        self.assertEqual(m.call_count, 3)
        sizes = [len(c.kwargs["params"]["uris"].split(",")) for c in m.call_args_list]
        self.assertEqual(sizes, [40, 40, 15])
        self.assertEqual(got, {"removed": 95})

    def test_empty_input_makes_no_calls(self):
        with patch.object(Spotify, "request", return_value={}) as m:
            got = self.sp.remove_liked_songs([])
        self.assertEqual(m.call_count, 0)
        self.assertEqual(got, {"removed": 0})


class DeletePlaylistTest(unittest.TestCase):
    def setUp(self):
        self.sp = Spotify()

    def test_hits_followers_endpoint_not_playlist_id(self):
        # Spotify models "delete playlist" as unfollow — hits /followers,
        # not /playlists/{id} directly. Regression guard.
        with patch.object(Spotify, "request", return_value={}) as m:
            got = self.sp.delete_playlist("PID42")
        self.assertEqual(m.call_args.args, ("DELETE", "/playlists/PID42/followers"))
        self.assertEqual(got, {"deleted": "PID42"})


if __name__ == "__main__":
    unittest.main()
