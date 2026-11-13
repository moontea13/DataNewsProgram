"""复现试标抽取，核对冻结的编号清单。"""
import random
from pipeline import ANN, SEED, read_json, lines


data=read_json(ANN/'input_index.json')
first={s:min(r['month'] for r in data['rankings'] if r['series_id']==s) for s in {w['series_id'] for w in data['works']}}
rng=random.Random(SEED)
series_ids=[s for m in sorted(set(first.values())) for s in rng.sample(sorted(s for s in first if first[s]==m),6)]
assert series_ids==read_json(ANN/'trial_series_ids.json')

# 这9条是在首次试标包全文阅读后补标的记录。抽样复现使用补标前的候选框。
trial_additions={'R0245','R0291','R0751','R1494','R1643','R1941','R2412','R2691','R2896'}
rows=[r for r in lines(ANN/'comment_opinions.tsv') if r[0] not in trial_additions]
ids={r[0] for r in rows}
rng=random.Random(SEED)
chosen=[]
for scope,relation in [('x','S'),('x','D'),('s','S'),('i','S'),('u','S'),('?','S')]:
    pool=sorted({r[0] for r in rows if r[1:3]==[scope,relation]}-set(chosen))
    chosen+=rng.sample(pool,min(10,len(pool)))
promo=sorted({c['local_id'] for c in data['comments'] if c['possible_creator_or_promo']=='True'}-set(chosen))
chosen+=rng.sample(promo,10)
normal={c['local_id'] for c in data['comments'] if c['local_id'] not in ids and c['possible_creator_or_promo']=='False'}
chosen+=rng.sample(sorted(normal-set(chosen)),120-len(chosen))
assert chosen==read_json(ANN/'trial_comment_ids.json')
print('试标24系列及120评论编号复现通过，种子为',SEED)
