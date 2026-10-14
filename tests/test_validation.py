import unittest
from tta_pipeline.catalog import leaders_by_age
from tta_pipeline.validation import check_cards

class ValidationTests(unittest.TestCase):

    def test_absent_leaders_are_not_shared_cards(self):
        findings = check_cards('SAMPLEAA', ('孔子', '无', '无', '无'), ('摩西', '无', '无', '无'), 'leader')
        self.assertEqual(findings, [])

    def test_real_shared_card_is_flagged(self):
        findings = check_cards('SAMPLEAA', ('大图书馆',), ('大图书馆',), 'wonder')
        self.assertEqual([f.rule for f in findings], ['shared_card'])

    def test_unknown_labels_are_visible(self):
        findings = check_cards('SAMPLEAA', ('未识别名称',), (), 'leader')
        self.assertEqual(findings[0].rule, 'unknown_name')

    def test_same_age_is_not_silently_discarded(self):
        with self.assertRaisesRegex(ValueError, 'Multiple leaders'):
            leaders_by_age(('孔子', '凯撒'))
        self.assertIn('repeated_age', {f.rule for f in check_cards('SAMPLEAA', ('孔子', '凯撒'), (), 'leader')})

    def test_missing_ages_are_padded(self):
        self.assertEqual(leaders_by_age(('孔子', '比尔盖茨')), ('孔子', '无', '无', '比尔盖茨'))
