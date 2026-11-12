"""从保存的抖音公开检索索引提取明确带评论结构的文本；不冒充实时全量评论区。

python3 scripts/提取抖音公开索引评论.py
只接受包含目标完整规范剧名的抖音视频来源，每个检索目标最多9条。
"""
import hashlib
import json
import re
from collections import Counter

from 作品匹配 import ROOT, parse_title, normalize
from 采集红果简介封面 import save_json, save_records, now, location

OUT=ROOT/'data/公开评论'
HEADER=re.compile(r'(?m)^([^\n]+) \((https://www\.douyin\.com/video/(\d+))\)\s*$')
COMMENT=re.compile(r'(?m)^([^\n]{1,80})\n\n\.\.\.\n\n(.*?)\n\n((?:\d+(?:秒|分钟|小时|天|周|个月|月|年)前|今天|昨天|前天|\d{4}-\d{2}-\d{2}|\d{1,2}-\d{1,2})(?:·[^\n]+)?)\n\n([0-9]+(?:\.[0-9]+)?万?)',re.S)


def main():
    rows=[];coverage=[];sources=[];seen=set()
    for path in sorted((OUT/'抖音索引').glob('*.json')):
        payload=json.loads(path.read_text());target=payload['target'];text=payload['result']
        if not isinstance(text,str):continue
        headers=list(HEADER.finditer(text));count=0;relevant=0;found=0
        target_key=parse_title(target['title'])['base_key']
        for i,h in enumerate(headers):
            segment=text[h.end():headers[i+1].start() if i+1<len(headers) else len(text)]
            body=segment.split('\n# ',1)
            if len(body)<2:continue
            body=body[1].split('\n## ',1)[0]
            caption=body.split('\n',1)[0]
            if target_key not in normalize(caption):continue
            relevant+=1;url=h[2];video_id=h[3]
            parsed=list(COMMENT.finditer(body));found+=len(parsed)
            sources.append({'ranking_id':target['ranking_id'],'ranking_title':target['title'],
                            'video_id':video_id,'video_caption':caption,'source_url':url,
                            'comments_recognized':len(parsed),'source_file':location(path),
                            'identity_status':'视频与剧名文字相关；榜单版本/发布者角色待核实'})
            for position,m in enumerate(parsed,1):
                if count>=9:break
                author,content,relative,likes=m.groups()
                content=re.sub(r'\n\n(?:作者赞过|作者回复过)\s*$','',content).strip()
                if not content or len(content)>3000 or any(x in content for x in ['发布时间：','粉丝','## 猜你喜欢']):continue
                ah=hashlib.sha256(author.encode()).hexdigest()[:16]
                key=hashlib.sha256((video_id+'|'+ah+'|'+content).encode()).hexdigest()[:24]
                if key in seen:continue
                seen.add(key);count+=1
                rows.append({'platform':'抖音','comment_key':'DY_INDEX_'+key,'native_comment_id':'',
                             'ranking_id':target['ranking_id'],'sample_month':target['month'],'ranking_title':target['title'],
                             'video_id':video_id,'source_url':url,'video_caption':caption,
                             'source_position_in_index':position,'text':content,'author_hash':ah,
                             'author_role':'待核对；未默认普通观众','likes_display':likes,
                             'published_display':relative,'published_at':'',
                             'date_note':'索引快照中的相对日期，锚点未知；不按采集日期倒推',
                             'captured_at':payload['captured_at'],'source_file':location(path),
                             'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                             'entry_type':'搜索服务公开索引评论片段；非实时/全量/随机/按热度排序接口',
                             'identity_status':target['identity_status'],
                             'review_status':'需回看原视频评论，核对作者身份、版本、上下文和相对日期'})
        coverage.append({'ranking_id':target['ranking_id'],'title':target['title'],'month':target['month'],
                         'relevant_video_pages':relevant,'comments_in_index_recognized':found,'comments_saved':count,
                         'status':'已取得索引片段，待原页核对' if count else '未取得可确认评论；不能当作零评论'})
    save_records(OUT,'抖音公开索引评论_待核查',rows)
    save_records(OUT,'抖音评论覆盖情况',coverage)
    save_records(OUT,'抖音相关视频线索',sources)
    stats={'generated_at':now(),'query_targets':len(coverage),'targets_with_comment_fragments':sum(x['comments_saved']>0 for x in coverage),
           'comment_fragments':len(rows),'distinct_video_ids_with_comments':len({r['video_id'] for r in rows}),
           'limits':'搜索索引片段，不是实时完整评论区；视频不等于剧目；时间及版本未核实；不与红果原页热评直接合并计算比例'}
    save_json(OUT/'抖音评论统计.json',stats);print(json.dumps(stats,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
