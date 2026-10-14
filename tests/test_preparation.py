"""Guard against row-based joins, false string flags, and concealed historical conflicts."""
import json
from pathlib import Path
import tempfile
import unittest
try:
    import pandas as pd
    import openpyxl
except ImportError:
    HAS_ANALYSIS = False
else:
    HAS_ANALYSIS = True
    from tta_pipeline.preparation import attach_players, build_prepared_tables, join_game_sources, prepare_archive, recognition_tables
    from tta_pipeline.reconciliation import check_text_players, compare_historical_excel
    from tta_pipeline.sources import normalize_source, parse_flag, players_from_source
ROOT = Path(__file__).resolve().parents[1]

def source_fixture():
    rows = []
    for index, (code, first_position, first_win) in enumerate((('SAMPLEAA', 1, True), ('SAMPLEAB', 0, False))):
        rows.append({'game_code': code, 'source_sequence_number': index + 10, 'source_file': 'source.xlsx', 'source_sheet': 'Games', 'source_row': index + 2, 'player1_username': 'NA', 'player1_position': first_position, 'player1_is_win': first_win, 'player1_is_resigned': False, 'player1_is_expired': False, 'player2_username': 'Other', 'player2_position': 1 - first_position, 'player2_is_win': not first_win, 'player2_is_resigned': False, 'player2_is_expired': False})
    return normalize_source(pd.DataFrame(rows), 'test source')

@unittest.skipUnless(HAS_ANALYSIS, 'Install the analysis extra to test pandas preparation')
class PreparationUnitTests(unittest.TestCase):

    def test_false_strings_and_invalid_flags_are_not_truthy_values(self):
        for value in (False, 0, '0', 'FALSE', ' false '):
            self.assertFalse(parse_flag(value))
        for value in (True, 1, '1', 'TRUE'):
            self.assertTrue(parse_flag(value))
        for value in ('', None, 'unknown', 2):
            with self.assertRaises(ValueError):
                parse_flag(value)

    def test_shuffled_sources_and_player_slots_preserve_identity_and_outcome(self):
        games = pd.DataFrame({'game_code': ['SAMPLEAB', 'SAMPLEAA'], 'batch': ['test', 'test']})
        joined = join_game_sources(games, {'source': source_fixture()}, {'test': 'source'})
        players = players_from_source(joined, {'top': 0, 'bottom': 1})
        keyed = players.set_index(['game_code', 'player_position'])
        self.assertEqual(keyed.loc[('SAMPLEAA', 0), 'username'], 'Other')
        self.assertFalse(keyed.loc[('SAMPLEAA', 0), 'is_win'])
        self.assertEqual(keyed.loc[('SAMPLEAB', 0), 'username'], 'NA')
        self.assertEqual(keyed.loc[('SAMPLEAA', 1), 'screenshot_position'], 'bottom')

    def test_missing_duplicate_and_null_source_keys_fail_before_export(self):
        games = pd.DataFrame({'game_code': ['SAMPLEAA', 'SAMPLEAB'], 'batch': ['test', 'test']})
        source = source_fixture()
        with self.assertRaisesRegex(ValueError, 'Missing player source'):
            join_game_sources(games, {'source': source.iloc[:1]}, {'test': 'source'})
        with self.assertRaisesRegex(ValueError, 'duplicate keys'):
            join_game_sources(games, {'source': pd.concat([source, source.iloc[:1]])}, {'test': 'source'})
        invalid = source.copy()
        invalid.loc[0, 'game_code'] = None
        with self.assertRaisesRegex(ValueError, 'missing join key'):
            join_game_sources(games, {'source': invalid}, {'test': 'source'})

    def test_invalid_positions_and_ambiguous_winners_are_rejected(self):
        source = source_fixture()
        invalid = source.copy()
        invalid.loc[0, 'player1_position'] = invalid.loc[0, 'player2_position']
        with self.assertRaisesRegex(ValueError, 'share a position'):
            normalize_source(invalid, 'test')
        for flag in (False, True):
            invalid = source.copy()
            invalid.loc[0, ['player1_is_win', 'player2_is_win']] = flag
            with self.assertRaisesRegex(ValueError, 'exactly one winner'):
                normalize_source(invalid, 'test')

    def test_card_join_does_not_drop_an_unmatched_player(self):
        players = players_from_source(source_fixture(), {'top': 0, 'bottom': 1})
        players['outcome'] = players.is_win.map({True: 'win', False: 'loss'})
        cards = pd.DataFrame({'game_code': ['MISSINGA'], 'player_position': [0]})
        with self.assertRaisesRegex(ValueError, 'no matched player'):
            attach_players(cards, players)

    def test_mixed_encoding_absent_leaders_and_variable_wonder_count(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'historical/test'
            folder.mkdir(parents=True)
            (folder / 'leaders.txt').write_text('9 SAMPLEAA 孔子 无 无 无 摩西 无 无 无\n', encoding='utf-16')
            from tta_pipeline._labels import WONDER_NAMES
            names = list(WONDER_NAMES[:9])
            (folder / 'top.txt').write_text('0 SAMPLEAA ' + ' '.join(names) + '\n', encoding='utf-8')
            (folder / 'bottom.txt').write_text('8 SAMPLEAA\n', encoding='utf-16')
            manifest = {'canonical_batches': ['test'], 'batches': {'test': {'role': 'test', 'expected_games': 1, 'leaders_matrix': 'leaders.txt', 'wonders_top': 'top.txt', 'wonders_bottom': 'bottom.txt'}}}
            games, leaders, wonders = recognition_tables(root, manifest, {'top': 0, 'bottom': 1})
            self.assertEqual(len(games), 1)
            self.assertEqual(leaders.is_present.sum(), 2)
            self.assertEqual(leaders.loc[~leaders.is_present, 'card_name'].unique().tolist(), ['无'])
            self.assertEqual(wonders.card_index.tolist(), list(range(9)))

    def test_text_conflicts_are_logged_only_with_an_explicit_source_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'historical/test'
            folder.mkdir(parents=True)
            (folder / 'players.txt').write_text('0 SAMPLEAA NA 1 FALSE Other 0 FALSE\n', encoding='utf-8')
            spec = {'batch': 'test', 'file': 'players.txt', 'source': 'source', 'value_fields': 6, 'outcome_resolution': 'source_workbook'}
            differences, report = check_text_players(root, {'text_player_checks': [spec]}, {'source': source_fixture()})
            self.assertEqual(len(differences), 1)
            self.assertEqual(differences.iloc[0].resolution, 'source_workbook')
            self.assertEqual(report['test']['outcome_mismatch_games'], 1)
            spec['outcome_resolution'] = 'require_equal'
            with self.assertRaisesRegex(ValueError, 'winner flags disagree'):
                check_text_players(root, {'text_player_checks': [spec]}, {'source': source_fixture()})

    def test_export_refuses_to_overwrite_existing_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / 'preserved.csv'
            marker.write_text('original', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                prepare_archive(Path('does-not-exist'), Path(temp))
            self.assertEqual(marker.read_text(), 'original')
