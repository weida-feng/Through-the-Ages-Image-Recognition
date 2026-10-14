import unittest
import numpy as np
from tta_pipeline.capture import template_difference
from tta_pipeline.cropping import extract_crops, feature_vector

class VisionTests(unittest.TestCase):

    def test_uint8_detector_uses_full_sum_and_preserves_crop_dimensions(self):
        image = np.zeros((2160, 3840), dtype=np.uint8)
        image[1377, 454:464] = 100
        image[1163, 464:474] = 80
        crops = extract_crops(image)
        self.assertEqual(len(crops['p1']), 1)
        self.assertEqual(crops['p1'][0].shape, (144, 144))
        self.assertEqual(len(crops['w1']), 1)
        self.assertEqual(crops['w1'][0].shape, (64, 120))
        self.assertEqual(crops['p2'], [])

    def test_leader_feature_is_the_center_not_the_full_crop(self):
        image = np.zeros((144, 144), dtype=np.uint8)
        image[48:96, 48:96] = 123
        vector = feature_vector(image, 'leader')
        self.assertEqual(vector.shape, (1, 2304))
        self.assertTrue(np.all(vector == 123))

    def test_changed_screenshot_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '3840 x 2160'):
            extract_crops(np.zeros((1080, 1920), dtype=np.uint8))

    def test_template_difference_does_not_wrap_uint8(self):
        a = np.zeros((52, 379), dtype=np.uint8)
        b = np.full((52, 379), 255, dtype=np.uint8)
        self.assertEqual(template_difference(a, b), 255 * 50 * 50)
