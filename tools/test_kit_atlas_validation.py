import unittest
import ftex_convert as fc
from validate_ab_kit_atlases import check_png


class AtlasValidationTests(unittest.TestCase):
    def setUp(self):
        self.png = fc.encode_png_rgba(bytes(range(16)), 2, 2)

    def test_rgba_png(self):
        check_png(self.png, 2, 2)

    def test_corruption(self):
        bad = bytearray(self.png)
        bad[29] ^= 1
        with self.assertRaisesRegex(ValueError, 'CRC'):
            check_png(bad, 2, 2)

    def test_wrong_dimensions(self):
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            check_png(self.png, 4, 1)

    def test_truncated_png(self):
        with self.assertRaises(ValueError):
            check_png(self.png[:-4], 2, 2)


if __name__ == '__main__':
    unittest.main()
