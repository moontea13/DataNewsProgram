"""核对方案明确要求的集合及评论计数场景。"""
import unittest
from pathlib import Path
from collections import Counter
from pipeline import novelty, comment_statistics, read_json, read_csv, ANN, BASE, load_comments, sha


class StatisticsTests(unittest.TestCase):
    def test_observation_period_sets_and_same_month(self):
        def row(m,w,s,c):
            return dict(month=m,work_id=w,series_id=s,cluster_id=c,title=w,evidence_excerpt='原文')
        rows=[row('07','A1','A','C1'),row('08','A1','A','C1'),row('08','A2','A','C1'),
              row('08','B1','B','C2'),row('08','C1','C','C2'),row('08','D1','D','C1'),row('08','E1','E','')]
        m1,m2,detail=novelty(rows)
        self.assertEqual(m1[1]['new_work_count'],5)
        self.assertEqual(m1[1]['new_series_count'],4)
        self.assertEqual(m1[1]['new_cluster_count'],1)
        self.assertEqual(m2[1]['codable_new_series_count'],3)
        self.assertEqual(m2[1]['reused_series_count'],1)
        self.assertEqual(m2[1]['reuse_ratio'],1/3)
        self.assertEqual(m2[1]['new_structure_series_count'],2)
        self.assertEqual(m2[1]['unassigned_new_series_count'],1)
        self.assertEqual({r['reuse_category'] for r in detail if r['series_id'] in ['B','C']},{'进入当月新结构'})

    def test_no_codable_new_series_is_blank(self):
        rows=[dict(month=m,work_id=m,series_id=m,cluster_id='',title=m,evidence_excerpt='') for m in ['07','08']]
        self.assertIsNone(novelty(rows)[1][1]['reuse_ratio'])

    def test_multi_object_only_once_in_metric3(self):
        comments=[dict(comment_key='a',work_id='w1',series_id='s1',eligibility='有效观众候选',work_title_as_captured='甲'),
                  dict(comment_key='b',work_id='w2',series_id='s2',eligibility='有效观众候选',work_title_as_captured='乙')]
        ops=[dict(comment_key='a',comparison_scope='不同系列',object=o,similarity_relation='指出相似',attitude='接受或喜爱重复') for o in ['剧情套路','角色外形']]
        result=comment_statistics(comments,ops)
        self.assertEqual(result[0][0]['numerator'],1)
        self.assertEqual(result[0][0]['denominator'],2)
        self.assertEqual(result[0][1]['ratio'],0.5)
        self.assertEqual(sum(r['comment_count'] for r in result[3]),2)

    def test_difference_and_internal_similarity_not_in_numerator(self):
        c=[dict(comment_key='a',work_id='w',series_id='s',eligibility='有效观众候选',work_title_as_captured='甲')]
        for scope,rel in [('不同系列','强调不同'),('同剧内部','指出相似'),('未说明','指出相似')]:
            ops=[dict(comment_key='a',comparison_scope=scope,object='剧情套路',similarity_relation=rel,attitude='未表态')]
            self.assertEqual(comment_statistics(c,ops)[0][0]['numerator'],0)

    def test_saved_semantic_examples(self):
        comments,ops=load_comments(read_json(ANN/'input_index.json'))
        by_id={c['local_id']:c for c in comments}
        self.assertFalse(by_id['R0206']['explicit_cross_series_similarity'])
        self.assertTrue(by_id['R0241']['explicit_cross_series_similarity'])
        self.assertFalse(by_id['R0329']['explicit_cross_series_similarity'])
        self.assertFalse(by_id['R0244']['explicit_cross_series_similarity'])
        self.assertTrue(any(o['local_id']=='R0718' and o['attitude']=='接受或喜爱重复' for o in ops))
        self.assertEqual(by_id['R0289']['eligibility'],'作者角色待判断')


@unittest.skipUnless((BASE/'logs/定稿执行清单.json').exists(),'尚未生成定稿')
class FinalDataTests(unittest.TestCase):
    def setUp(self):
        self.out=BASE/'results/reviewed'

    def test_user_decisions_and_exclusions(self):
        ss={s['anonymous_series']:s for s in read_csv(self.out/'系列结构标注.csv')}
        self.assertEqual(ss['S009']['turning_mechanism'],'关系支持')
        self.assertEqual(ss['S020']['cluster_id'],'C008')
        self.assertEqual(ss['S020']['turning_mechanism'],'超常能力或体质')
        self.assertEqual(ss['S013']['core_conflict'],'其他／未交代')
        self.assertEqual(ss['S016']['cluster_id'],'')
        self.assertEqual(ss['S048']['cluster_id'],'')
        self.assertEqual(ss['S082']['response_path'],'专业知识技术破局')
        self.assertEqual(ss['S082']['cluster_id'],'')
        self.assertIn('youtube.com',ss['S189']['source_url'])
        self.assertEqual(ss['S047']['cluster_id'],'C085')
        self.assertTrue(all(s['exclusion_reason'] for s in ss.values() if not s['cluster_id']))

    def test_final_catalog_members_names_and_nodes_reconcile(self):
        ss=read_csv(self.out/'系列结构标注.csv')
        cc={c['cluster_id']:c for c in read_csv(self.out/'结构簇目录.csv')}
        rr=read_csv(self.out/'榜单簇归属.csv')
        self.assertEqual(len(rr),400)
        self.assertEqual(sum(bool(s['cluster_id']) for s in ss),180)
        self.assertEqual(len(cc),85)
        self.assertEqual(sum(bool(r['cluster_id']) for r in rr),374)
        for cid,c in cc.items():
            actual={s['series_id'] for s in ss if s['cluster_id']==cid}
            self.assertEqual(actual,set(__import__('json').loads(c['member_series_ids'])))
            self.assertEqual(len(actual),int(c['member_count']))
        self.assertTrue(all(not r['cluster_id'] or r['cluster_name']==cc[r['cluster_id']]['cluster_name'] for r in rr))

    def test_confirmation_provenance_not_fabricated_for_new_clusters(self):
        authorization=read_json(ANN/'final_authorization.json')
        self.assertTrue(authorization['bulk_review_confirmed'])
        rows=read_csv(BASE/'review/簇校审表.csv')
        self.assertEqual(sum(r['human_review_status']=='人工已审' for r in rows),70)
        self.assertEqual(sum(r['human_review_status']=='不适用：确认后授权新增' for r in rows),15)
        self.assertTrue(all(not r['reviewer'] for r in rows if r['human_review_status'].startswith('不适用')))

    def test_uncertain_comparisons_excluded_but_valid_parent_kept(self):
        ops=read_csv(self.out/'评论观点明细.csv')
        excluded=read_csv(self.out/'评论不确定观点排除.csv')
        cs={c['comment_key']:c for c in read_csv(self.out/'评论筛选与标签.csv')}
        self.assertEqual(len(excluded),28)
        self.assertTrue(all(o['comparison_scope']!='待人工判断' for o in ops))
        self.assertTrue(all(o['exclusion_reason'] for o in excluded))
        self.assertTrue(any(cs[o['comment_key']]['eligibility']=='有效观众' for o in excluded))
        m=read_csv(self.out/'指标3_相似反馈统计.csv')
        self.assertEqual((m[0]['numerator'],m[0]['denominator']),('27','3049'))

    def test_source_hashes_and_supplement_origin(self):
        m=read_json(BASE/'logs/定稿执行清单.json')
        for f in m['input_hashes']:
            self.assertEqual(sha(BASE.parent/f['path']),f['sha256'])
        ws=read_csv(self.out/'作品结构初标.csv')
        s189=next(w for w in ws if w['anonymous_series']=='S189')
        self.assertEqual(s189['description_original'],'')
        self.assertTrue(s189['annotation_text'])
        self.assertIn('释义',s189['evidence_origin'])
        self.assertEqual(len(read_csv(self.out/'系列结构排除清单.csv')),16)


if __name__=='__main__':
    unittest.main(verbosity=2)
