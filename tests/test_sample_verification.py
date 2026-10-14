"""Check honest reference comparison and exercise real models in the pinned environment."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from importlib.metadata import PackageNotFoundError, version
from tta_pipeline.pipeline import recognize_with_predictors
from tta_pipeline.recognition import CardPredictor
from tta_pipeline.sample_verification import compare_sequences, sample_inputs, verify_examples
ROOT = Path(__file__).resolve().parents[1]
try:
    HAS_LEGACY_VISION = version('scikit-learn') == '0.24.1' and version('opencv-python') == '4.5.3.56'
except PackageNotFoundError:
    HAS_LEGACY_VISION = False

class SampleVerificationUnitTests(unittest.TestCase):

    def test_order_and_length_changes_cannot_be_hidden_by_partial_comparison(self):
        self.assertTrue(compare_sequences(['A', 'B'], ['A', 'B'])['matches'])
        self.assertFalse(compare_sequences(['A', 'B'], ['B', 'A'])['matches'])
        self.assertFalse(compare_sequences(['A', 'B'], ['A'])['matches'])
        self.assertFalse(compare_sequences([], ['A'])['matches'])

    def test_missing_screenshot_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'examples/test/SAMPLEAA').mkdir(parents=True)
            config = {'groups': {'test': {'expected_games': 1}}, 'expected_games': 1, 'expected_saved_crops': 0}
            (root / 'examples.json').write_text(json.dumps(config), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Missing screenshot'):
                sample_inputs(root)

    def test_duplicate_sample_codes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for group in ('one', 'two'):
                folder = root / 'examples' / group / 'SAMPLEAA'
                folder.mkdir(parents=True)
                (folder / 'img.jpg').touch()
            config = {'groups': {name: {'expected_games': 1} for name in ('one', 'two')}, 'expected_games': 2, 'expected_saved_crops': 0}
            (root / 'examples.json').write_text(json.dumps(config), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'duplicate example code'):
                sample_inputs(root)

    def test_existing_verification_outputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / 'report.md'
            marker.write_text('preserve', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                verify_examples(Path('missing'), Path('missing'), Path(temp))
            self.assertEqual(marker.read_text(), 'preserve')

    def test_mismatched_sklearn_version_fails_before_unpickling_models(self):
        load = Mock()
        with patch.dict('sys.modules', {'joblib': SimpleNamespace(load=load), 'sklearn': SimpleNamespace(__version__='wrong')}):
            with self.assertRaisesRegex(RuntimeError, 'require scikit-learn 0.24.1'):
                CardPredictor.load(ROOT / 'assets/models', 'leader')
        load.assert_not_called()

    def test_cached_predictors_must_match_the_requested_card_kinds(self):
        models = {'leader': SimpleNamespace(kind='wonder'), 'wonder': SimpleNamespace(kind='leader')}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'new'
            with self.assertRaisesRegex(ValueError, 'matching leader and wonder'):
                recognize_with_predictors(Path('missing.jpg'), 'SAMPLEAA', models, output)
            self.assertFalse(output.exists())
