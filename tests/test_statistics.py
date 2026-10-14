"""Guard statistical denominators, population filtering, and historical equivalence."""
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
try:
    import pandas as pd
    import openpyxl
except ImportError:
    HAS_ANALYSIS = False
else:
    HAS_ANALYSIS = True
    from tta_pipeline.preparation import prepare_archive
    from tta_pipeline.statistics import analyze_archive, build_statistics, leader_coverage, load_prepared, select_cohorts, summarize_cards, wilson_interval
    from tta_pipeline.statistics_reference import compare_statistics_reference
ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(HAS_ANALYSIS, 'Install the analysis extra to test statistics')
class StatisticsUnitTests(unittest.TestCase):

    def test_wilson_known_values_and_complement_symmetry(self):
        low, high = wilson_interval(5, 10)
        self.assertAlmostEqual(low, 0.23658959361548731)
        self.assertAlmostEqual(high, 0.7634104063845127)
        self.assertAlmostEqual(wilson_interval(0, 10)[1], 0.2775401687666166)
        self.assertAlmostEqual(wilson_interval(10, 10)[0], 0.7224598312333834)
        a, b = (wilson_interval(3, 10), wilson_interval(7, 10))
        self.assertAlmostEqual(a[0], 1 - b[1])
        self.assertAlmostEqual(a[1], 1 - b[0])

    def test_zero_sample_is_unestimated_and_invalid_counts_fail(self):
        self.assertTrue(all((math.isnan(x) for x in wilson_interval(0, 0))))
        for wins, total, z in ((-1, 10, 1.96), (11, 10, 1.96), (0, -1, 1.96), (1, 10, 0), (1, 10, math.nan)):
            with self.assertRaises(ValueError):
                wilson_interval(wins, total, z)

    def test_game_denominator_absent_leaders_and_unused_categories(self):
        games = pd.DataFrame({'game_code': ['ONE', 'TWO']})
        cards = pd.DataFrame({'game_code': ['ONE', 'ONE', 'TWO'], 'card_name': ['孔子', '无', '无'], 'is_win': [True, False, True], 'username': ['A', 'B', 'A']})
        metrics = summarize_cards(cards, 'leader', games, 'test').set_index('card_name')
        self.assertEqual(len(metrics), 48)
        self.assertNotIn('无', metrics.index)
        self.assertEqual(metrics.loc['孔子', 'selection_rate'], 0.5)
        self.assertEqual(metrics.loc['孔子', 'player_usage_rate'], 0.25)
        self.assertEqual(metrics.loc['孔子', 'win_rate'], 1)
        self.assertEqual(metrics.loc['摩西', 'usage_count'], 0)
        self.assertTrue(math.isnan(metrics.loc['摩西', 'win_rate']))
        empty = summarize_cards(cards, 'leader', games.iloc[:0], 'empty')
        self.assertTrue(empty.selection_rate.isna().all())

    def test_duplicate_use_cannot_inflate_game_selection_rate(self):
        games = pd.DataFrame({'game_code': ['ONE']})
        cards = pd.DataFrame({'game_code': ['ONE', 'ONE'], 'card_name': ['孔子', '孔子'], 'is_win': [True, False], 'username': ['A', 'B']})
        with self.assertRaisesRegex(ValueError, 'duplicate keys'):
            summarize_cards(cards, 'leader', games, 'test')

    def test_resignation_expiration_and_pending_review_views(self):
        games = pd.DataFrame({'game_code': ['A', 'B', 'C', 'D'], 'batch': ['5239', 'resign', 'resign', 'other'], 'has_resignation': [False, True, True, False], 'has_expiration': [False, True, False, True]})
        cohorts = select_cohorts(games, {'A'})
        self.assertEqual(cohorts['completed'].game_code.tolist(), ['A'])
        self.assertEqual(cohorts['resigned'].game_code.tolist(), ['B', 'C'])
        self.assertEqual(cohorts['resigned_no_expiration'].game_code.tolist(), ['C'])
        self.assertEqual(len(cohorts['all_processed']), 4)
        self.assertTrue(cohorts['completed_without_review_cases'].empty)

    def test_absent_coverage_uses_player_slots_as_denominator(self):
        games = pd.DataFrame({'game_code': ['ONE']})
        slots = pd.DataFrame({'game_code': ['ONE', 'ONE'], 'age': ['A', 'A'], 'card_name': ['孔子', '无'], 'is_win': [True, False]})
        coverage = leader_coverage(slots, games, 'test').set_index('age')
        self.assertEqual(coverage.loc['A', 'present_rate'], 0.5)
        self.assertEqual(coverage.loc['A', 'absent_losses'], 1)
        self.assertTrue(math.isnan(coverage.loc['I', 'present_rate']))

    def test_statistics_export_preserves_existing_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / 'report.md'
            marker.write_text('original', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                analyze_archive(Path('missing'), Path('missing'), Path(temp))
            self.assertEqual(marker.read_text(), 'original')
