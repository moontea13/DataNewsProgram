"""Build ready-to-display JSON/CSV, metrics, provenance and an offline QA preview."""
import argparse
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import hashlib
import html
import math
import re
import numpy as np
from common import (DEFAULT_SOURCE, DEFAULT_OUTPUT, RESULTS, ROOT, MONTHS, THRESHOLDS,
                    WARNINGS, load, save, csv_save, sha256, ratio, quantiles, envelope)

class Exporter:
    def __init__(self, source=DEFAULT_SOURCE, output=DEFAULT_OUTPUT):
        self.source, self.output = Path(source), Path(output)
        self.hg = self.source / '红果400条交付'
        self.rankings = load(self.hg / '系列合并/上榜记录_系列季映射.json')
        self.works = load(self.hg / '系列合并/季作品表.json')
        self.series = load(self.output / 'data/series.json')
        self.registry = {r['series_id']: r for r in self.series}
        self.confirmed = {r['series_id'] for r in self.series if r['confirmed_group']}
        self.reps = load(RESULTS / 'representatives.json')
        self.coded = load(RESULTS / 'story_coding.json')
        self.coding = {r['series_id']: r for r in self.coded}
        self.exclude_pairs = {tuple(sorted([r['series_a'], r['series_b']])) for r in load(RESULTS / 'excluded_pairs.json')}
        self.metrics, self.files, self.similarities = [], [], {}
        self.brand_edges = load(self.hg / '关系核实/出品品牌_主体_系列季关系.json')
        self.brands_by_series = defaultdict(set)
        for edge in self.brand_edges:
            if edge['brand_name'] and edge['brand_name'] not in ['待认领', '待确认', '待核', '空值']:
                self.brands_by_series[edge['series_id']].add(edge['brand_name'])

    def metric(self, id_, title, value, unit='个', numerator=None, denominator=None,
               denominator_definition='', method='', section='', status='可展示', limits=None, sources=None):
        item = {'id': id_, 'title': title, 'value': value, 'unit': unit, 'numerator': numerator,
                'denominator': denominator, 'denominator_definition': denominator_definition,
                'method': method, 'section': section, 'status': status,
                'scope': '2026年7—10月红果月榜400条记录', 'sources': sources or [], 'limits': limits or []}
        self.metrics.append(item)
        return item

    def percentage(self, id_, title, n, d, definition, section, method='', status='可展示', limits=None):
        return self.metric(id_, title, ratio(n, d)['percent'], '%', n, d, definition, method, section, status, limits)

    def write(self, name, title, data, **kwargs):
        kwargs.setdefault('sources', sorted({r['source_url'] for r in self.rankings}) + ['data/sources.json'])
        item = envelope(name, title, data, **kwargs)
        save(self.output / f'data/{name}.json', item)
        self.files.append({'id': name, 'file': f'data/{name}.json', 'title': title, 'status': item['status'], 'chart': item['chart']})
        return item

    def table(self, name, rows, fields=None):
        csv_save(self.output / f'tables/{name}.csv', rows, fields)

    def scope_stats(self):
        data = load(RESULTS / 'sample_summary.json')
        for key, label in [('ranking_rows', '红果上榜记录'), ('work_candidates', '分季作品候选'),
                           ('confirmed_series', '有平台系列号的系列'), ('pending_units', '系列关系待核单元')]:
            self.metric('sample.' + key, label, data[key], section='基础样本')
        self.write('sample', '样本与有效材料', data, chart='cards', limits=WARNINGS)
        for s in self.series:
            sid = s['series_id']
            if sid in self.coding:
                s['story'] = self.coding[sid]
            s['producer_brands'] = sorted(self.brands_by_series[sid])
        save(self.output / 'data/series.json', self.series)
        self.table('系列资料', self.series)

    def context(self):
        audience = load(self.source / '补采/行业人数口径登记.json')
        self.write('audience', '受众规模：不同口径分别呈现', audience, unit='亿人', chart='timeline',
                   method='保留原有指标与数值属性，不计算跨口径增长率。',
                   limits=['1.2亿、预计超过6亿、预测7亿的指标口径不同，不能画成同口径实际观看人数趋势。'])
        self.metric('audience.actual_trend', '同口径实际观看人数趋势', None, section='1.1', status='数据不足',
                    limits=['未取得多个时间点的同口径实际观看人数。'])
        for i, row in enumerate(audience):
            self.metric(f'audience.point{i+1}', row['period'] + ' ' + row['measure'], row['value'], row['unit'],
                        section='1.1', status='仅供探索' if '预测' in row['value_type'] or '预计' in row['value_type'] else '可展示',
                        limits=[row['comparability'], row['value_type']], sources=[row['source_url']])
        governance = load(self.source / '补采/治理材料登记.json')
        quotes = ['治理同一剧集通过更换片名或主角姓名等方式，改头换面、反复播出',
                  '治理首页首屏首推和重点榜单推荐同质化问题，提升算法推荐内容的多样性']
        for item in governance:
            raw = (self.source.parent / item['source_file']).read_text(encoding='utf-8')
            flat = html.unescape(re.sub('<[^>]+>', '', raw))
            compact = re.sub(r'\s+', '', flat)
            item['quotes'] = []
            for quote in quotes:
                assert re.sub(r'\s+', '', quote) in compact, '治理引文必须能在本地原文找到'
                item['quotes'].append({'text': quote, 'exact_excerpt': True})
            item.pop('source_file', None)
            item['sample_relation'] = '7—10月榜单早于11月1日治理起始日；不据此检验治理效果，也不等于榜单作品违规。'
        self.write('governance', '治理背景与研究问题', governance, chart='quote', unit='', sources=[r['source_url'] for r in governance])
        self.table('受众规模来源', audience)

    def sequel_stats(self, months):
        monthly = []
        for month in months:
            rows = [r for r in self.rankings if r['month'] == month]
            known = [r for r in rows if r['series_id'] in self.confirmed]
            pending = [r for r in rows if r['series_id'] not in self.confirmed]
            groups = Counter(r['series_id'] for r in known)
            extra = sum(n - 1 for n in groups.values())
            top = sorted(groups, key=lambda sid: (-groups[sid], sid))[:10]
            monthly.append({'month': month, 'ranking_rows': len(rows), 'work_candidates': len({r['work_id'] for r in rows}),
                'known_series': len(groups), 'known_ranking_rows': len(known),
                'pending_units': len({r['series_id'] for r in pending}), 'pending_ranking_rows': len(pending),
                'confirmed_extra_slots': extra, 'confirmed_extra_slots_rate': ratio(extra, len(rows)),
                'multi_work_series': sum(n > 1 for n in groups.values()),
                'multi_work_series_slots': sum(n for n in groups.values() if n > 1),
                'multi_work_series_slots_rate': ratio(sum(n for n in groups.values() if n > 1), len(rows)),
                'max_series_slots': max(groups.values(), default=0),
                'top10': [{'series_id': sid, 'title': self.registry[sid]['title'], 'slots': groups[sid],
                           'share': ratio(groups[sid], len(rows)),
                           'ranking_details': [r for r in self.registry[sid]['ranking_details'] if r['month'] == month]} for sid in top]})
        return monthly

    def sequels(self):
        monthly = self.sequel_stats(MONTHS)
        all_heat = []
        for s in self.series:
            if not s['confirmed_group']:
                continue
            for month in MONTHS:
                positions = [r['rank'] for r in s['ranking_details'] if r['month'] == month]
                all_heat.append({'series_id': s['series_id'], 'title': s['title'], 'month': month,
                                 'slots': len(positions), 'best_rank': min(positions) if positions else None})
        repeat_counts = Counter(r['work_id'] for r in self.rankings)
        repeated = [{'work_id': wid, 'ranking_rows': n, 'extra_records': n - 1,
                     'ranking_ids': [r['ranking_id'] for r in self.rankings if r['work_id'] == wid]} for wid, n in repeat_counts.items() if n > 1]
        season = Counter('明确季号' if r['season_code'].startswith('S') and not r['season_code'].startswith('SU') else
                         '数字编号待核' if r['season_code'].startswith('N') else '未标季' for r in self.works)
        data = {'monthly': monthly, 'series_month_heatmap': all_heat, 'repeated_work_candidates': repeated,
                'season_status': [{'label': k, **ratio(v, len(self.works)), 'count': v} for k, v in season.items()],
                'series_ranking': sorted([{'series_id': s['series_id'], 'title': s['title'], 'work_count': s['work_count'],
                                           'ranking_count': s['ranking_count'], 'month_count': len(s['months']),
                                           'confirmed_group': s['confirmed_group']} for s in self.series], key=lambda r: (-r['ranking_count'], r['series_id']))}
        self.write('sequels', '同系列续作如何占据榜位', data, unit='个榜位', chart='grouped-bar',
                   denominator_definition='额外榜位率分母为当月100条记录；只累计有确认平台系列号的k−1。',
                   limits=['待核单元不计入已确认重复；跨月重复为作品候选口径。'])
        for row in monthly:
            self.percentage('sequels.extra.' + row['month'], row['month'] + '确认同系列额外榜位比例', row['confirmed_extra_slots'], row['ranking_rows'],
                            '当月全部榜位', '3.1', '确认系列占k席计k−1；待核关系不推断重复')
            self.metric('sequels.known.' + row['month'], row['month'] + '有平台系列号的系列数', row['known_series'], section='3.1')
            self.metric('sequels.pending.' + row['month'], row['month'] + '系列待核单元数', row['pending_units'], section='3.1')
            self.percentage('sequels.multi.' + row['month'], row['month'] + '多作品系列涉及榜位比例', row['multi_work_series_slots'], row['ranking_rows'], '当月全部榜位', '3.1')
        self.metric('sequels.repeated_candidates', '跨月重复上榜的作品候选数', len(repeated), section='3.1')
        self.metric('sequels.extra_records', '作品候选跨月重复增加的记录数', sum(r['extra_records'] for r in repeated), section='3.1')
        self.table('月度续作占榜', monthly)
        self.table('系列月份热力图', all_heat)
        self.table('跨月重复作品候选', repeated)
        return monthly

    def story_summary(self, allowed=None):
        coded = [r for r in self.coded if allowed is None or r['series_id'] in allowed]
        n = len(coded)
        fields = ['protagonist_identity', 'inciting_event', 'turning_point', 'reversal_type', 'setting']
        genre_counts = Counter(r['genre_primary'] for r in coded)
        genres = [{'label': label, 'count': count, **ratio(count, n)} for label, count in genre_counts.most_common()]
        distributions = {}
        for field in fields:
            counts = Counter(v['label'] for r in coded for v in r[field])
            valid = sum(bool(r[field]) for r in coded)
            distributions[field] = {'valid_series': valid, 'unknown_series': n - valid,
                'rows': [{'label': label, 'count': count, **ratio(count, valid), 'share_all_series': ratio(count, n)} for label, count in counts.most_common()]}
        top3 = [r['label'] for r in distributions['reversal_type']['rows'][:3]]
        eligible = {r['series_id'] for r in coded if r['reversal_type']}
        covered = {r['series_id'] for r in coded if set(v['label'] for v in r['reversal_type']) & set(top3)}
        matrix = []
        for genre in genre_counts:
            if genre == '未知':
                continue
            rows = [r for r in coded if r['genre_primary'] == genre and r['reversal_type']]
            for label in distributions['reversal_type']['rows']:
                count = sum(label['label'] in {v['label'] for v in r['reversal_type']} for r in rows)
                matrix.append({'genre': genre, 'reversal': label['label'], 'count': count, **ratio(count, len(rows))})
        templates = defaultdict(list)
        for r in coded:
            if all(r[field] for field in ['protagonist_identity', 'inciting_event', 'reversal_type']):
                # One series can contain several observed labels; exact full-set tuple is one structure fingerprint.
                key = tuple('、'.join(sorted({v['label'] for v in r[field]})) for field in ['protagonist_identity', 'inciting_event', 'reversal_type'])
                templates[key].append(r['series_id'])
        template_rows = sorted([{'identity': key[0], 'inciting_event': key[1], 'reversal': key[2],
                                 'count': len(ids), 'series_ids': ids} for key, ids in templates.items()], key=lambda r: (-r['count'], r['identity']))
        repeated = {sid for r in template_rows if r['count'] > 1 for sid in r['series_ids']}
        return {'n': n, 'genres': genres, 'fields': distributions, 'top3_reversals': top3,
                'top3_union': {**ratio(len(covered), len(eligible)), 'series_ids': sorted(covered)},
                'genre_reversal_matrix': matrix, 'templates': template_rows,
                'repeated_template_series': ratio(len(repeated), sum(len(ids) for ids in templates.values())),
                'coding_status': dict(Counter(r['status'] for r in coded)),
                'automatic_parse_failures': 0, 'unknown_genre': genre_counts.get('未知', 0)}

    def stories(self):
        data = self.story_summary()
        global_top3 = data['top3_reversals']
        monthly = []
        for month in MONTHS:
            allowed = {r['series_id'] for r in self.rankings if r['month'] == month}
            summary = self.story_summary(allowed)
            rows = [r for r in self.coded if r['series_id'] in allowed]
            valid = [r for r in rows if r['reversal_type']]
            covered = sum(bool({v['label'] for v in r['reversal_type']} & set(global_top3)) for r in valid)
            monthly.append({'month': month, 'series_with_description': len(rows), 'genres': summary['genres'], 'fields': summary['fields'],
                            'global_top3_reversal_union': ratio(covered, len(valid))})
        data['monthly'] = monthly
        data['pilot'] = load(RESULTS / 'story_pilot.json')
        self.write('story', '简介中的题材与剧情结构', data, chart='heatmap',
                   denominator_definition='题材用全部有效简介系列；多标签比例用该字段至少一个明确标签的系列；未知另列。',
                   method='固定词项规则与原文证据，主类按正向词项数选择；每系列一个代表简介。',
                   limits=['自动规则可能遗漏隐含情节、误认配角行为；不是人工语义标注。', '结构重复只是标签组合相同，不表示正片故事相同。'])
        for field, distribution in data['fields'].items():
            for item in distribution['rows']:
                self.percentage(f'story.{field}.{item["label"]}', item['label'] + '覆盖率', item['count'], distribution['valid_series'],
                                f'简介中{field}至少一个标签有证据的系列', '2.3', '词项规则识别；多选不相加')
        self.percentage('story.top3_union', '最常见三种翻盘表述的并集覆盖率', data['top3_union']['numerator'], data['top3_union']['denominator'],
                        '至少一种翻盘表述有证据的系列', '2.3', '固定全期Top 3，按系列并集去重')
        self.percentage('story.repeated_template', '重复剧情结构标签组合涉及的系列比例', data['repeated_template_series']['numerator'], data['repeated_template_series']['denominator'],
                        '身份、起因、翻盘方式三字段都有证据的系列', '2.3', '比较完整标签集合，非故事同一性判断')
        self.table('简介结构编码', self.coded)
        self.table('题材分布', data['genres'])
        self.table('题材翻盘矩阵', data['genre_reversal_matrix'])
        self.table('剧情结构组合', data['templates'])
        self.table('月度剧情构成', monthly)
        self.write('codebook', '自动编码词典及规则', load(RESULTS / 'codebook.json'), chart='table', unit='')
        self.keywords()

    def keywords(self):
        # Dictionary words plus literal recurrent phrases; all frequencies count series, never token occurrences.
        from story_rules import LABELS
        dictionary = {word for field in LABELS.values() for expression in field.values()
                      for word in re.findall(r'[\u4e00-\u9fff]{2,8}', expression)}
        dictionary |= {'主角', '命运', '逆天改命', '步步为营', '扮猪吃虎', '前世', '今生', '复仇', '穿越', '重生', '系统',
                       '灵根', '豪门', '霸总', '千金', '觉醒', '逆袭', '守护', '救赎', '真相', '打脸', '崛起', '破局'}
        title_patterns = {'我靠…': r'我靠', '谁说…': r'谁说', '开局…': r'开局', '…后…': r'后',
                          '…之…': r'之', '重生…': r'重生', '穿越…': r'穿越', '系统…': r'系统',
                          '…逆袭…': r'逆袭', '…神医…': r'神医', '…千金…': r'千金', '…修仙…': r'修仙'}
        descriptions = [r for r in self.reps if r['modality'] == 'description']
        titles = [r for r in self.reps if r['modality'] == 'title']
        outputs = {}
        for modality, rows, field in [('description', descriptions, 'description'), ('title', titles, 'title_core')]:
            words = []
            for word in sorted(dictionary):
                ids = [r['series_id'] for r in rows if word in r[field]]
                if len(ids) >= 2:
                    words.append({'phrase': word, 'count': len(ids), **ratio(len(ids), len(rows)), 'series_ids': ids})
            outputs[modality + '_phrases'] = sorted(words, key=lambda r: (-r['count'], -len(r['phrase']), r['phrase']))
        # Add data-derived segmented words when jieba is installed, with an explicit version tag.
        try:
            import jieba
            candidates = Counter(word for r in descriptions for word in set(jieba.lcut(r['description']))
                                 if re.fullmatch(r'[\u4e00-\u9fff]{2,6}', word) and word not in {'一个','自己','他们','为了','这个','成为','却是','可以','开始','之后','最终','一次','不断','面对','之中','如何','所有','没有','一场','一位','同时','之路','背后','原本','她们','随着','之间','直到','竟然','一步','从此','不仅','还是','那些','逐渐','通过','一名','之下','一切','以及','一步步'})
            outputs['segmented_words'] = [{'phrase': word, 'count': count, **ratio(count, len(descriptions))} for word, count in candidates.most_common(100) if count >= 3]
            outputs['segmentation'] = 'jieba ' + jieba.__version__
        except ImportError:
            outputs['segmented_words'] = []
            outputs['segmentation'] = '未安装jieba；固定词典词组仍完整提供'
        outputs['title_patterns'] = []
        for label, pattern in title_patterns.items():
            ids = [r['series_id'] for r in titles if re.search(pattern, r['title_core'])]
            outputs['title_patterns'].append({'label': label, 'count': len(ids), **ratio(len(ids), len(titles)), 'series_ids': ids})
        outputs['title_length'] = dict(sorted(Counter(len(r['title_core']) for r in titles).items()))
        outputs['patterns_by_genre'] = []
        for genre in sorted({r['genre_primary'] for r in self.coded}):
            group = [r for r in titles if self.coding.get(r['series_id'], {}).get('genre_primary') == genre]
            for label, pattern in title_patterns.items():
                n = sum(bool(re.search(pattern, r['title_core'])) for r in group)
                outputs['patterns_by_genre'].append({'genre': genre, 'pattern': label, 'count': n, **ratio(n, len(group))})
        self.write('phrases', '高频命名方式与简介词组', outputs, chart='bar', method='按包含词组的独立系列数统计；未作情节语义推断。')
        for key in ['title_phrases', 'description_phrases', 'title_patterns', 'patterns_by_genre', 'segmented_words']:
            self.table(key, outputs[key])

    def sim_summary(self, pairs, ids, threshold):
        selected = [p for p in pairs if p['score'] >= threshold]
        members = {sid for p in selected for sid in [p['series_a'], p['series_b']]}
        degree = Counter(sid for p in selected for sid in [p['series_a'], p['series_b']])
        connected = {sid for p in pairs for sid in [p['series_a'], p['series_b']]}
        valid_ids = sorted(set(ids) & connected)
        return {'threshold': threshold, 'series_rate': ratio(len(members), len(valid_ids)),
                'pair_rate': ratio(len(selected), len(pairs)), 'series_ids': sorted(members),
                'eligible_series_ids': valid_ids, 'isolated_by_exclusions': sorted(set(ids) - connected),
                'neighbor_counts': [{'series_id': sid, 'count': degree[sid]} for sid in valid_ids],
                'neighbor_count_distribution': [{'neighbors': k, 'series_count': v} for k, v in sorted(Counter(degree[sid] for sid in valid_ids).items())]}

    def similarity(self, modality):
        rows = [r for r in self.reps if r['modality'] == modality]
        ids = [r['series_id'] for r in rows]
        vectors = np.load(RESULTS / f'{modality}_embeddings.npy')
        meta = load(RESULTS / f'{modality}_model.json')
        assert meta['series_ids'] == ids
        assert meta['input_sha256'] == sha256(RESULTS / 'representatives.json'), 'Embeddings stale'
        assert np.isfinite(vectors).all() and np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4)
        matrix = np.clip(vectors @ vectors.T, -1, 1)
        pairs = []
        for i, left in enumerate(rows):
            for j in range(i + 1, len(rows)):
                right = rows[j]
                assert left['series_id'] != right['series_id']
                if tuple(sorted([left['series_id'], right['series_id']])) in self.exclude_pairs:
                    continue
                pairs.append({'series_a': left['series_id'], 'series_b': right['series_id'],
                              'title_a': left['series_title'], 'title_b': right['series_title'],
                              'work_a': left['work_id'], 'work_b': right['work_id'], 'score': float(matrix[i, j]),
                              'exact_same': left.get('pixel_sha256') == right.get('pixel_sha256') if modality == 'cover' else
                                            left['title_core'] == right['title_core'] if modality == 'title' else left['description'] == right['description']})
        pairs.sort(key=lambda r: (-r['score'], r['series_a'], r['series_b']))
        top3, maxima = [], []
        for sid in ids:
            candidates = [r for r in pairs if sid in (r['series_a'], r['series_b'])][:3]
            if candidates:
                maxima.append(candidates[0]['score'])
            for position, pair in enumerate(candidates, 1):
                other = pair['series_b'] if pair['series_a'] == sid else pair['series_a']
                top3.append({'series_id': sid, 'neighbor_series_id': other, 'position': position, 'score': pair['score']})
        thresholds = [self.sim_summary(pairs, ids, threshold) for threshold in THRESHOLDS]
        exact = [p for p in pairs if p['exact_same']]
        exact_members = {sid for p in exact for sid in [p['series_a'], p['series_b']]}
        # Unordered pairs, fixed-width bins with signed cosine support.
        edges = np.linspace(-1, 1, 41)
        counts, _ = np.histogram([p['score'] for p in pairs], bins=edges)
        histogram = [{'lower': round(float(edges[i]), 3), 'upper': round(float(edges[i + 1]), 3), 'count': int(n)} for i, n in enumerate(counts)]
        cases = []
        if pairs:
            for label, index in [('high', 0), ('upper_quartile', len(pairs)//4), ('middle', len(pairs)//2), ('low', len(pairs)-1)]:
                case = dict(pairs[index], band=label)
                case['series_a_detail'] = self.registry[case['series_a']]['representatives'][modality]
                case['series_b_detail'] = self.registry[case['series_b']]['representatives'][modality]
                cases.append(case)
        exact_pre = []
        if modality == 'title':
            for a, b in combinations(rows, 2):
                if a['title_core'] == b['title_core']:
                    exact_pre.append({'series_a': a['series_id'], 'series_b': b['series_id'], 'title_core': a['title_core'],
                                      'excluded_as_identity_uncertain': tuple(sorted([a['series_id'], b['series_id']])) in self.exclude_pairs})
        title = {'cover': '跨系列封面相似候选', 'title': '跨系列剧名相似候选', 'description': '跨系列简介相似候选'}[modality]
        data = {'valid_series': len(ids), 'valid_pairs': len(pairs), 'model': meta, 'thresholds': thresholds,
                'main_threshold': .85, 'exact_same': {'series_rate': ratio(len(exact_members), len(ids)), 'pairs': exact},
                'normalized_title_matches_before_identity_exclusion': exact_pre,
                'nearest_score_quantiles': quantiles(maxima), 'all_pair_quantiles': quantiles([p['score'] for p in pairs]),
                'histogram': histogram, 'top3': top3, 'cases': cases}
        self.write('similarity_' + modality, title, data, chart='histogram',
                   denominator_definition='系列占比：有可比对象的有效代表系列；配对占比：排除同系列及身份疑点后的无序配对。',
                   method=f'{meta["model"]}@{meta["revision"]}；余弦相似度≥0.85为主标准，另给0.80/0.90。',
                   limits=['阈值为本研究操作定义，未校准为人类视觉或语义判断；不能直接认定相同故事或抄袭。'])
        for entry in thresholds:
            n, d = entry['series_rate']['numerator'], entry['series_rate']['denominator']
            self.percentage(f'{modality}.series_rate.{entry["threshold"]:.2f}', f'{title}系列占比（≥{entry["threshold"]:.2f}）', n, d,
                            '有跨系列可比对象的有效代表系列', '2.' + ('1' if modality == 'cover' else '2' if modality == 'title' else '3'),
                            f'至少一个允许配对的余弦相似度≥{entry["threshold"]}；不含同系列续季')
            self.percentage(f'{modality}.pair_rate.{entry["threshold"]:.2f}', f'{title}配对占比（≥{entry["threshold"]:.2f}）',
                            entry['pair_rate']['numerator'], entry['pair_rate']['denominator'], '全部允许的无序跨系列配对', '2')
        self.percentage(f'{modality}.exact_same', title.replace('相似候选', '精确相同') + '涉及系列比例', len(exact_members), len(ids), '有效代表系列', '2', '像素哈希/规范标题/原始简介精确比较，身份疑点配对另列')
        self.table(f'{modality}_全部跨系列配对', pairs, ['series_a','series_b','title_a','title_b','work_a','work_b','score','exact_same'])
        self.table(f'{modality}_Top3', top3)
        self.table(f'{modality}_阈值敏感性', thresholds)
        save(RESULTS / f'{modality}_pairs.json', pairs)
        self.similarities[modality] = {'rows': rows, 'pairs': pairs, 'summary': data}
        return data

    def intersections(self):
        common = set.intersection(*[{r['series_id'] for r in value['rows']} for value in self.similarities.values()])
        sets, pair_sets = {}, {}
        for modality, value in self.similarities.items():
            pairs = [r for r in value['pairs'] if r['series_a'] in common and r['series_b'] in common]
            selected = [r for r in pairs if r['score'] >= .85]
            sets[modality] = {sid for r in selected for sid in [r['series_a'], r['series_b']]}
            pair_sets[modality] = {tuple(sorted([r['series_a'], r['series_b']])) for r in selected}
        rows = []
        names = {'cover': '封面', 'title': '剧名', 'description': '简介'}
        for size in [1, 2, 3]:
            for combo in combinations(['cover', 'title', 'description'], size):
                ids = set.intersection(*(sets[name] for name in combo))
                same_pairs = set.intersection(*(pair_sets[name] for name in combo))
                rows.append({'modalities': list(combo), 'label': '与'.join(names[name] for name in combo),
                             'series_rate': ratio(len(ids), len(common)), 'series_ids': sorted(ids),
                             'same_pair_count': len(same_pairs), 'same_pairs': [list(p) for p in sorted(same_pairs)]})
        # Distinguish a series having different neighbors in different modalities from one pair matching both.
        cases = []
        for a, b in sorted(pair_sets['cover'] & pair_sets['description'])[:12]:
            cases.append({'series_a': a, 'series_b': b,
                          'cover_score': next(p['score'] for p in self.similarities['cover']['pairs'] if (p['series_a'], p['series_b']) == (a, b)),
                          'description_score': next(p['score'] for p in self.similarities['description']['pairs'] if (p['series_a'], p['series_b']) == (a, b))})
        data = {'threshold': .85, 'common_series': len(common), 'rows': rows, 'cover_description_same_pair_cases': cases,
                'interpretation': '系列交集可能在各模态命中不同邻居；same_pairs才表示同一对系列同时达到标准。'}
        self.write('similarity_intersections', '封面、剧名、简介相似候选的交集', data, chart='intersection')
        self.table('跨模态相似交集', rows)

    def producers(self):
        by_brand = defaultdict(list)
        for edge in self.brand_edges:
            if edge['brand_name'] not in ['待认领', '待确认', '待核', '空值', '']:
                by_brand[edge['brand_name']].append(edge)
        ranking_map = {r['ranking_id']: r for r in self.rankings}
        table = []
        for brand, edges in by_brand.items():
            known = {e['series_id'] for e in edges if e['series_id'] in self.confirmed}
            pending = {e['series_id'] for e in edges if e['series_id'] not in self.confirmed}
            genre_counts = Counter(self.coding[sid]['genre_primary'] for sid in known if sid in self.coding)
            known_genres = {label: count for label, count in genre_counts.items() if label != '未知'}
            valid = sum(known_genres.values())
            dominant = max(known_genres, key=known_genres.get) if known_genres else None
            record_ids = {e['ranking_id'] for e in edges}
            slots_by_month = Counter(ranking_map[rid]['month'] for rid in record_ids)
            extras = 0
            for month in MONTHS:
                counts = Counter(ranking_map[rid]['series_id'] for rid in record_ids if ranking_map[rid]['month'] == month and ranking_map[rid]['series_id'] in self.confirmed)
                extras += sum(n - 1 for n in counts.values())
            table.append({'brand': brand, 'confirmed_series_count': len(known), 'pending_units': len(pending),
                          'series_ids': sorted(known), 'work_count': len({e['work_id'] for e in edges}),
                          'ranking_count': len(record_ids), 'monthly_ranking_count': dict(slots_by_month),
                          'confirmed_extra_slots': extras, 'genre_counts': dict(genre_counts),
                          'dominant_genre': dominant, 'dominant_genre_rate': ratio(known_genres[dominant], valid) if dominant else ratio(0, 0),
                          'genre_hhi': round(sum((n / valid) ** 2 for n in known_genres.values()), 6) if valid else None,
                          'supported_entities': sorted({e['entity_name_supported'] for e in edges if e['entity_name_supported']}),
                          'evidence_urls': sorted({e.get('source_url') or e.get('ranking_source_url') for e in edges if e.get('source_url') or e.get('ranking_source_url')})})
        table.sort(key=lambda r: (-r['confirmed_series_count'], -r['ranking_count'], r['brand']))
        concentration = []
        for k in [1, 5, 10]:
            selected = table[:k]
            members = {sid for r in selected for sid in r['series_ids']}
            concentration.append({'top_k': k, 'brands': [r['brand'] for r in selected],
                                  'series_ids': sorted(members), **ratio(len(members), len(self.confirmed))})
            self.percentage(f'producers.top{k}', f'前{k}家署名品牌覆盖系列比例', len(members), len(self.confirmed),
                            '全部有平台系列号的系列，含署名未知系列', '3.2', '按品牌确认系列数降序；联合出品按系列并集去重')
        matrix = []
        for row in table:
            for genre, count in row['genre_counts'].items():
                matrix.append({'brand': row['brand'], 'genre': genre, 'count': count, **ratio(count, row['confirmed_series_count'])})
        compared, comparison_rows = {}, []
        for modality, value in self.similarities.items():
            representatives = {r['series_id']: r for r in value['rows']}
            groups = defaultdict(list)
            pair_rows = []
            for pair in value['pairs']:
                a, b = pair['series_a'], pair['series_b']
                genre_a = self.coding.get(a, {}).get('genre_primary', '未知')
                genre_b = self.coding.get(b, {}).get('genre_primary', '未知')
                if genre_a == '未知' or genre_a != genre_b or representatives[a]['content_type'] != representatives[b]['content_type']:
                    continue
                brands_a, brands_b = self.brands_by_series[a], self.brands_by_series[b]
                if not brands_a or not brands_b:
                    continue
                if len(brands_a) != 1 or len(brands_b) != 1:
                    relation = '联合或跨季署名多方，单列'
                elif brands_a == brands_b:
                    relation = '同一家'
                else:
                    relation = '不同家'
                record = dict(pair, relation=relation, genre=genre_a, content_type=representatives[a]['content_type'],
                              brands_a=sorted(brands_a), brands_b=sorted(brands_b), modality=modality)
                pair_rows.append(record)
                groups[relation].append(pair['score'])
            rows = []
            for relation in ['同一家', '不同家', '联合或跨季署名多方，单列']:
                scores = groups[relation]
                row = {'modality': modality, 'relation': relation, 'quantiles': quantiles(scores),
                       'high_similarity_pair_rate': ratio(sum(s >= .85 for s in scores), len(scores))}
                rows.append(row)
                comparison_rows.append(row)
            compared[modality] = {'summary': rows, 'cases': sorted(pair_rows, key=lambda r: -r['score'])[:12]}
            self.table(modality + '_同家异家允许配对', pair_rows)
        unnamed = Counter(r['producer_raw'] for r in self.rankings if r['producer_raw'] in ['待认领', '待确认', '待核', ''])
        data = {'ranking': table, 'concentration': concentration, 'genre_matrix': matrix, 'comparison': compared,
                'missing_signature_rows': dict(unnamed), 'named_signature_ranking_rows': 400 - sum(unnamed.values()),
                'named_brands': len(table),
                'credit_method': '品牌多方完整计入，覆盖率按系列并集；同家/异家仅比较单一署名系列，联合及跨季署名变化单列。'}
        self.write('producers', '相似作品与出品署名', data, chart='heatmap',
                   limits=['品牌/账号与企业主体不等同。', '仅描述同题材、同内容形态内的配对差异，不做因果推断或独立样本显著性检验。'])
        self.table('出品方排名', table)
        self.table('出品方题材矩阵', matrix)
        self.table('同家异家相似度对比', comparison_rows)

    def adaptations(self):
        relations = load(self.hg / '关系核实/系列_原著作者关系.json')
        evidence = load(self.hg / '关系核实/改编证据登记.json')
        books = load(self.hg / '关系核实/红果原著官方书目.json')
        books_by_id = {r['book_id']: r for r in books}
        by_series, evidence_by_series = defaultdict(list), defaultdict(list)
        for r in relations:
            by_series[r['series_id']].append(r)
        for r in evidence:
            evidence_by_series[r['series_id']].append(r)
        categories = ['具体作品有直接改编声明', '系列有官方或媒体改编证据', '仅主创自述，身份或别名待核', '仅候选线索', '明确原创', '未知']
        statuses = []
        for s in self.series:
            sid = s['series_id']
            ev = evidence_by_series[sid]
            if any(r['evidence_level'].startswith('A_红果作品') for r in ev):
                status = categories[0]
            elif any(r['evidence_level'].startswith('A_原著官方') or '实地采访' in r['evidence_level'] for r in ev):
                status = categories[1]
            elif any('主创' in r['evidence_level'] for r in ev):
                status = categories[2]
            elif by_series[sid]:
                status = categories[3]
            else:
                status = categories[5]
            statuses.append({'series_id': sid, 'title': s['title'], 'confirmed_group': s['confirmed_group'],
                             'category': status, 'book_ids': sorted({r['book_id'] for r in by_series[sid]}),
                             'evidence_ids': [r['evidence_id'] for r in ev]})
        known = [r for r in statuses if r['confirmed_group']]
        category_counts = Counter(r['category'] for r in known)
        distribution = [{'label': name, 'count': category_counts[name], **ratio(category_counts[name], len(known))} for name in categories]
        pending = Counter(r['category'] for r in statuses if not r['confirmed_group'])
        candidates = {r['series_id'] for r in relations if r['series_id'] in self.confirmed}
        self.percentage('adaptation.candidate_coverage', '有原著线索的确认系列比例', len(candidates), len(known), '有平台系列号的系列', '3.3', '候选线索覆盖不等于确认改编')
        for row in distribution:
            self.percentage('adaptation.' + row['label'], row['label'] + '的系列比例', row['count'], len(known), '有平台系列号的系列', '3.3')
        nodes, edges = {}, []
        strong_by_book, strong_by_author = defaultdict(set), defaultdict(set)
        candidate_by_book, candidate_by_author = defaultdict(set), defaultdict(set)
        def node(id_, kind, label, **kwargs):
            nodes[id_] = {'id': id_, 'kind': kind, 'label': label, **kwargs}
        for r in relations:
            sid, bid = r['series_id'], r['book_id']
            if sid not in self.registry:
                continue
            author_id = r.get('author_id')
            node(sid, 'series', self.registry[sid]['title'], confirmed_group=sid in self.confirmed)
            node('book:' + bid, 'book', r.get('book_title') or books_by_id.get(bid, {}).get('official_book_title', bid), source_url=r.get('book_source_url'))
            candidate_by_book[bid].add(sid)
            if author_id:
                node('author:' + author_id, 'author', r.get('author') or author_id)
                candidate_by_author[author_id].add(sid)
                edges.append({'source': 'author:' + author_id, 'target': 'book:' + bid, 'relation': '官方书目作者',
                              'level': '官方书目', 'source_url': r.get('book_source_url'), 'source_sha256': r.get('book_source_sha256')})
            direct = [e for e in evidence_by_series[sid] if e['book_id'] == bid]
            if direct:
                for e in direct:
                    edges.append({'source': 'book:' + bid, 'target': sid, 'relation': e['relation_direction'],
                                  'level': e['evidence_level'], 'scope': e['scope'], 'evidence_id': e['evidence_id'],
                                  'excerpt': e['claim_excerpt'], 'source_url': e['source_url'], 'source_sha256': e['source_sha256'], 'limit': e['limit']})
                    if e['evidence_level'].startswith('A_') or '实地采访' in e['evidence_level']:
                        strong_by_book[bid].add(sid)
                        if author_id:
                            strong_by_author[author_id].add(sid)
            else:
                edges.append({'source': 'book:' + bid, 'target': sid, 'relation': '第三方候选关联', 'level': '候选，未确认改编',
                              'source_urls': r.get('third_party_source_urls', []), 'excerpt': None})
            for brand in sorted(self.brands_by_series[sid]):
                brand_id = 'brand:' + hashlib.sha256(brand.encode()).hexdigest()[:12]
                node(brand_id, 'brand', brand)
                edges.append({'source': brand_id, 'target': sid, 'relation': '榜单出品署名', 'level': '榜单署名，主体证据另列',
                              'source_url': next((x.get('source_url') or x.get('ranking_source_url') for x in self.brand_edges if x['series_id'] == sid and x['brand_name'] == brand), None)})
        # Deduplicate shared authors and brands while preserving distinct adaptation evidence records.
        unique_edges = {__import__('json').dumps(r, ensure_ascii=False, sort_keys=True): r for r in edges}
        edges = list(unique_edges.values())
        def rank_edges(mapping, kind, reliable):
            result = []
            for id_, series in mapping.items():
                if len(series) > 1:
                    nid = 'book:' + id_ if kind == 'book' else 'author:' + id_
                    result.append({'id': id_, 'label': nodes.get(nid, {}).get('label', id_), 'series_count': len(series),
                                   'series_ids': sorted(series), 'evidence_status': '有官方/媒体证据' if reliable else '候选线索'})
            return sorted(result, key=lambda r: (-r['series_count'], r['id']))
        data = {'confirmed_series_distribution': distribution, 'pending_units_distribution': dict(pending), 'statuses': statuses,
                'candidate_books': len(books), 'candidate_authors': len({r['official_author_id'] for r in books if r['official_author_id']}),
                'candidate_book_series_edges': len(relations), 'evidence_records': len(evidence),
                'one_book_multiple_series_evidenced': rank_edges(strong_by_book, 'book', True),
                'one_author_multiple_series_evidenced': rank_edges(strong_by_author, 'author', True),
                'one_book_multiple_series_candidates': rank_edges(candidate_by_book, 'book', False),
                'one_author_multiple_series_candidates': rank_edges(candidate_by_author, 'author', False),
                'nodes': list(nodes.values()), 'edges': edges,
                'counts_scope': '书目、作者、网络含全部196个统计单元；主比例仅169个确认系列；每个节点标注确认状态。'}
        self.write('adaptations', '原著、作者与改编证据', data, chart='network',
                   method='按最强证据互斥分类，主创待核自述独立一类；所有具体关系保留证据。',
                   limits=['官方书页只确认书目，不能自动确认改编或授权。', '没有明确原创证据时，不以缺少原著线索判为原创。'])
        self.table('系列改编状态', statuses)
        self.table('改编证据分布', distribution)
        self.table('原著作者网络节点', nodes.values())
        self.table('原著作者网络边', edges)
        self.table('改编证据登记', [{k:v for k,v in r.items() if not k.endswith('_file')} for r in evidence])

    def aigc(self):
        rows = load(RESULTS / 'aigc_scores.json')
        meta = load(RESULTS / 'aigc_model.json')
        assert meta['input_sha256'] == sha256(RESULTS / 'representatives.json')
        texts = [r for r in rows if r['sample_kind'] == 'series_description']
        valid = [r for r in texts if r['score_ai'] is not None]
        refs = [r for r in rows if r['sample_kind'] == 'book_reference' and r['score_ai'] is not None]
        matches = []
        for row in valid:
            candidates = [r for r in refs if abs(r['token_count'] - row['token_count']) / row['token_count'] <= .20]
            if not candidates:
                matches.append({'series_id': row['sample_id'], 'reference_book_id': None, 'reason': '无token长度差≤20%的可用原著参照'})
                continue
            chosen = min(candidates, key=lambda r: (abs(r['token_count'] - row['token_count']), r['sample_id']))
            matches.append({'series_id': row['sample_id'], 'reference_book_id': chosen['sample_id'],
                            'series_tokens': row['token_count'], 'reference_tokens': chosen['token_count'],
                            'series_score': row['score_ai'], 'reference_score': chosen['score_ai'],
                            'score_difference': row['score_ai'] - chosen['score_ai']})
        matched = [r for r in matches if r['reference_book_id'] is not None]
        groups = []
        for label, subset in [('≤100 token', [r for r in valid if r['token_count'] <= 100]),
                               ('101—200 token', [r for r in valid if 100 < r['token_count'] <= 200]),
                               ('201—512 token', [r for r in valid if r['token_count'] > 200])]:
            groups.append({'kind': 'length', 'label': label, 'scores': quantiles([r['score_ai'] for r in subset]),
                           'model_ai_label_rate': ratio(sum(r['predicted_label'] == 'AI' for r in subset), len(subset))})
        for genre in sorted({r['genre_primary'] for r in self.coded}):
            subset = [r for r in valid if self.coding[r['series_id']]['genre_primary'] == genre]
            groups.append({'kind': 'genre', 'label': genre, 'scores': quantiles([r['score_ai'] for r in subset]),
                           'model_ai_label_rate': ratio(sum(r['predicted_label'] == 'AI' for r in subset), len(subset))})
        for label in sorted({r['ai_status'] for r in valid}):
            subset = [r for r in valid if r['ai_status'] == label]
            groups.append({'kind': 'ai_evidence', 'label': label, 'scores': quantiles([r['score_ai'] for r in subset]),
                           'model_ai_label_rate': ratio(sum(r['predicted_label'] == 'AI' for r in subset), len(subset))})
        for label in sorted({v['label'] for r in self.coded for v in r['reversal_type']}):
            subset = [r for r in valid if label in {v['label'] for v in self.coding[r['series_id']]['reversal_type']}]
            groups.append({'kind': 'reversal', 'label': label, 'scores': quantiles([r['score_ai'] for r in subset])})
        # Descriptive correlations only, no author ground truth exists.
        correlations = []
        phrases = load(self.output / 'data/phrases.json')['data']['description_phrases'][:20]
        for phrase in phrases:
            members = set(phrase['series_ids'])
            present = [r['score_ai'] for r in valid if r['series_id'] in members]
            absent = [r['score_ai'] for r in valid if r['series_id'] not in members]
            correlations.append({'phrase': phrase['phrase'], 'present': quantiles(present), 'absent': quantiles(absent)})
        counts, edges = np.histogram([r['score_ai'] for r in valid], bins=np.linspace(0, 1, 21))
        data = {'model': meta, 'total_series_texts': len(texts), 'valid_series_texts': len(valid),
                'excluded_series': [r for r in texts if r['score_ai'] is None],
                'score_quantiles': quantiles([r['score_ai'] for r in valid]),
                'official_demo_ai_label_rate': ratio(sum(r['predicted_label'] == 'AI' for r in valid), len(valid)),
                'histogram': [{'lower': round(float(edges[i]), 3), 'upper': round(float(edges[i + 1]), 3), 'count': int(n)} for i, n in enumerate(counts)],
                'rows': rows, 'groups': groups, 'phrase_associations': correlations,
                'length_matches': matches, 'matched_comparison': {
                    'matched_series': len(matched), 'unique_reference_books': len({r['reference_book_id'] for r in matched}),
                    'series_scores': quantiles([r['series_score'] for r in matched]),
                    'reference_scores_reuse_weighted': quantiles([r['reference_score'] for r in matched]),
                    'score_differences': quantiles([r['score_difference'] for r in matched]),
                    'method': '每条剧简介选token长度最近且相差≤20%的原著简介，允许复用；无匹配记缺失。',
                }}
        self.write('aigc', '中文短文本检测模型分数（探索性）', data, chart='histogram', unit='模型分数', status='仅供探索',
                   method='官方示例类别[人类,AI]，softmax第二类得分；分类遵循官方argmax，不是本研究自行定阈值。',
                   limits=['参照原著简介未确认写作者。', '无真实作者标签，不能估计AI创作真实比例、检测准确率或视频AI制作。',
                           '超过512 token的文本排除而不截断。', '长度匹配参照允许复用，不作为独立样本显著性检验。'])
        self.percentage('aigc.demo_label_rate', '被检测器分到AI标签的简介比例（探索性）', sum(r['predicted_label'] == 'AI' for r in valid), len(valid),
                        '不超过512 token的有效系列代表简介', '2.4', '官方示例argmax；不是AI创作真实占比', status='仅供探索')
        self.table('AIGC模型分数', rows)
        self.table('AIGC分组统计', groups)
        self.table('AIGC长度匹配参照', matches)
        self.table('AIGC词组关联', correlations)

    def robustness(self):
        subsets = {
            'aug_oct_fixed_representatives': {
                'ids': {r['series_id'] for r in self.rankings if r['month'] >= '2026-08'} & self.confirmed,
                'label': '8—10月出现的确认系列，保持全期固定代表材料',
                'limit': '只改变入榜系列集合，不重新选择历史材料，不解释为素材自身随时间变化。'},
            'direct_ai_representative': {
                'ids': {r['series_id'] for r in self.reps if r['ai_direct_work_evidence']},
                'label': '至少一项所选代表作品有直接AI制作证据的系列',
                'limit': '每个模态还需其所选代表作品本身具有直接证据；不外推至同系列其他季。'},
        }
        output = []
        for name, spec in subsets.items():
            selected_rankings = [r for r in self.rankings if (r['month'] >= '2026-08' if name == 'aug_oct_fixed_representatives' else r['series_id'] in spec['ids'])]
            item = {'id': name, 'label': spec['label'], 'limits': spec['limit'], 'series_count': len(spec['ids']),
                    'story': self.story_summary(spec['ids']), 'similarity': {},
                    'ranking_rows': len(selected_rankings), 'work_candidates': len({r['work_id'] for r in selected_rankings}),
                    'pending_units': len({r['series_id'] for r in selected_rankings if r['series_id'] not in self.confirmed})}
            brand_series = defaultdict(set)
            for sid in spec['ids']:
                for brand in self.brands_by_series[sid]:
                    brand_series[brand].add(sid)
            brand_order = sorted(brand_series, key=lambda b: (-len(brand_series[b]), b))
            item['producer_concentration'] = [{'top_k': k, 'brands': brand_order[:k],
                **ratio(len({sid for b in brand_order[:k] for sid in brand_series[b]}), len(spec['ids']))} for k in [1,5,10]]
            for modality, value in self.similarities.items():
                allowed = {r['series_id'] for r in value['rows'] if r['series_id'] in spec['ids'] and
                           (name != 'direct_ai_representative' or r['ai_direct_work_evidence'])}
                pairs = [p for p in value['pairs'] if p['series_a'] in allowed and p['series_b'] in allowed]
                item['similarity'][modality] = {'valid_representative_series': len(allowed), 'thresholds': [self.sim_summary(pairs, allowed, t) for t in THRESHOLDS]}
            if name == 'direct_ai_representative':
                description_allowed = {r['series_id'] for r in self.reps if r['modality'] == 'description' and r['ai_direct_work_evidence']}
                item['story'] = self.story_summary(description_allowed)
                item['story_sample_definition'] = '仅简介代表作品本身有直接AI制作证据'
            output.append(item)
        self.write('robustness', '原方案月份范围及直接AI证据子样本', output, chart='table',
                   limits=['直接AI证据子样本很小；无可比配对时比例为null而不是0。',
                           '27个待核单元不混入跨系列相似度敏感性实验，仅在基础与续作统计单列。'])

    def findings(self):
        metrics = {r['id']: r for r in self.metrics}
        def percent(id_):
            value = metrics[id_]['value']
            return f'{value:.2f}%' if value is not None else '无法计算'
        cards = []
        def card(id_, section, title, text, files, limits):
            cards.append({'id': id_, 'section': section, 'title': title, 'text': text, 'data_files': files,
                          'status': '可展示', 'limits': limits})
        card('sample', '开场', '榜位数量与系列数量各有不同含义',
             '7—10月红果月榜共有400条上榜记录，对应368部分季作品候选；169个有平台系列号的系列之外，另有27个待核单元。',
             ['data/sample.json'], ['平台系列归组不等于独立故事，作品身份仍有待核状态。'])
        c = metrics['cover.series_rate.0.85']
        loose = metrics['cover.series_rate.0.80']
        card('cover', '2.1', '封面比例必须说明模型和判定标准',
             f'排除同系列续季后，在{c["denominator"]}个代表系列中，DINOv2余弦相似度≥0.85的封面候选涉及{c["numerator"]}个系列，占{percent(c["id"])}；改用0.80标准时涉及{loose["numerator"]}个系列，占{percent(loose["id"])}。',
             ['data/similarity_cover.json'], ['这是本研究模型阈值结果，不能据此称封面客观相似比例为零。'])
        for mode, label, section in [('title','剧名','2.2'), ('description','简介','2.3')]:
            m = metrics[mode+'.series_rate.0.85']
            card(mode, section, f'跨系列{label}高相似候选比例',
                 f'在{m["denominator"]}个代表系列中，至少与另一个系列的{label}达到BGE-M3余弦相似度0.85的有{m["numerator"]}个，占{percent(m["id"])}。',
                 [f'data/similarity_{mode}.json'], ['同系列续季和重复上榜已去重；高相似不代表同一正片故事。'])
        m = metrics['story.top3_union']
        story = load(self.output/'data/story.json')['data']
        card('reversal', '2.3', '常见翻盘表述的并集覆盖',
             f'在{m["denominator"]}个简介中识别到明确翻盘词项的系列中，{m["numerator"]}个涉及全期最常见的三类表述（'+
             '、'.join(story['top3_reversals'])+f'），并集覆盖率为{percent(m["id"])}。',
             ['data/story.json','data/codebook.json'], ['自动词项编码，未知不进入此分母；不是人工确认的完整剧情。'])
        monthly = load(self.output/'data/sequels.json')['data']['monthly']
        card('sequel', '3.1', '确认同系列续作占据额外榜位',
             '7—10月每月100个榜位中，按确认系列合并后分别减少'+ '、'.join(str(r['confirmed_extra_slots']) for r in monthly)+
             '个榜位，对应'+ '、'.join(f'{r["confirmed_extra_slots_rate"]["percent"]:.0f}%' for r in monthly)+'。',
             ['data/sequels.json'], ['只计确认系列每月k−1，待核关系不推断重复。'])
        m = metrics['producers.top5']
        card('producer', '3.2', '头部出品署名覆盖的系列',
             f'按覆盖确认系列数排序，前5家署名品牌合计覆盖{m["numerator"]}/{m["denominator"]}个系列，占{percent(m["id"])}；联合署名按系列并集去重。',
             ['data/producers.json'], ['品牌署名不等于公司主体；分母含署名未知系列。'])
        adap = load(self.output/'data/adaptations.json')['data']
        counts = {r['label']:r['count'] for r in adap['confirmed_series_distribution']}
        card('adaptation', '3.3', '书目线索与改编证据分开看',
             f'169个确认系列中，{counts["具体作品有直接改编声明"]}个有具体作品改编声明，{counts["系列有官方或媒体改编证据"]}个有系列级官方或媒体证据，{counts["仅主创自述，身份或别名待核"]}个仅有待核主创自述；另有候选线索和未知状态。',
             ['data/adaptations.json'], ['上述证据不能外推全部季或授权情况；没有原著线索不等于原创。'])
        self.write('findings', '可引用的正文数据卡', cards, chart='cards', unit='',
                   method='从同包指标和统计表确定性填入文字；引用时保留对应限制和分母。')
        self.table('正文数据卡', cards)

    def delivery(self):
        for metric in self.metrics:
            if not metric['sources']:
                metric['sources'] = ['data/' + ('similarity_' + metric['id'].split('.')[0] if metric['id'].split('.')[0] in self.similarities else
                                   'sequels' if metric['id'].startswith('sequels.') else 'story' if metric['id'].startswith('story.') else
                                   'producers' if metric['id'].startswith('producers.') else 'adaptations' if metric['id'].startswith('adaptation.') else
                                   'aigc' if metric['id'].startswith('aigc.') else 'sample') + '.json']
        save(self.output / 'data/metrics.json', self.metrics)
        self.table('全部网页指标', self.metrics)
        self.table('数据文件目录', self.files)
        sources = []
        for r in self.reps:
            sources.append({k: r.get(k) for k in ['series_id','modality','ranking_id','work_id','material_id','source_url','source_sha256','source_kind','cover_captured_at','identity_status']})
        self.write('sources', '代表材料来源', sources, chart='table', unit='')
        excluded = load(RESULTS / 'exclusions.json')
        self.write('exclusions', '样本排除与身份疑点', {'material_exclusions': excluded, 'pair_exclusions': load(RESULTS / 'excluded_pairs.json')}, chart='table', unit='')
        manifest = {'title': '红果新闻网页 Part 1—3 成品数据', 'schema_version': '1.0.0',
                    'scope': '2026年7—10月红果月榜400条记录', 'thresholds': THRESHOLDS, 'main_threshold': .85,
                    'files': self.files, 'metrics_file': 'data/metrics.json', 'series_file': 'data/series.json',
                    'metrics_count': len(self.metrics), 'warnings': WARNINGS,
                    'input_fingerprints': load(RESULTS / 'input_fingerprints.json'),
                    'method_changes': ['简介采用词项与原文证据的确定性规则编码，非人工或生成式语义标注；词典完整交付。',
                                       'AIGC使用原方案仓库官方提供的中文v3短文本模型；argmax分类口径留存。']}
        save(self.output / 'data/manifest.json', manifest)
        self.write_docs(manifest)
        self.write_preview()
        print('Exported', len(self.metrics), 'metrics,', len(self.files), 'datasets to', self.output, flush=True)

    def write_docs(self, manifest):
        text = '''# 红果新闻网页 Part 1—3 数据使用说明

本包是图表数据与素材交付，不是完整新闻网站。打开 `preview/index.html` 可离线查看数据验收预览；前端正式接入读取 `data/manifest.json`、各章节JSON和 `data/series.json`。

## 使用入口

- `data/metrics.json`：每个指标已有稳定ID、数值、单位、分子、分母、方法、来源、限制和状态。
- `data/similarity_cover.json`、`similarity_title.json`、`similarity_description.json`：主阈值0.85及0.80/0.90敏感性、Top 3、分布和案例。
- `data/story.json`：题材、五组结构标签、全期Top 3翻盘表述并集、模板、月度变化；`phrases.json`补充命名方式与词组。
- `data/sequels.json`、`producers.json`、`adaptations.json`：续作占榜、出品署名、改编证据和网络。
- `data/aigc.json`：探索性文本模型结果，不是AI创作真实比例。
- `data/robustness.json`：8—10月系列集合与直接AI证据代表作品子样本。
- `tables/`：UTF-8 BOM CSV，含全部允许跨系列配对、编码证据、指标和网络明细。
- `assets/covers/`：所选代表封面的本地缩略图，JSON中的资源路径相对交付包根目录。

## 相似比例怎么读

主指标为“至少与另一独立平台系列达到余弦相似度0.85的系列数 ÷ 有可比对象的有效系列数”。另有配对比例，两者不能互换。所有配对都是无序配对，没有A—B/B—A重复。0.80、0.85、0.90是本研究预先固定的操作阈值，不是通用的人类相似判断标准；分数不能跨模型解释。零命中是有效结果，不降低阈值来制造结论。

同系列不同季、同作品跨月、未解决系列关联均不作为跨系列主配对。精确同图指RGB像素和尺寸哈希相同；标题精确同名按季号规范后的文字比较，身份疑点配对在排除表单列。跨模态“系列交集”可能各自命中不同邻居；`same_pairs`才是同一对系列同时命中。

## 样本与版本

全集400条记录、368部分季作品候选；169个有平台系列号的系列、27个待核单元。系列号证明平台归组，不等于独立故事，也不保证历史榜单身份。代表材料按合格材料中的最好榜次、最早月份、稳定作品ID选择。封面与简介为采集时版本。月度题材比例使用固定代表简介，只反映当月入榜系列的构成。

全榜包含3D漫和AI仿真人剧，不全是已证实AI制作。`ai_status_counts`保留证据分层；`robustness.json`中各模态仅让代表作品本身有直接AI证据的样本参加严格子分析，不能外推其他季。

## 简介自动编码

采用固定词典的确定性规则，编码主类题材、身份、起因、转机、翻盘方式和设定。非未知标签提供原文及字符偏移；不从剧名补剧情。词典见`data/codebook.json`。30条试运行检查格式、字面证据和重复运行一致性，不是人工语义准确率。

规则可能遗漏隐含情节、无法确定主次或将配角表述识别为某种结构。因此输出代表“简介明确词项涉及的结构”，不能称为已人工证实的故事分类；未知保留。翻盘方式为多标签，比例可超过100%；Top 3并集按系列去重。结构组合重复不是正片相同。

## 出品与改编

品牌署名与企业主体分开。联合署名全计各方，头部覆盖率按系列并集；同家/异家比较控制题材与内容形态，仅单一署名系列进入两主组，联合或跨季署名变化单列。比较为描述性，不做因果结论。

改编主分类按最强证据互斥；主创身份待核自述独立一类。官方书目不自动证明改编；未知不等于原创。网络和书目含196个统计单元，主比例只用169个确认系列，节点标明待核状态。

## AIGC检测

使用官方中文v3-short模型，固定模型commit，官方示例类别顺序为[人类,AI]；保存softmax第二类得分、原始logits及argmax标签。超过512 token的文本不截断，主分析排除。没有已核实真实作者标签，不能给出检测准确率或AI真实占比。

原著简介只是来源明确的参照，不代表人写。长度按token匹配，差≤20%，允许复用，结果明确列出重复参照数；不作独立样本显著性检验。

## 空值和状态

`null`表示缺失、无法计算或不适用；数值0表示有效零。`percent`为0—100；相似度为余弦分数。`可展示`表示数据完整可用于相应措辞，非身份和模型判断全部确认；`仅供探索`不得包装为事实认定；`数据不足`不可补0。具体限制与来源必须随图保留。

## 受众与治理

受众数值保留约数、预计下界、未来预测等属性，口径不同，不连成实际观看人数增长折线。治理节选对照本地原文逐字核验；样本早于治理，不用于判断治理效果，也不表示样本作品违规。

## 复现

代码位于原项目`analysis/`。先执行`prepare.py`、`story_rules.py`，下载固定模型，再分别执行`infer_models.py cover/text/aigc`，最后执行`export_news.py`和`validate_delivery.py`。表格导出可使用应用自带Python；模型推理使用具备torch/transformers的独立运行环境。模型权重与向量只保存在分析缓存和results，不混入本交付包。
'''
        (self.output / '数据使用说明.md').write_text(text, encoding='utf-8')

    def write_preview(self):
        data = {p.stem: load(p) for p in sorted((self.output / 'data').glob('*.json'))}
        preview = self.output / 'preview'
        preview.mkdir(exist_ok=True)
        (preview / 'data.js').write_text('window.NEWS_DATA = ' + __import__('json').dumps(data, ensure_ascii=False, allow_nan=False) + ';\n', encoding='utf-8')
        import shutil
        for name in ['index.html', 'app.js', 'style.css']:
            shutil.copy2(ROOT / 'preview_template' / name, preview / name)

    def run(self):
        self.scope_stats()
        self.context()
        self.sequels()
        self.stories()
        for modality in ['cover', 'title', 'description']:
            self.similarity(modality)
        self.intersections()
        self.producers()
        self.adaptations()
        self.aigc()
        self.robustness()
        self.findings()
        self.delivery()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    Exporter(args.source, args.output).run()
