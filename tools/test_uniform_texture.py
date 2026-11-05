import struct
import unittest
import zlib

import uniform_texture as u


class UniformTests(unittest.TestCase):
    def fixture(self):
        data = bytearray(u.SIZE)
        data[:4] = bytes.fromhex("0d000001")
        data[32] = 1
        data[-2:] = b"\x02\0"
        struct.pack_into(">I", data, 8, u.checksum(data))
        return bytes(data)

    def test_pixel_edit_preserves_metadata_and_updates_checksum(self):
        original = self.fixture()
        pixels = bytes([172, 11, 24, 128]) * (256 * 256)
        output = u.replace_pixels(original, pixels)
        self.assertEqual(output[:8], original[:8])
        self.assertEqual(output[12:33], original[12:33])
        self.assertEqual(output[-2:], original[-2:])
        self.assertEqual(output[33:-2], pixels)
        self.assertNotEqual(output[8:12], original[8:12])
        u.validate(output)

    def test_all_png_filters(self):
        pixels = bytes((i * 17 + i // 1024) % 256 for i in range(u.PIXELS))
        for kind in range(5):
            filtered = bytearray()
            for y in range(256):
                filtered.append(kind)
                for x in range(1024):
                    i = y * 1024 + x
                    a = pixels[i - 4] if x >= 4 else 0
                    b = pixels[i - 1024] if y else 0
                    c = pixels[i - 1028] if x >= 4 and y else 0
                    pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                    paeth = a if pa <= pb and pa <= pc else b if pb <= pc else c
                    predictor = [0, a, b, (a + b) // 2, paeth][kind]
                    filtered.append((pixels[i] - predictor) % 256)
            encoded = (u.MAGIC + u.png_chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0))
                       + u.png_chunk(b"IDAT", zlib.compress(filtered)) + u.png_chunk(b"IEND", b""))
            self.assertEqual(u.decode_png(encoded), pixels)

    def test_png_and_save_corruption(self):
        png = bytearray(u.encode_png(bytes(u.PIXELS)))
        png[45] ^= 1
        with self.assertRaises(ValueError):
            u.decode_png(png)
        save = bytearray(self.fixture())
        save[100] ^= 1
        with self.assertRaisesRegex(ValueError, "CRC32"):
            u.validate(save)

    def test_wrong_resolution_rejected(self):
        png = (u.MAGIC + u.png_chunk(b"IHDR", struct.pack(">IIBBBBB", 512, 512, 8, 6, 0, 0, 0))
               + u.png_chunk(b"IEND", b""))
        with self.assertRaisesRegex(ValueError, "256x256"):
            u.decode_png(png)


if __name__ == "__main__":
    unittest.main()
