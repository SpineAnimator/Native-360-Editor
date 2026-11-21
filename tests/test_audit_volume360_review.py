"""Pixel-only test fixtures for passive licensed Spine Editor review sheets.

These PNGs only exercise evidence layout and validation, never represent an
animation or independently verify native Editor provenance.
"""
from pathlib import Path
import hashlib
import tempfile
import unittest

from PIL import Image, ImageDraw
from scripts.create_editor360_review_sheets import build


def fake_png_inputs(folder, number=40, wrong_last=False, wrong_size=False):
    paths = []
    for index in range(number):
        size = (87, 64) if wrong_size and index == 19 else (88, 64)
        frame = Image.new("RGBA", size, (29, 22, 58, 255))
        draw = ImageDraw.Draw(frame)
        # Same first and last pixels. Intermediate differences are fixtures,
        # not a 360 animation, and should not affect frame SHA validation.
        x = (index if index != number - 1 else 0)
        if wrong_last and index == number - 1:
            x = 18
        draw.ellipse((16 + x // 3, 23, 49 + x // 3, 57),
                     fill=(190, 25, 50, 255))
        path = folder / f"original-editor-volume360_{index:02d}.png"
        frame.save(path)
        paths.append(path)
    return paths


def do_build(folder):
    return build(folder, folder / "all.jpg", folder / "focus.jpg", folder / "report.json",
                 expected_count=40, source_ref="e" * 40)


class LicensedFrameReviewSheetTests(unittest.TestCase):
    def test_all_realistic_input_frames_are_included_without_touching_pngs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            paths = fake_png_inputs(folder)
            original = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
            report = do_build(folder)
            self.assertEqual(report["actual_frames"], 40)
            self.assertEqual([x["frame"] for x in report["frames"]], list(range(40)))
            self.assertEqual(report["frames"][0]["rgba_sha256"],
                             report["frames"][-1]["rgba_sha256"])
            self.assertEqual(report["source_git_sha"], "e" * 40)
            self.assertEqual(report["focused_frame_indexes"],
                             [0, 8, 12, 15, 16, 19, 20, 24, 25, 26, 27, 28, 29, 31, 36, 39])
            self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest() for p in paths],
                             original, "Review tool must never modify original PNGs")
            self.assertFalse(report["artistic_quality_approved"])
            self.assertFalse(report["publication_ready"])
            for name in ("all.jpg", "focus.jpg", "report.json"):
                self.assertTrue((folder / name).is_file())
            with Image.open(folder / "all.jpg") as img:
                self.assertGreater(img.width, 1000)
                self.assertGreater(img.height, 500)

    def test_missing_or_duplicate_frame_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            paths = fake_png_inputs(folder)
            paths[18].rename(folder / "original-editor-volume360_17-copy.png")
            with self.assertRaisesRegex(ValueError, "Unnumbered"):
                do_build(folder)

    def test_missing_middle_frame_fails_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            paths = fake_png_inputs(folder)
            paths[18].unlink()
            with self.assertRaisesRegex(ValueError, "Expected 40"):
                do_build(folder)

    def test_source_art_must_return_exactly_at_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fake_png_inputs(folder, wrong_last=True)
            with self.assertRaisesRegex(ValueError, "source pixels do not return"):
                do_build(folder)

    def test_inconsistent_dimensions_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fake_png_inputs(folder, wrong_size=True)
            with self.assertRaisesRegex(ValueError, "inconsistent dimensions"):
                do_build(folder)

    def test_untrusted_source_commit_ref_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fake_png_inputs(folder)
            with self.assertRaisesRegex(ValueError, "exact 40-character"):
                build(folder, folder / "all.jpg", folder / "focus.jpg", folder / "report.json",
                      source_ref="not-a-commit")


if __name__ == "__main__":
    unittest.main()
