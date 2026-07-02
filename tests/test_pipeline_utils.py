import unittest

from src.yolo_detect import classify_detected_objects
from api.main import extract_keywords


class PipelineUtilsTests(unittest.TestCase):
    def test_classify_promotional_posts(self):
        self.assertEqual(classify_detected_objects(["person", "bottle"]), "promotional")

    def test_classify_product_display_posts(self):
        self.assertEqual(classify_detected_objects(["bottle", "container"]), "product_display")

    def test_extract_keywords_filters_noise(self):
        text = "Paracetamol 500mg is available now at a great price"
        self.assertEqual(extract_keywords(text, 3), ["paracetamol", "500mg", "available"])


if __name__ == "__main__":
    unittest.main()
