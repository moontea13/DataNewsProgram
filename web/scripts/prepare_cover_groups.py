"""中心裁剪特征的完整连接展示组；组内每一对均需达到固定阈值。"""
import csv
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / 'web'
THRESHOLD = .70
# 从确定性完整连接候选中，经逐图查看选出叙事清楚的展示组。
# 组名描述图片里可直接看到的外观，不冒充字体识别模型的分类结果。
SELECTIONS = [
    ('暗色双人像，白字落在下半幅', '贴近的人物关系、偏暗的紫粉背景，和下半幅的白色横排标题。', ['人物贴近', '下部白字', '暗紫与粉色'], '#ead4dc', ['HG_7670117824450284569', 'HG_7681905064142703640', 'HG_7687841226178972696']),
    ('暖金色调，居中的古装人物', '人物占据画面中央，背景偏金黄；书法标题沿画面的上下边缘铺开。', ['古装人物', '暖金色背景', '书法标题'], '#e9d7ad', ['HG_7644850685896313881', 'HG_7663096556081384472', 'HG_7664586541355781145']),
    ('西装男女，白色大标题', '现代装束的男女并置在画面前景，浅色标题压在人物衣服和画面下方。', ['西装与礼服', '男女并置', '白色标题'], '#d9dce1', ['HG_7662307235489385534', 'HG_7662667624169344024', 'HG_7667170646199110681']),
    ('多人仙侠，金色书法字', '几个人物围绕主角排开，金色书法标题与衣袍、光效一起构成仙侠视觉。', ['多人组合', '仙侠服饰', '金色文字'], '#dce2e8', ['HG_7660352389433543705', 'HG_7665691216951905305', 'HG_7686465915717700633', 'HG_7698946793580530750']),
    ('暗色仙侠，红金色标题', '深色底图上，单个男主位于视觉中心，红色或金色的书法标题形成强对比。', ['男主居中', '深色底图', '红金书法字'], '#ded4d2', ['HG_7670484913375693849', 'HG_7679383226309168190', 'HG_7688265718504098878', 'HG_7690426815780752408']),
]

def main():
    scores = {}
    with (ROOT / '临时/解包/style/tables/model_pairs.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            if row['model_variant'] == 'dinov2_center':
                scores[frozenset([row['series_a'], row['series_b']])] = float(row['score'])
    gallery = {row['series_id']: row for row in json.loads((WEB / 'public/data/gallery.json').read_text())}
    used = set()
    groups = []
    for index, (title, description, cues, color, members) in enumerate(SELECTIONS):
        assert not used.intersection(members), '展示组不重复占用系列'
        assert all(sid in gallery for sid in members)
        pairs = []
        for a, b in itertools.combinations(members, 2):
            score = scores[frozenset([a, b])]
            assert score >= THRESHOLD, (title, a, b, score)
            pairs.append({'a': a, 'b': b, 'score': score})
        used.update(members)
        groups.append({'id': f'G{index+1:02}', 'title': title, 'description': description, 'cues': cues, 'color': color, 'members': members, 'pair_scores': pairs, 'minimum_score': min(pair['score'] for pair in pairs)})
    data = {'model': 'dinov2_center', 'threshold': THRESHOLD, 'method': '中心裁剪DINOv2特征、固定阈值、完整连接；从候选中逐图核对并选择展示组。', 'scope': '169个固定代表系列', 'visual_cues_method': '编辑逐图查看封面；未使用字体家族识别模型。', 'groups': groups, 'displayed_series': len(used)}
    target = WEB / 'public/data/cover_groups.json'
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'封面看板：中心裁剪，阈值{THRESHOLD:.2f}，{len(groups)}组／{len(used)}个系列；全部组内配对已核对。')

if __name__ == '__main__':
    main()
