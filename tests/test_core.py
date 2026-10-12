import tempfile
import unittest
from pathlib import Path

from cleanup_manager.core import folder_size, format_size, scan_folder

class CoreTests(unittest.TestCase):
    def test_scan_top_level_and_sizes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "folder").mkdir()
            (root / "folder" / "a.txt").write_bytes(b"abc")
            (root / "image.jpg").write_bytes(b"12345")
            results = scan_folder(root, include_nested=False)
            self.assertEqual({item.name for item in results}, {"folder", "image.jpg"})
            self.assertEqual(folder_size(root / "folder"), 3)

    def test_nested_scan_and_filter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "folder").mkdir()
            (root / "folder" / "small.txt").write_bytes(b"x")
            results = scan_folder(root, include_nested=True, min_size=2)
            self.assertEqual([item.name for item in results], [])

    def test_format_size(self):
        self.assertEqual(format_size(1536), "1.5 KB")

class SafetyTests(unittest.TestCase):
    def test_scan_does_not_follow_nested_directory_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            outside = Path(temp) / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "secret.txt").write_text("secret")
            try:
                (root / "link").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation not supported")
            self.assertEqual(scan_folder(root, include_nested=True), [])
            self.assertEqual(folder_size(root), 0)

    def test_recycling_is_not_supported_on_non_windows(self):
        import os
        from cleanup_manager.core import recycle_paths
        if os.name == "nt":
            self.skipTest("Runs only on non-Windows systems")
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "keep.txt"
            file.write_text("keep")
            with self.assertRaises(RuntimeError):
                recycle_paths([file])
            self.assertTrue(file.exists())

if __name__ == "__main__":
    unittest.main()
