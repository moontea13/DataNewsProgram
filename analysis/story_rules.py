"""Conservative deterministic coding v1: every non-unknown label has a literal span.

This is rule-based automatic extraction, not a human annotation or an LLM accuracy claim.
"""
import re
from collections import Counter
from common import RESULTS, load, save

VERSION = 'redfruit-evidence-rules-1.1'
GENRES = {
    '玄幻仙侠': r'修仙|修真|修炼|修为|灵根|灵气|仙界|仙门|仙尊|仙帝|妖魔|妖兽|渡劫|宗门|长生|玄幻|神通|灵石|飞升|炼丹|雷劫|大乘|散仙|天骄|天剑|虚丹|秘境|半魔|灵兽|御兽|神兽|魔神|魔族|妖祖|九尾狐|妖气|养尸|六界|天道|魔性|圣魔|妖界',
    '末世生存': r'末世|末日|丧尸|天灾|求生|全球.{0,4}灾|极寒|灾变',
    '悬疑灵异': r'悬疑|凶案|破案|侦探|推理|诡异|阴阳|厉鬼|鬼怪|风水|守棺|道士|阴间|灵异|巫蛊|邪祟|灭门案',
    '历史军事': r'大唐|大宋|南宋|北宋|大明|明朝|唐朝|清朝|民国|抗战|军阀|督军|历史|战场|大秦|秦朝|三国|李世民|朱元璋|入宋|现代武器|匈奴|秦法|将领|边军|边关|朝堂|皇权|军营',
    '古代宫廷': r'古代|王朝|王爷|王妃|皇帝|皇后|宫斗|后宫|太子|嫡女|庶女|侯府|丞相|将军|暴君|公主|摄政王|王府|世子|京城|皇商|锦衣卫|科举|县试|府试|大奉|宫廷',
    '家庭婚恋': r'婚姻|结婚|离婚|闪婚|联姻|契约婚姻|丈夫|妻子|夫人|婆婆|婆媳|未婚夫|未婚妻|萌宝|甜宠|恋爱|霸总|总裁|爱情|千金|豪门|重男轻女|母女|父女|亲情|家族|家庭|母亲|父亲|兄长|女友|男友|初恋|相守|求娶|成亲|大婚|婚书|重逢|相恋',
    '职场商战': r'职场|商战|创业|公司|董事长|商业帝国|商界|集团|商业|职员|打工|总经理',
    '都市生活': r'都市|现代|城市|中年|农村|乡村|种田|高考|大学|校园|学生|神医|保安|外卖|赘婿|渔民|渔王|娱乐圈|演员|明星|影帝|顶流|医生|医院|医疗|病例|同学|聚会|大一|租客|房东|歌手|乐坛|选秀|家装|拆迁|猎户|全村|林区|七零|八零|年代',
    '科幻冒险': r'星际|银河系|外星|科技残骸|文明覆灭|机械文明|宇宙|太空|星舰',
}
LABELS = {
    'protagonist_identity': {
        '重生者': r'重生|重活一世|再活一世|回到.{0,6}(?:年前|前夕|过去)',
        '穿越者': r'穿越|穿到|魂穿|穿成|穿入|一朝醒来.{0,14}(?:大唐|古代|异界)',
        '穿书者': r'穿书|穿进.{0,8}(?:小说|书)|穿成.{0,8}(?:炮灰|反派)',
        '系统持有者': r'系统|金手指',
        '修行者': r'修仙|修士|修真|修为|灵根|修炼|宗门弟子',
        '医者': r'神医|医术|医生|医圣|医仙|中医',
        '军人战神': r'战神|兵王|军人|特种兵|退伍|将军|统帅',
        '赘婿': r'赘婿|上门女婿',
        '豪门或权贵': r'总裁|豪门|千金|首富|皇子|太子|王爷|公主|贵族|世子',
        '普通劳动者': r'打工|外卖|保安|农民|渔民|穷小子|普通人|平凡|小人物|社畜',
        '艺人': r'演员|明星|影帝|顶流|娱乐圈|歌手',
    },
    'inciting_event': {
        '背叛与伤害': r'背叛|陷害|被害|惨死|虐待|欺辱|羞辱|冤枉|被杀|灭门',
        '身份或世界变化': r'重生|穿越|穿书|穿成|魂穿|醒来|身份互换|抱错',
        '困境与危机': r'破产|家破人亡|落榜|失业|绝境|危机|濒死|身患|负债|家徒四壁',
        '婚恋或家庭变故': r'退婚|离婚|闪婚|联姻|替嫁|逼婚|家族|亲生父母|真假千金',
        '偶遇或意外': r'意外|偶然|偶遇|机缘|偶得',
    },
    'turning_point': {
        '系统或异能出现': r'觉醒.{0,10}(?:系统|异能|能力)|绑定.{0,8}系统|获得.{0,8}(?:系统|异能)|系统觉醒|金手指|开启.{0,8}系统',
        '获得机缘或传承': r'获得.{0,10}(?:传承|机缘|神器|神通)|得到.{0,8}(?:传承|神器)|奇遇|机缘|拜师|传承',
        '重生穿越': r'重生|穿越|穿书|魂穿|重活一世',
        '身份揭晓': r'身份.{0,6}(?:曝光|揭晓|揭露)|真实身份|身世.{0,6}(?:揭开|揭晓)|认亲|真千金',
        '能力突破': r'突破|修为.{0,6}(?:暴涨|大增)|实力.{0,6}(?:暴涨|大增)|医术',
        '关键人物帮助': r'贵人|得到.{0,6}帮助|遇到.{0,6}(?:总裁|师父|师傅)|被.{0,6}收养',
    },
    'reversal_type': {
        '系统金手指': r'系统|金手指|异能|透视|读心|签到|空间异能',
        '重生先知': r'重生|重活一世|再活一世|前世记忆|预知未来|先知',
        '穿越穿书优势': r'穿越|穿书|魂穿|穿成|现代知识|现代科技|现代武器',
        '修炼或传承变强': r'修炼|修仙|修为|神通|传承|修真|灵根|吞噬|功法',
        '身份揭露': r'身份.{0,8}(?:曝光|揭晓|揭露)|真实身份|身世.{0,8}(?:揭开|揭晓)|真千金|首富.{0,5}(?:儿子|女儿)|隐藏身份',
        '医术或专业技能': r'医术|神医|医圣|救治|治病|妙手|厨艺|鉴宝|技术|才华|学霸|科举',
        '财富权力跃迁': r'首富|商业帝国|财富|暴富|致富|商业版图|登基|称帝|权倾|掌权',
        '婚恋关系助力': r'契约婚姻|闪婚|联姻|嫁给|娶了|总裁.{0,6}(?:宠|爱)|王爷.{0,6}(?:宠|爱)',
        '复仇清算': r'复仇|报仇|雪恨|血债|清算|报复|讨回公道',
        '打脸反击': r'打脸|反击|逆袭|扮猪吃虎|碾压|扬眉吐气',
    },
    'setting': {
        '古代历史': r'古代|大唐|唐朝|大宋|北宋|南宋|大明|明朝|大秦|秦朝|王朝|皇帝|王爷|侯府|丞相|太子|民国',
        '现代都市': r'现代|都市|城市|公司|集团|总裁|大学|高考|娱乐圈|校园|外卖',
        '修仙异界': r'仙界|修仙|异界|修真界|宗门|妖魔|灵气|仙门|玄幻',
        '末世灾难': r'末世|末日|丧尸|天灾|灾变|极寒',
        '乡村年代': r'乡村|农村|村庄|年代|知青|七零|八零|六零|种田',
    },
}

def hits(text, labels):
    result = []
    for label, expression in labels.items():
        for match in re.finditer(expression, text):
            # Avoid counting explicit negation of the lexical cue as positive evidence.
            prefix = text[max(0, match.start() - 4):match.start()]
            if re.search(r'(?:没有|并无|无|未曾|不是|不靠)$', prefix):
                continue
            # Recognized synopsis disclosures are not plot events.
            sentence_start = max(text.rfind('。', 0, match.start()), text.rfind('\n', 0, match.start())) + 1
            if re.match(r'\s*(?:本剧|该剧)?(?:改编自|根据)', text[sentence_start:]):
                continue
            result.append({'label': label, 'evidence': match.group(), 'start': match.start(), 'end': match.end()})
            break
    return result

def code(record):
    text = record['description']
    genre_matches = {label: hits(text, {label: expression}) for label, expression in GENRES.items()}
    # More distinct literal cues win. Dictionary order resolves a tie reproducibly.
    scored = [(len(set(re.findall(expression, text))), -i, label) for i, (label, expression) in enumerate(GENRES.items()) if genre_matches[label]]
    genre = max(scored)[2] if scored else '未知'
    fields = {name: hits(text, labels) for name, labels in LABELS.items()}
    unknown = [name for name, values in fields.items() if not values]
    return {'series_id': record['series_id'], 'work_id': record['work_id'], 'material_id': record['material_id'],
            'title': record['series_title'], 'description': text, 'genre_primary': genre,
            'genre_evidence': genre_matches.get(genre, []), **fields,
            'unknown_fields': {field: '规则未找到明确正向表述；不等于剧情不存在' for field in unknown},
            'status': '可用规则编码' if genre != '未知' else '题材信息不足或规则未覆盖',
            'method': VERSION, 'limits': '词项规则识别的是简介中的表述，不保证为主角行为或真实因果，未作人工语义准确性核验。'}

def validate(row):
    errors = []
    for name in list(LABELS) + ['genre_evidence']:
        for value in row[name]:
            if row['description'][value['start']:value['end']] != value['evidence']:
                errors.append(name + ': evidence offset mismatch')
            if name in LABELS and value['label'] not in LABELS[name]:
                errors.append(name + ': invalid label')
    return errors

def run():
    rows = [r for r in load(RESULTS / 'representatives.json') if r['modality'] == 'description']
    pilot = rows[:30]
    first, second = [code(r) for r in pilot], [code(r) for r in pilot]
    check = {'method': VERSION, 'pilot_size': len(pilot), 'evidence_errors': sum(len(validate(r)) for r in first),
             'repeat_exact_matches': sum(a == b for a, b in zip(first, second)),
             'interpretation': '固定规则的运行一致性和证据定位检查，不是人工标注准确率。'}
    coded = [code(r) for r in rows]
    assert all(not validate(r) for r in coded)
    save(RESULTS / 'story_coding.json', coded)
    save(RESULTS / 'story_pilot.json', check)
    save(RESULTS / 'codebook.json', {'version': VERSION, 'genres': GENRES, 'fields': LABELS,
         'genre_selection': '简介内正向词项匹配最多的主类，平局按字典顺序；无命中为未知',
         'unknown_policy': '不根据剧名或平台标签推断；不命中为未知；保留原文字符偏移'})
    print('story coding', len(coded), Counter(r['genre_primary'] for r in coded), check, flush=True)

if __name__ == '__main__':
    run()
