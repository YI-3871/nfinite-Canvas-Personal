import os
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from color_preservation import preserve_image_colors, rgb_to_lab, delta_e76


def _make_reference(size=(240, 320)):
    image = Image.new("RGB", size, (242, 242, 242))
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 24, 90, 290), fill=(43, 46, 58))
    draw.rectangle((150, 28, 224, 292), fill=(86, 88, 92))
    draw.ellipse((82, 38, 166, 132), fill=(210, 168, 142))
    draw.rectangle((88, 125, 170, 260), fill=(36, 42, 55))
    return image


def _make_drifted_edit(reference):
    image = reference.copy()
    draw = ImageDraw.Draw(image)
    # The semantic edit must not be used as a color anchor.
    draw.rectangle((88, 125, 170, 260), fill=(55, 128, 190))
    red, green, blue = image.split()
    red = red.point(lambda value: min(255, value + 7))
    green = green.point(lambda value: max(0, value - 6))
    blue = blue.point(lambda value: min(255, value + 8))
    return Image.merge("RGB", (red, green, blue))


class ColorPreservationTests(unittest.TestCase):
    def test_hybrid_correction_preserves_dimensions_and_reduces_neutral_error(self):
        reference = _make_reference()
        generated = _make_drifted_edit(reference)
        with tempfile.TemporaryDirectory() as folder:
            reference_path = os.path.join(folder, "reference.png")
            generated_path = os.path.join(folder, "raw.png")
            corrected_path = os.path.join(folder, "corrected.png")
            reference.save(reference_path)
            generated.save(generated_path)

            result = preserve_image_colors(reference_path, generated_path, corrected_path, mode="strict", task_mode="outfit_swap")

            self.assertEqual(result["status"], "corrected", result)
            self.assertTrue(os.path.isfile(corrected_path))
            with Image.open(corrected_path) as corrected:
                self.assertEqual(corrected.size, generated.size)
                before = delta_e76(rgb_to_lab(reference.getpixel((30, 180))), rgb_to_lab(generated.getpixel((30, 180))))
                after = delta_e76(rgb_to_lab(reference.getpixel((30, 180))), rgb_to_lab(corrected.convert("RGB").getpixel((30, 180))))
                self.assertLess(after, before)

    def test_identical_image_is_not_reencoded(self):
        reference = _make_reference()
        with tempfile.TemporaryDirectory() as folder:
            reference_path = os.path.join(folder, "reference.png")
            corrected_path = os.path.join(folder, "corrected.png")
            reference.save(reference_path)
            result = preserve_image_colors(reference_path, reference_path, corrected_path, mode="auto", task_mode="outfit_swap")
            self.assertEqual(result["status"], "passthrough")
            self.assertFalse(os.path.exists(corrected_path))

    def test_scene_change_resets_baseline(self):
        reference = _make_reference()
        generated = _make_drifted_edit(reference)
        with tempfile.TemporaryDirectory() as folder:
            reference_path = os.path.join(folder, "reference.png")
            generated_path = os.path.join(folder, "raw.png")
            corrected_path = os.path.join(folder, "corrected.png")
            reference.save(reference_path)
            generated.save(generated_path)
            result = preserve_image_colors(reference_path, generated_path, corrected_path, mode="strict", task_mode="scene_change")
            self.assertEqual(result["status"], "passthrough")
            self.assertFalse(os.path.exists(corrected_path))

    def test_pose_change_allows_small_background_differences(self):
        reference = _make_reference()
        generated = _make_drifted_edit(reference)
        draw = ImageDraw.Draw(generated)
        draw.rectangle((5, 6, 42, 30), fill=(220, 225, 232))
        with tempfile.TemporaryDirectory() as folder:
            reference_path = os.path.join(folder, "reference.png")
            generated_path = os.path.join(folder, "raw.png")
            corrected_path = os.path.join(folder, "corrected.png")
            reference.save(reference_path)
            generated.save(generated_path)
            result = preserve_image_colors(reference_path, generated_path, corrected_path, mode="auto", task_mode="pose_change")
            self.assertEqual(result["status"], "corrected", result)
            with Image.open(corrected_path) as corrected:
                self.assertEqual(corrected.size, generated.size)


if __name__ == "__main__":
    unittest.main()
