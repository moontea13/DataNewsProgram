"""复用已验证评论解析器，输出本轮按名次分层样本。"""
import csv
import json
import sys
from pathlib import Path
import 批量采集红果评论 as parser
from 持续补采 import OUT,records,save

parser.OUT=OUT/'评论分层'
parser.extract()
sample={r['platform_work_id']:r for r in map(json.loads,(parser.OUT/'红果评论抽样清单.jsonl').read_text().splitlines())}
rows=[json.loads(l) for l in (parser.OUT/'红果公开热评.jsonl').read_text().splitlines()]
for r in rows:r['rank_stratum']=sample[r['platform_work_id']]['rank_stratum']
records('红果名次分层评论',rows)
old=[json.loads(l) for l in (parser.ROOT/'data/公开评论/红果公开热评.jsonl').read_text().splitlines()]
union={r['comment_key']:{**r,'sampling_batches':['原按名次优先样本']} for r in old}
for r in rows:
    if r['comment_key'] in union:union[r['comment_key']]['sampling_batches'].append('本轮五名次层样本')
    else:union[r['comment_key']]={**r,'sampling_batches':['本轮五名次层样本']}
records('红果评论合并索引_分析须按抽样批次筛选',list(union.values()))
save('红果评论增量统计.json',{'new_stratified_sample_works':len(sample),'new_stratified_comments':len(rows),'union_comments_deduplicated':len(union),'union_works':len({r['platform_work_id'] for r in union.values()}),'new_comments_beyond_old_sample':sum(r['comment_key'] not in {x['comment_key'] for x in old} for r in rows),'limits':'正式分层比较使用本轮样本；合并索引仅作资料库，不能把不同抽样规则直接混算。身份仍须核实。'})
