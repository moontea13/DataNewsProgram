"""Small behavior tests for the errors that would invalidate the news metrics."""
import unittest
from export_news import Exporter
from common import ratio, quantiles
from prepare import title_core
from story_rules import code, validate

class Invariants(unittest.TestCase):
    def test_season_normalization_does_not_erase_story_numbers(self):
        self.assertEqual(title_core('穿越七零：七个孩子第十二季', 'S12'), '穿越七零七个孩子')
        self.assertEqual(title_core('全家2', 'N02'), '全家2')
        self.assertEqual(title_core('故事第二季', 'SU'), '故事第二季')

    def test_unavailable_is_not_zero(self):
        self.assertIsNone(ratio(0, 0)['percent'])
        self.assertEqual(ratio(0, 169)['percent'], 0)
        self.assertIsNone(quantiles([])['median'])

    def test_series_rate_counts_union_not_edges(self):
        exporter = object.__new__(Exporter)
        pairs = [{'series_a':'A','series_b':'B','score':.9}, {'series_a':'A','series_b':'C','score':.86},
                 {'series_a':'B','series_b':'C','score':.3}]
        summary = exporter.sim_summary(pairs, ['A','B','C'], .85)
        self.assertEqual(summary['series_rate']['numerator'], 3)
        self.assertEqual(summary['pair_rate']['numerator'], 2)
        self.assertEqual(summary['series_rate']['percent'], 100)

    def test_coding_evidence_and_explicit_negation(self):
        record = {'series_id':'A','work_id':'A-S01','material_id':'M','series_title':'测试',
                  'description':'没有系统。少年被陷害后，凭借医术救治病人。'}
        result = code(record)
        self.assertFalse(validate(result))
        self.assertNotIn('系统金手指', [v['label'] for v in result['reversal_type']])
        self.assertIn('医术或专业技能', [v['label'] for v in result['reversal_type']])

    def test_no_evidence_remains_unknown(self):
        result = code({'series_id':'A','work_id':'A','material_id':'M','series_title':'系统重生', 'description':'故事继续。'})
        self.assertEqual(result['genre_primary'], '未知')
        self.assertFalse(result['reversal_type'])

if __name__ == '__main__':
    unittest.main()
