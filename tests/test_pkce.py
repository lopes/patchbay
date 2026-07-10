import base64
import hashlib
import unittest

from patchbay.auth import _pkce_pair


class PkcePairTest(unittest.TestCase):
    def test_challenge_is_sha256_of_verifier(self):
        verifier, challenge = _pkce_pair()
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        self.assertEqual(challenge, expected)

    def test_no_padding(self):
        _v, challenge = _pkce_pair()
        self.assertFalse(challenge.endswith("="))

    def test_pair_is_random(self):
        a, _ = _pkce_pair()
        b, _ = _pkce_pair()
        self.assertNotEqual(a, b)

    def test_verifier_length_meets_rfc7636(self):
        # RFC 7636: 43 <= len(code_verifier) <= 128
        verifier, _ = _pkce_pair()
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)


if __name__ == "__main__":
    unittest.main()
