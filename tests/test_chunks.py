import unittest

from patchbay.client import _chunks


class ChunksTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(list(_chunks([], 3)), [])

    def test_exact_multiple(self):
        self.assertEqual(list(_chunks([1, 2, 3, 4], 2)), [[1, 2], [3, 4]])

    def test_ragged(self):
        self.assertEqual(list(_chunks([1, 2, 3], 2)), [[1, 2], [3]])

    def test_single_chunk(self):
        self.assertEqual(list(_chunks([1, 2], 10)), [[1, 2]])


if __name__ == "__main__":
    unittest.main()
