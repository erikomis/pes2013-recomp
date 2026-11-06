import unittest
from index_texture_capture import parse_row


class TextureCaptureIndexTests(unittest.TestCase):
    def test_padded_runtime_format(self):
        row = parse_row('0123456789abcdef 1024x512  DXT5  fmt 0xA8 loc 1 off 0xC3CCD880 frame 321')
        self.assertEqual((row['width'], row['height'], row['format']), (1024, 512, 0xA8))
        self.assertEqual(row['frame'], 321)

    def test_small_texture_padding(self):
        row = parse_row('0123456789ABCDEF   32x16   RGBA8 fmt 0x85 loc 0 off 0x00001000 frame 1')
        self.assertEqual(row['key'], '0123456789abcdef')
        self.assertEqual(row['height'], 16)

    def test_rejects_non_key_paths(self):
        with self.assertRaises(ValueError):
            parse_row('../../sample.png 32x16 RGBA8 fmt 0x85 loc 0 off 0x0 frame 1')


if __name__ == '__main__':
    unittest.main()
