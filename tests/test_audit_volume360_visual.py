"""Regression coverage for real-editor cherry 360 low-detail material rejection.

The synthetic fixtures are only input PNGs to the passive visual auditor.
They never claim editor provenance or generate Spine animations.
"""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from scripts.audit_volume360_visual import audit


def synthetic_editor_sequence(folder, flat_rear, gold_seam_frames=(), gold_color=(252, 178, 22), frame_count=40, dark_hole_frames=(), dark_bridge_frames=(), brown_hole_frames=(), hot_red_hole_frames=()):
    paths = []
    width = height = 96
    for frame in range(frame_count):
        image = Image.new("RGBA", (width, height), (29, 21, 57, 255))
        values = image.load()
        for y in range(height):
            for x in range(width):
                fruit = (((x - 33) / 20) ** 2 + ((y - 66) / 20) ** 2 <= 1 or
                         ((x - 65) / 20) ** 2 + ((y - 66) / 20) ** 2 <= 1)
                if not fruit:
                    continue
                is_rear = flat_rear and 17 <= frame <= 24
                r = 208 if is_rear else 185 + ((x * 11 + y * 7) % 48)
                values[x, y] = (r, 34, 49, 255)
        if frame in gold_seam_frames:
            # Source-like triangular material exposure inside the lower fruit.
            # Only the PIXEL-AUDITOR test fixture is synthesised, never an
            # animation or an official Spine Editor evidence frame.
            for y in range(69, 82):
                for x in range(43, 60):
                    if y - 69 >= abs(x - 51) * .6:
                        values[x, y] = (*gold_color, 255)
        if frame in dark_hole_frames:
            # An actual-style black-red enclosed cavity WITHOUT gold color.
            # The static test fixture must not be represented as Editor art.
            for y in range(69, 83):
                for x in range(42, 60):
                    if y-69 >= abs(x-51)*.65:
                        values[x,y] = (50, 24, 23, 255)
        if frame in brown_hole_frames:
            # Reproduce the exact *class* of real PR123 4.3.26 failure:
            # a flat muddy-brown material island, not the gold or black
            # colour caught by previous negative tests. Test-input PNG only.
            for y in range(69, 83):
                for x in range(43, 60):
                    if y-69 >= abs(x-51)*.65:
                        values[x,y]=(122,41,14,255)
        if frame in hot_red_hole_frames:
            # Passive auditor negative fixture: 22+ uniform saturated red
            # pixels where real Editor frames 26-29 exposed a flattened crease.
            for y in range(69, 83):
                for x in range(42, 60):
                    if y-69 >= abs(x-51)*.65:
                        values[x,y] = (246,73,67,255)
        if dark_hole_frames:
            # The production detector requires >1500 visible fruit pixels;
            # use a full-resolution negative case, not a miniature patch.
            # NEAREST is static test-input scaling, never animation generation.
            image = image.resize((192, 192), Image.Resampling.NEAREST)
        if frame in dark_bridge_frames:
            # Pixel-only fixture: a narrow dark wedge bounded by two red
            # cherries. It is NOT a generated Spine frame or Editor proof.
            for y in range(63, 82):
                for x in range(47, 56):
                    values[x, y] = (28, 19, 25, 255)
        path = folder / f"cherry_volume360-volume360_{frame:02d}.png"
        image.save(path)
        paths.append(path)
    return paths


class NativeCherryVisualGateTests(unittest.TestCase):
    def test_flat_rear_rejected_despite_nonrectangular_silhouette(self):
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(Path(temp), flat_rear=True))
        self.assertEqual(report["status"], "REJECTED_LOW_REAR_SURFACE_DETAIL")
        self.assertTrue(report["sustainedLowRearDetail"])
        self.assertGreaterEqual(len(report["lowDetailRearFrames"]), 3)
        self.assertEqual(report["severeRectangleFrames"], [])
        self.assertEqual(report["overexposedRearFrames"], [])
        self.assertFalse(report["artisticQualityApproved"])
        self.assertFalse(report["publicationReady"])

    def test_sustained_bright_return_side_hole_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp), flat_rear=False, gold_seam_frames=(15, 26, 27)))
        self.assertEqual(report["status"], "REJECTED_BRIGHT_RETURN_SIDE_SEAM")
        self.assertEqual(report["goldReturnSideSeamFrames"], [26, 27])
        self.assertEqual(report["goldFirstSideWarningFrames"], [15])
        self.assertTrue(report["goldReturnSideSeamDetected"])
        self.assertFalse(report["artisticQualityApproved"])
        self.assertFalse(report["publicationReady"])

    def test_single_narrow_side_glint_is_a_warning_not_false_hard_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp), flat_rear=False, gold_seam_frames=(15,)))
        self.assertEqual(report["status"], "PASS_GEOMETRIC_PIXEL_HEURISTIC")
        self.assertEqual(report["goldFirstSideWarningFrames"], [15])
        self.assertEqual(report["goldReturnSideSeamFrames"], [])
        self.assertFalse(report["goldReturnSideSeamDetected"])
        self.assertFalse(report["artisticQualityApproved"])

    def test_medium_gold_realistic_38_frame_hole_fails_without_source_halo(self):
        # Captures a missed REAL licensed Spine 4.3.26 scenario:
        # frame26/27 cavity is gold/orange but not R>=225/G>=145, and the
        # 0-degree original has a brighter outside halo than the returned side.
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp), flat_rear=False, gold_seam_frames=(26, 27),
                gold_color=(190, 116, 88), frame_count=38))
        self.assertEqual(report["status"], "REJECTED_BRIGHT_RETURN_SIDE_SEAM")
        self.assertTrue(report["goldReturnSideSeamDetected"])
        self.assertEqual(report["goldReturnSideSeamFrames"], [26, 27])
        self.assertTrue(all("lowerFruitGoldFraction" in m
                            for m in report["returnSideGoldMetrics"]))
        self.assertFalse(report["publicationReady"])

    def test_dark_side_cavity_rejected_after_gold_rim_is_gone(self):
        # Regression for genuine licensed Spine frames 26..28: first
        # color-class repair eliminated the bright gold contour but still
        # exposed a visible near-black triangular hole.
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp),flat_rear=False,dark_hole_frames=(26,27,28)))
        self.assertEqual(report["status"],"REJECTED_DARK_RETURN_SIDE_CAVITY")
        # Detection may legitimately include adjacent transitional poses when
        # the triangle moves across the silhouette; do not require exactly
        # three frames and accidentally disable a stronger safety gate.
        detected=set(report["darkReturnSideCavityFrames"])
        self.assertTrue({26,27,28}.issubset(detected))
        self.assertTrue(detected.issubset(set(range(24,32))))
        self.assertTrue(report["darkReturnSideCavityDetected"])
        self.assertEqual(report["goldReturnSideSeamFrames"],[])
        self.assertFalse(report["artisticQualityApproved"])
        self.assertFalse(report["publicationReady"])

    def test_edge_on_narrow_dark_wedge_rejected_on_38_frame_return(self):
        # The previous dark detector required at least 1500 lower-fruit red
        # pixels. Real Editor frame 27 has fewer at this angle; narrow internal
        # cavities must still be found while background remains unrestricted.
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp), flat_rear=False, frame_count=38,
                dark_bridge_frames=(27, 28)))
        self.assertEqual(report["status"], "REJECTED_DARK_RETURN_SIDE_CAVITY")
        self.assertTrue(report["darkReturnSideBridgeDetected"])
        self.assertEqual(report["darkReturnSideBridgeFrames"], [27, 28])
        self.assertTrue({27, 28}.issubset(report["darkReturnSideCavityFrames"]))
        self.assertFalse(report["publicationReady"])
        self.assertFalse(report["artisticQualityApproved"])

    def test_real_pr123_style_muddy_brown_return_cavity_is_rejected(self):
        # The licensed PR123 exact-sha frame 26 contained 63 identical
        # (122,41,14) pixels, unlike the original source (max 5). Both gold
        # and R<110 dark gates previously reported a false PASS.
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp),flat_rear=False,brown_hole_frames=(26,27,28)))
        self.assertEqual(report["status"],"REJECTED_FLAT_BROWN_RETURN_SIDE_CAVITY")
        self.assertTrue({26,27,28}.issubset(set(report["brownFlatReturnSideFrames"])))
        self.assertTrue(report["brownFlatReturnSideDetected"])
        self.assertEqual(report["goldReturnSideSeamFrames"],[])
        self.assertFalse(report["artisticQualityApproved"])
        self.assertFalse(report["publicationReady"])

    def test_single_brown_texture_pixel_cluster_does_not_approve_art(self):
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp),flat_rear=False,brown_hole_frames=(27,)))
        self.assertFalse(report["brownFlatReturnSideDetected"],
            'a single suspicious image cannot satisfy sustained seam evidence')
        self.assertFalse(report["publicationReady"])
        self.assertFalse(report["artisticQualityApproved"])

    def test_uniform_hot_red_contact_triangle_on_return_is_rejected(self):
        # A real licensed PR123 40-frame clip passed the older gold/dark
        # heuristics while frames 26-29 repeated RGB(246,73,67) 22-26 times;
        # the original setup contained only a few same-colour texels.
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp), flat_rear=False, hot_red_hole_frames=(26,27,28)))
        self.assertEqual(report["status"], "REJECTED_FLAT_HOT_RED_RETURN_SIDE_CAVITY")
        self.assertTrue({26,27,28}.issubset(
            set(report["hotRedFlatReturnSideFrames"])))
        self.assertTrue(report["hotRedFlatReturnSideDetected"])
        self.assertFalse(report["publicationReady"])
        self.assertFalse(report["artisticQualityApproved"])

    def test_isolated_hot_red_glint_is_not_sustained_art_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp), flat_rear=False, hot_red_hole_frames=(27,)))
        self.assertFalse(report["hotRedFlatReturnSideDetected"])
        self.assertEqual(report["status"], "PASS_GEOMETRIC_PIXEL_HEURISTIC")

    def test_first_side_flat_burgundy_hole_is_rejected_even_if_return_is_clean(self):
        # The *main* native 40-frame run on source 27b23da8 lost the obvious
        # brown return-side seam but first side frames 15..17 repeated the
        # same RGB(146,36,49) 36 / 41 / 33 times. Both arcs need protection.
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp),flat_rear=False,brown_hole_frames=(15,16,17)))
        self.assertEqual(report["status"],"REJECTED_FLAT_BROWN_FIRST_SIDE_CAVITY")
        self.assertTrue({15,16,17}.issubset(set(report["brownFlatFirstSideFrames"])))
        self.assertTrue(report["brownFlatFirstSideDetected"])
        self.assertFalse(report["brownFlatReturnSideDetected"])
        self.assertEqual(report["brownFlatReturnSideFrames"],[])
        self.assertFalse(report["artisticQualityApproved"])
        self.assertFalse(report["publicationReady"])

    def test_single_brown_first_side_frame_keeps_approval_blocked_without_false_alert(self):
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp),flat_rear=False,brown_hole_frames=(16,)))
        self.assertFalse(report["brownFlatFirstSideDetected"])
        self.assertEqual(report["status"],"PASS_GEOMETRIC_PIXEL_HEURISTIC")
        self.assertFalse(report["artisticQualityApproved"])
        self.assertFalse(report["publicationReady"])

    def test_licensed_style_flat_red_channel_plate_is_rejected_even_with_varying_green_and_blue(self):
        # Run 43018228841 passed the older RGB-mode detector despite R=145
        # occupying 46%/32% of first-side red surface on frames 15/16.
        with tempfile.TemporaryDirectory() as tmp:
            frames=synthetic_editor_sequence(Path(tmp), flat_rear=False)
            for frame_index in (15,16):
                with Image.open(frames[frame_index]) as img:
                    image=img.convert("RGBA")
                pixels=image.load()
                for y in range(66,87):
                    for x in range(17,49):
                        r,g,b,a=pixels[x,y]
                        if r>170 and g<100:
                            pixels[x,y]=(145,32+((x+y)%5),45+((x*3+y)%7),a)
                image.save(frames[frame_index])
            review=audit(frames)
        self.assertEqual(review["status"],"REJECTED_FLAT_RED_SIDE_CHANNEL")
        self.assertEqual(review["flatRedFirstSideFrames"],[15,16])
        self.assertTrue(review["flatRedChannelDetected"])
        self.assertFalse(review["artisticQualityApproved"])
        self.assertFalse(review["publicationReady"])

    def test_one_flat_red_channel_frame_is_only_warning_not_a_release_certificate(self):
        with tempfile.TemporaryDirectory() as tmp:
            frames=synthetic_editor_sequence(Path(tmp), flat_rear=False)
            with Image.open(frames[15]) as img:
                image=img.convert("RGBA")
            pixels=image.load()
            for y in range(66,87):
                for x in range(17,49):
                    r,g,b,a=pixels[x,y]
                    if r>170 and g<100:
                        pixels[x,y]=(145,32+((x+y)%5),45+((x+y*3)%7),a)
            image.save(frames[15])
            review=audit(frames)
        self.assertIn(15,review["flatRedFirstSideFrames"])
        self.assertFalse(review["flatRedChannelDetected"])
        self.assertFalse(review["artisticQualityApproved"])

    def test_warm_orange_gradient_return_cavity_without_flat_brown_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(
                Path(temp), flat_rear=False, gold_seam_frames=(26, 27),
                gold_color=(190, 75, 45), frame_count=38))
        self.assertEqual(report["status"], "REJECTED_WARM_RETURN_SIDE_CAVITY")
        self.assertEqual(report["warmReturnSideCavityFrames"], [26, 27])
        self.assertTrue(report["warmReturnSideCavityDetected"])
        self.assertEqual(report["goldReturnSideSeamFrames"], [])
        self.assertFalse(report["artisticQualityApproved"])
        self.assertFalse(report["publicationReady"])

    def test_preserved_surface_detail_only_passes_heuristic_not_art(self):
        with tempfile.TemporaryDirectory() as temp:
            report = audit(synthetic_editor_sequence(Path(temp), flat_rear=False))
        self.assertEqual(report["status"], "PASS_GEOMETRIC_PIXEL_HEURISTIC")
        self.assertEqual(report["lowDetailRearFrames"], [])
        self.assertFalse(report["artisticQualityApproved"])
        self.assertFalse(report["publicationReady"])


if __name__ == "__main__":
    unittest.main()
