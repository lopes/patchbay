import unittest
from unittest.mock import patch

from patchbay.client import Spotify, SpotifyError


class AccessTokenTest(unittest.TestCase):
    def setUp(self):
        self.sp = Spotify()

    def test_returns_cached_when_fresh(self):
        tokens = {"access_token": "fresh", "expires_at": 10**12}  # year 33658, safely future
        with patch.object(Spotify, "_load_tokens", return_value=tokens):
            self.assertEqual(self.sp._access_token(), "fresh")

    def test_refresh_when_expired(self):
        tokens = {
            "access_token": "old",
            "refresh_token": "R1",
            "expires_at": 0,
            "client_id": "cid",
        }
        saved = {}
        payload = b'{"access_token": "new", "expires_in": 3600}'
        with patch.object(Spotify, "_load_tokens", return_value=tokens), \
             patch.object(Spotify, "_save_tokens", side_effect=lambda d: saved.update(d)), \
             patch("patchbay.client._http.request", return_value=(200, {}, payload)):
            got = self.sp._access_token()
        self.assertEqual(got, "new")
        self.assertEqual(saved["access_token"], "new")
        # Not rotated by Spotify — old refresh token stays.
        self.assertEqual(saved["refresh_token"], "R1")

    def test_rotates_refresh_token_when_returned(self):
        tokens = {
            "access_token": "old",
            "refresh_token": "R1",
            "expires_at": 0,
            "client_id": "cid",
        }
        saved = {}
        payload = b'{"access_token": "new", "expires_in": 3600, "refresh_token": "R2"}'
        with patch.object(Spotify, "_load_tokens", return_value=tokens), \
             patch.object(Spotify, "_save_tokens", side_effect=lambda d: saved.update(d)), \
             patch("patchbay.client._http.request", return_value=(200, {}, payload)):
            self.sp._access_token()
        self.assertEqual(saved["refresh_token"], "R2")

    def test_refresh_failure_raises_spotify_error(self):
        tokens = {
            "access_token": "old",
            "refresh_token": "R1",
            "expires_at": 0,
            "client_id": "cid",
        }
        with patch.object(Spotify, "_load_tokens", return_value=tokens), \
             patch("patchbay.client._http.request", return_value=(400, {}, b"bad")):
            with self.assertRaises(SpotifyError):
                self.sp._access_token()


if __name__ == "__main__":
    unittest.main()
