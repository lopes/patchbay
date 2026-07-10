import unittest
from unittest.mock import patch

from patchbay.client import Spotify, SpotifyError


class _CaseInsensitiveHeaders(dict):
    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


def _headers(retry_after: str = "0") -> _CaseInsensitiveHeaders:
    return _CaseInsensitiveHeaders({"Retry-After": retry_after})


class RequestRetryTest(unittest.TestCase):
    def setUp(self):
        self.sp = Spotify()

    def test_429_then_200_returns_body(self):
        responses = [
            (429, _headers(), b""),
            (429, _headers(), b""),
            (200, _headers(), b'{"ok": true}'),
        ]
        with patch("patchbay.client._http.request", side_effect=responses), \
             patch.object(Spotify, "_access_token", return_value="tok"), \
             patch("patchbay.client.time.sleep") as sleep:
            got = self.sp.request("GET", "/whatever")
        self.assertEqual(got, {"ok": True})
        # Two sleeps — one per 429.
        self.assertEqual(sleep.call_count, 2)

    def test_five_consecutive_429s_raises(self):
        with patch("patchbay.client._http.request",
                   return_value=(429, _headers(), b"")), \
             patch.object(Spotify, "_access_token", return_value="tok"), \
             patch("patchbay.client.time.sleep"):
            with self.assertRaises(SpotifyError):
                self.sp.request("GET", "/whatever")

    def test_non_2xx_raises_immediately(self):
        with patch("patchbay.client._http.request",
                   return_value=(500, _headers(), b"boom")), \
             patch.object(Spotify, "_access_token", return_value="tok"):
            with self.assertRaises(SpotifyError):
                self.sp.request("GET", "/whatever")

    def test_204_returns_empty_dict(self):
        with patch("patchbay.client._http.request",
                   return_value=(204, _headers(), b"")), \
             patch.object(Spotify, "_access_token", return_value="tok"):
            got = self.sp.request("DELETE", "/whatever")
        self.assertEqual(got, {})

    def test_retry_after_honored(self):
        responses = [
            (429, _headers(retry_after="7"), b""),
            (200, _headers(), b'{}'),
        ]
        with patch("patchbay.client._http.request", side_effect=responses), \
             patch.object(Spotify, "_access_token", return_value="tok"), \
             patch("patchbay.client.time.sleep") as sleep:
            self.sp.request("GET", "/whatever")
        # Implementation adds a 1-second safety margin on top of Retry-After.
        sleep.assert_called_once_with(8)


if __name__ == "__main__":
    unittest.main()
