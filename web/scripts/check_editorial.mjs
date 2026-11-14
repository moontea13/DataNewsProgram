import assert from 'node:assert/strict';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { coverBoardsHTML } from '../src/cover-boards.js';
import { governanceHTML, coverOverviewHTML, storyEvidenceHTML, storyFindingsHTML, originOverviewHTML, producerOverviewHTML, adaptationHTML, adaptationRelations } from '../src/editorial.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const D={};
for(const name of ['gallery','editorial','cover_layout','cover_models','cover_groups','adaptations','producers','sequels','governance'])D[name]=JSON.parse(await readFile(path.join(root,'public/data',name+'.json'),'utf8'));
const s=D.editorial.structure;
const ids=D.editorial.clusters.flatMap(c=>c.members);
assert.equal(ids.length,s.valid_series);
assert.equal(new Set(ids).size,ids.length,'每个系列只能归属一个共同核心');
assert.equal(D.editorial.clusters.length,s.cluster_count);
assert.equal(D.editorial.semantic.length,s.valid_series);
assert(D.editorial.semantic.every(r=>r.main_included&&!r.integration_exclusion),'排除单元不得返回主结构结果');
assert.equal(D.editorial.clusters.filter(c=>c.count>1).reduce((n,c)=>n+c.count,0),s.repeated_cluster_coverage.numerator);
assert.equal(s.top3_mechanisms.reduce((n,label)=>n+s.distributions.turning_mechanism.find(r=>r.label===label).numerator,0),s.top3_union.numerator);
const byId=new Map(D.gallery.map(r=>[r.series_id,r]));
for(const id of ids)assert(byId.has(id));
for(const row of D.sequels.monthly){
  assert.equal(row.confirmed_extra_slots+row.known_series+row.pending_ranking_rows,100);
  assert.equal(row.confirmed_extra_slots_rate.numerator,row.confirmed_extra_slots);
}
assert.equal(D.adaptations.confirmed_series_distribution.reduce((n,r)=>n+r.count,0),169);
for(const row of D.cover_groups.groups){assert.equal(new Set(row.members).size,row.members.length);for(const id of row.members)assert(byId.has(id));}
assert.equal(D.editorial.producer_concentration.find(r=>r.top_k===10).series_ids.length,37);
for(const row of D.gallery)await stat(path.join(root,'public',row.cover));
const evidence=storyEvidenceHTML(D);
assert.equal((evidence.match(/<mark /g)||[]).length,9,'每个案例的三个原文证据必须能精确定位');
for(const match of evidence.matchAll(/<article class="evidence-card">[\s\S]*?data-series="([^"]+)"/g))assert(ids.includes(match[1]));
const boards=coverBoardsHTML(D);
assert.equal((boards.match(/class="cover-board"/g)||[]).length,5);
assert.equal((boards.match(/id="annotation-toggle"/g)||[]).length,1);
const output=[boards,governanceHTML(D),coverOverviewHTML(D),evidence,storyFindingsHTML(D),originOverviewHTML(D),producerOverviewHTML(D),adaptationHTML(D),adaptationRelations(D)].join('');
assert(!output.includes('undefined'));
assert(coverOverviewHTML(D).includes('148 / 169'));
assert(coverOverviewHTML(D).includes('87.6'));
assert(coverOverviewHTML(D).includes('阈值0.50'));
assert(!boards.includes('<details'));
assert(!output.includes('169个代表剧名 · 具体句式统计'));
assert(!output.includes('D:\\'));
const waffleBlocks=[...originOverviewHTML(D).matchAll(/<div class="slot-grid"[\s\S]*?<\/div>/g)];
assert.equal(waffleBlocks.length,4);
assert(waffleBlocks.every(([html])=>(html.match(/<i class=/g)||[]).length===100));
console.log('通过：146个系列/74组、原文9处定位、4×100榜位、169封面资源、改编证据分类、5组案例和来源数据。');
