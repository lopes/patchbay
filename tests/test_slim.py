import unittest

from patchbay.client import _slim_track


class SlimTrackTest(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(_slim_track(None))

    def test_empty_dict_returns_none(self):
        # Falsy short-circuit — matches the "missing track" case in responses.
        self.assertIsNone(_slim_track({}))

    def test_full_track(self):
        got = _slim_track({
            "id": "abc",
            "uri": "spotify:track:abc",
            "name": "Song",
            "artists": [{"name": "A"}, {"name": "B"}],
            "album": {"name": "Album"},
        })
        self.assertEqual(got, {
            "id": "abc",
            "uri": "spotify:track:abc",
            "name": "Song",
            "artists": "A, B",
            "album": "Album",
        })

    def test_empty_artists(self):
        got = _slim_track({
            "id": "x",
            "uri": "u",
            "name": "N",
            "artists": [],
            "album": {"name": "A"},
        })
        self.assertEqual(got["artists"], "")

    def test_missing_album(self):
        got = _slim_track({
            "id": "x",
            "uri": "u",
            "name": "N",
            "artists": [{"name": "A"}],
        })
        self.assertIsNone(got["album"])


if __name__ == "__main__":
    unittest.main()
