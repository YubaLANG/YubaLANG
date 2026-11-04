import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_release import create_archive


class ReleasePackagingTests(unittest.TestCase):
    def test_zip_archive_is_reproducible_and_has_normalized_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "YubaLANG.exe"
            binary.write_bytes(b"executable bytes")
            first = root / "first.zip"
            second = root / "second.zip"

            create_archive(binary, first, "zip", 1_800_000_001)
            create_archive(binary, second, "zip", 1_800_000_001)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                item = archive.getinfo("YubaLANG.exe")
                self.assertEqual(item.date_time, (2027, 1, 15, 8, 0, 0))
                self.assertEqual(archive.read(item), b"executable bytes")

    def test_tar_gzip_archive_is_reproducible_and_has_normalized_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "YubaLANG"
            binary.write_bytes(b"executable bytes")
            first = root / "first.tar.gz"
            second = root / "second.tar.gz"

            create_archive(binary, first, "tar.gz", 1_800_000_001)
            create_archive(binary, second, "tar.gz", 1_800_000_001)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first, "r:gz") as archive:
                item = archive.getmember("YubaLANG")
                self.assertEqual(item.mtime, 1_800_000_001)
                self.assertEqual(archive.extractfile(item).read(), b"executable bytes")

    def test_rejects_unknown_archive_format(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "YubaLANG"
            binary.write_bytes(b"executable bytes")
            with self.assertRaisesRegex(ValueError, "Unsupported release archive"):
                create_archive(binary, root / "asset", "rar", 1_800_000_001)


if __name__ == "__main__":
    unittest.main()
