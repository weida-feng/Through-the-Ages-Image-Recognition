"""Check public table integrity and the actual archived-model demonstration."""
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
try:
    import pandas
    from tta_pipeline.statistics import load_prepared
except ImportError:
    HAS_ANALYSIS = False
else:
    HAS_ANALYSIS = True
try:
    HAS_LEGACY_VISION = version("scikit-learn") == "0.24.1" and version("opencv-python") == "4.5.3.56"
except PackageNotFoundError:
    HAS_LEGACY_VISION = False


class PublicAssetTests(unittest.TestCase):
    def test_public_inputs_match_recorded_hashes(self):
        for folder, manifest in (("data/demo", "selection.json"), ("assets/demo", "examples.json")):
            metadata = json.loads((ROOT / folder / manifest).read_text(encoding="utf-8"))
            for name, expected in metadata["input_sha256"].items():
                with self.subTest(name=name):
                    self.assertEqual(hashlib.sha256((ROOT / folder / name).read_bytes()).hexdigest(), expected)


@unittest.skipUnless(HAS_ANALYSIS, "Install the analysis extra for public-table validation")
class PublicDataTests(unittest.TestCase):
    def test_curated_real_tables_validate_with_consistent_pseudonyms(self):
        tables = load_prepared(ROOT / "data/demo")
        self.assertEqual(len(tables["games"]), 20)
        self.assertEqual(len(tables["players"]), 40)
        self.assertEqual(len(tables["leader_slots"]), 160)
        self.assertEqual(len(tables["wonders"]), 92)
        self.assertEqual(int(tables["games"].has_resignation.sum()), 5)
        for name, frame in tables.items():
            self.assertTrue(frame.game_code.str.fullmatch(r"DEMO\d{4}").all(), name)
            self.assertFalse(any(column.startswith("source_") for column in frame), name)
            if "username" in frame:
                self.assertTrue(frame.username.str.fullmatch(r"player_\d{3}").all(), name)


@unittest.skipUnless(HAS_LEGACY_VISION, "Use the pinned legacy vision environment")
class PublicModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tta_pipeline.recognition import CardPredictor
        cls.models = {kind: CardPredictor.load(ROOT / "assets/models", kind)
                      for kind in ("leader", "wonder")}

    def test_selected_card_crops_match_the_historical_references(self):
        expected = (("leader_confucius.jpg", "leader", "孔子"),
                    ("wonder_great_library.jpg", "wonder", "大图书馆"),
                    ("wonder_silk_road.jpg", "wonder", "丝绸之路"))
        for filename, kind, label in expected:
            with self.subTest(filename=filename):
                self.assertEqual(self.models[kind].predict(ROOT / "assets/demo" / filename), label)

    def test_same_class_label_cannot_distinguish_empty_region_and_real_card(self):
        from tta_pipeline.capture import template_difference
        from tta_pipeline.cropping import read_grayscale
        template = read_grayscale(ROOT / "assets/templates/nowonder.jpg")
        empty = ROOT / "assets/demo/empty_wonder.jpg"
        real = ROOT / "assets/demo/wonder_silk_road.jpg"
        self.assertEqual(self.models["wonder"].predict(empty), "丝绸之路")
        self.assertEqual(self.models["wonder"].predict(real), "丝绸之路")
        self.assertLess(template_difference(template, read_grayscale(empty)), 5000)
        self.assertGreaterEqual(template_difference(template, read_grayscale(real)), 5000)
