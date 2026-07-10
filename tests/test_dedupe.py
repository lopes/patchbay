import unittest

from patchbay.client import dedupe_tracks


def _t(id_, name, artists, isrc=None):
    return {"id": id_, "uri": f"spotify:track:{id_}", "name": name, "artists": artists, "isrc": isrc}


class DedupeTracksTest(unittest.TestCase):
    def test_isrc_wins_when_present(self):
        # Same ISRC across two IDs → collapse.
        got = dedupe_tracks([
            _t("a", "Song - Remastered 2011", "Artist", isrc="USRC12345678"),
            _t("b", "Song", "Artist", isrc="USRC12345678"),
        ])
        self.assertEqual(len(got), 1)
        # Cleaner name preferred.
        self.assertEqual(got[0]["id"], "b")

    def test_different_isrcs_stay_apart(self):
        # Different recordings (studio vs live edit) → keep both.
        got = dedupe_tracks([
            _t("a", "Song", "Artist", isrc="AAA11111111"),
            _t("b", "Song - Live", "Artist", isrc="BBB22222222"),
        ])
        self.assertEqual(len(got), 2)

    def test_name_artist_fallback_when_isrc_missing(self):
        # Neither track has ISRC → fall back to (normalized name, primary artist).
        got = dedupe_tracks([
            _t("a", "Wonderwall - Remastered", "Oasis"),
            _t("b", "Wonderwall", "Oasis"),
        ])
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["id"], "b")

    def test_different_primary_artists_stay_apart(self):
        # Covers should NOT collapse even with same name.
        got = dedupe_tracks([
            _t("a", "Wonderwall", "Oasis"),
            _t("b", "Wonderwall", "Ryan Adams"),
        ])
        self.assertEqual(len(got), 2)

    def test_preserves_first_seen_order(self):
        got = dedupe_tracks([
            _t("a", "First", "X"),
            _t("b", "Second", "Y"),
            _t("c", "First - Remastered", "X"),  # duplicate of 'a'
            _t("d", "Third", "Z"),
        ])
        self.assertEqual([t["id"] for t in got], ["a", "b", "d"])

    def test_isrc_dedup_beats_name_mismatch(self):
        # Same recording released under different names in different regions.
        got = dedupe_tracks([
            _t("a", "Wonderwall", "Oasis", isrc="GBAYE9500001"),
            _t("b", "Wonderwall - 2014 Remaster", "Oasis", isrc="GBAYE9500001"),
        ])
        self.assertEqual(len(got), 1)

    def test_ignores_none_entries(self):
        got = dedupe_tracks([None, _t("a", "Song", "X"), None])
        self.assertEqual(len(got), 1)

    def test_empty_input(self):
        self.assertEqual(dedupe_tracks([]), [])

    def test_live_and_acoustic_normalized(self):
        got = dedupe_tracks([
            _t("a", "Track (Live)", "Artist"),
            _t("b", "Track - Acoustic", "Artist"),
            _t("c", "Track", "Artist"),
        ])
        # All three normalize to "track" for the same artist; collapse to cleanest.
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["id"], "c")


if __name__ == "__main__":
    unittest.main()
