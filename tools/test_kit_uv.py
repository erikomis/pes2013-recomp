import io
import pickle
import unittest

from extract_kit_uv_map import NumericOnly
from probe_kit_uv import rasterize


class KitUVTests(unittest.TestCase):
    def test_identity_preserves_every_pixel_and_alpha(self):
        corners = [[0, 0], [1, 0], [1, 1], [0, 1]]
        pairs = [dict(source_uvs=[corners[i] for i in indices],
                      target_uvs=[corners[i] for i in indices])
                 for indices in [(0, 1, 2), (0, 2, 3)]]
        pixels = bytes(range(64))
        for flip in (False, True):
            result, stats = rasterize(pixels, 4, 4, pairs, 4, 4, flip)
            self.assertEqual(result, pixels)
            self.assertEqual(stats['covered_pixels'], 16)

    def test_degenerate_triangle_does_not_write(self):
        pair = dict(source_uvs=[[0, 0]]*3, target_uvs=[[.5, .5]]*3)
        result, stats = rasterize(bytes([255]*16), 2, 2, [pair], 2, 2)
        self.assertEqual(result, bytes(16))
        self.assertEqual(stats['degenerate_triangles'], 1)

    def test_pickle_rejects_callable_import(self):
        # The data reader must not resolve even a harmless built-in callable.
        with self.assertRaisesRegex(ValueError, 'Unsupported global'):
            NumericOnly(io.BytesIO(pickle.dumps(len))).load()


if __name__ == '__main__':
    unittest.main()
