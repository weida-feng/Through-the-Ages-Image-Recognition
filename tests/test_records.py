"""Cases that previously made manual imports and row-based joins fragile."""
from pathlib import Path
import tempfile
import unittest
from tta_pipeline.records import pair_by_code, read_records

class RecordTests(unittest.TestCase):

    def test_utf8_utf16_and_reordered_pairing(self):
        with tempfile.TemporaryDirectory() as temp:
            top = Path(temp) / 'top.txt'
            bottom = Path(temp) / 'bottom.txt'
            top.write_text('0 SAMPLEAA 孔子\n1 SAMPLEAB 凯撒\n', encoding='utf-16')
            bottom.write_text('8 SAMPLEAB 荷马\n9 SAMPLEAA 摩西\n', encoding='utf-8')
            pairs = list(pair_by_code(read_records(top), read_records(bottom)))
            self.assertEqual(pairs, [('SAMPLEAA', ('孔子',), ('摩西',)), ('SAMPLEAB', ('凯撒',), ('荷马',))])

    def test_duplicate_codes_do_not_silently_overwrite_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'duplicate.txt'
            source.write_text('0 SAMPLEAA 孔子\n1 SAMPLEAA 凯撒\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'duplicate game code'):
                read_records(source)

    def test_missing_counterpart_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            top = Path(temp) / 'top.txt'
            bottom = Path(temp) / 'bottom.txt'
            top.write_text('0 SAMPLEAA 孔子\n', encoding='utf-8')
            bottom.write_text('0 SAMPLEAB 凯撒\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'code mismatch'):
                list(pair_by_code(read_records(top), read_records(bottom)))
