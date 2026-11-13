"""复现语义初标前的检索队列。命中不等于相似，未命中不等于已审核。"""
import re
from pipeline import ANN,read_json,write_json


data=read_json(ANN/'input_index.json')
pattern=r'像|似|同质|雷同|套路|重复|一样|相同|不同|区别|差异|新颖|新意|撞|一模|换皮|既视感|即视感|其他|其它|别的|别部|别剧|抄|缝合|借鉴|翻版|模仿|复刻|套皮|套壳|脸盲|分不清|认不[出清]|千篇一律|千人一面'
queue=[]
for c in data['comments']:
    if c['possible_creator_or_promo']=='True':
        continue
    hits=[s for s in re.split(r'[。！!？?\n]',c['text']) if re.search(pattern,s)]
    if hits:
        queue.append(dict(id=c['local_id'],title=c['work_title_as_captured'],snippets='。'.join(hits)))
assert queue==read_json(ANN/'semantic_candidates.json')
print('比较候选语句检索复现通过：',len(queue),'条。语义观点另存，不由检索规则生成。')
