import * as d3 from './vendor/d3.js';
import scrollama from './vendor/scrollama.js';
import { autoWindow } from './motion.js';
import { esc, month, source } from './components.js';

const sequences = {
  origins:{
    theme:'butter',title:'顺着一部剧，找到它的来处',
    steps:[
      ['一部剧，也可能是一个长系列。','同一系列的不同季，反复出现在榜单中。每张纸页是一部季作品，也是一份被续写的故事。','同系列各季'],
      ['再往外，看看谁还署了同一个名字。','系列保留在左边，右边展开与它共用出品署名的其他系列。同一个署名，还连接着其他题材与人物。','同出品署名'],
      ['原著这条线，走到了哪一步？','继续沿着同一部剧找书目与作者。一些作品能追溯到具体书目，一些仍只有改编线索。','原著与作者'],
    ],
  },
  timeline:{
    theme:'plain',title:'在同一条时间轴上，看三种换新',
    steps:[
      ['先把新作品连起来。','观察期内，每月新入榜的分季作品，从7月的100部，到10月的86部。','作品'],
      ['把续季合起来，再画一条。','绿色线按系列计数。同一系列的后续季仍是新作品，但不会再被记成一个新系列。','加入系列'],
      ['结构的变化，是第三条线。','红色线标记首次出现的全局结构簇。各月的作品数、系列数、结构种类，是不同层次的“新”。','加入结构簇'],
      ['在同一个月，看看三条线。','月份依次轮换。新作品、新系列、新结构的数字，沿着同一根标线展开。','月份流转'],
    ],
  },
};

export function exhibitHTML(id) {
  const config=sequences[id];
  return `<div class="exhibit exhibit-${config.theme}" id="exhibit-${id}" data-exhibit="${id}">
    <figure class="exhibit-visual"><div class="exhibit-frame" tabindex="0" role="group" aria-label="${config.title}，可用左右方向键切换"><div class="exhibit-top"><span class="exhibit-caption">${config.title}</span><span class="exhibit-page">01 / ${String(config.steps.length).padStart(2,'0')}</span></div><div class="exhibit-body" id="exhibit-body-${id}"></div><div class="exhibit-transport"><button data-exhibit-prev="${id}" aria-label="上一个视角">←</button><div class="exhibit-tabs" role="group" aria-label="切换观察维度">${config.steps.map((step,index)=>`<button data-exhibit-goto="${id}" data-position="${index}" class="${index===0?'active':''}" aria-pressed="${index===0}">${step[2]}</button>`).join('')}</div><button data-exhibit-next="${id}" aria-label="下一个视角">→</button></div><div class="exhibit-progress"><i></i></div></div><figcaption>${id==='recipe'?'简介结构 · 红果7—10月榜单系列':id==='origins'?'作品、出品署名与原著资料':'红果7—10月月榜 · 7月为观察期基线'}</figcaption></figure>
    <div class="exhibit-narrative">${config.steps.map((step,index)=>`<article class="exhibit-step ${index===0?'is-active':''}" data-exhibit-step="${index}"><span class="exhibit-step-no">${String(index+1).padStart(2,'0')}</span><h3>${step[0]}</h3><p>${step[1]}</p><span class="exhibit-read-cue" aria-hidden="true">↓</span></article>`).join('')}</div>
  </div>`;
}

function poster(row, extra='', label='') {
  return `<div class="shelf-item ${extra}"><button class="physical-cover" data-series="${row.series_id}" aria-label="查看${esc(row.title)}"><img src="./${row.cover}" alt="${esc(row.title)}的封面" loading="lazy"><span class="cover-spine" aria-hidden="true"></span><span class="ocr-shapes"></span></button><span class="shelf-item-title">${esc(row.title)}</span>${label?`<small class="shelf-item-label">${label}</small>`:''}</div>`;
}

export function initExhibits(D) {
  const gallery=new Map(D.gallery.map(row=>[row.series_id,row]));
  const sceneStates=new Map();
  let originId='HG_7624475539960499262';
  function drawOrigins(){
    const row=gallery.get(originId),nodeRows=D.part45.nodes.filter(n=>n.series_id===originId).sort((a,b)=>a.month.localeCompare(b.month)||a.rank-b.rank),works=[...new Map(nodeRows.map(n=>[n.work_id,n])).values()],brand=row.producer_brands[0];
    const peers=D.gallery.filter(r=>r.series_id!==originId&&r.producer_brands.includes(brand)).slice(0,3);
    const status=D.adaptations.statuses.find(r=>r.series_id===originId);
    const bookId=status?.book_ids?.[0],book=D.adaptations.nodes.find(r=>r.id===`book:${bookId}`),authorEdge=book&&D.adaptations.edges.find(r=>r.target===book.id&&r.source.startsWith('author:')),author=authorEdge&&D.adaptations.nodes.find(r=>r.id===authorEdge.source);
    const options=D.sequels.series_ranking.filter(r=>gallery.has(r.series_id)&&(r.series_id==='HG_7624475539960499262'||D.sequels.series_ranking.indexOf(r)<10));
    const confirmed=status&&['具体作品有直接改编声明','系列有官方或媒体改编证据'].includes(status.category);
    const evidence=D.editorial.adaptation_evidence.find(r=>r.series_id===originId);
    document.getElementById('exhibit-body-origins').innerHTML=`<div class="origin-selector"><label>沿着这个系列看<select id="origin-series">${options.map(r=>`<option value="${r.series_id}" ${r.series_id===originId?'selected':''}>${esc(r.title)}</option>`).join('')}</select></label></div><div class="origin-scene"><div class="origin-reference">${poster(row,'origin-book','系列代表封面')}</div><div class="origin-connector" aria-hidden="true"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><path d="M5 50 H40 Q50 50 50 35 V15 H95 M50 35 V80 Q50 90 60 90 H95"/></svg></div><div class="origin-slide-window"><div class="origin-slide-track"><div class="origin-slide"><div class="season-record-list">${nodeRows.map(work=>`<button data-node="${work.ranking_id}"><span>${month(work.month)}<strong>第${work.rank}名</strong></span><span>${esc(work.title)}</span></button>`).join('')}</div><p class="origin-slide-caption">${works.length}部分季作品 · ${nodeRows.length}条上榜记录，按月份排列</p></div><div class="origin-slide"><div class="publisher-name"><small>榜单出品署名</small><strong>${esc(brand||'署名缺失')}</strong></div><div class="publisher-shelf">${peers.length?peers.map(r=>poster(r,'publisher-book')).join(''):'<p class="shelf-empty">169个代表材料中，暂无其他同署名系列。</p>'}</div></div><div class="origin-slide"><div class="book-source ${confirmed?'confirmed':'candidate'}"><span class="source-book-spine" aria-hidden="true"></span><small>${confirmed?'有证据支持的关联书目':'待核书目线索'}</small><strong>${esc(book?.label||'尚未找到明确书目')}</strong><span>${esc(author?.label||'作者信息未齐')}</span></div><p class="book-evidence">${esc(status?.category||'未知')}${!confirmed&&book?' · 仅作线索展示':''}</p>${evidence?`<blockquote class="origin-claim">“${esc(evidence.claim_excerpt)}”</blockquote>${source(evidence.source_url,'核对改编证据')}`:''}${book?source(book.source_url,'打开书目'):''}</div></div></div></div>`;
    document.getElementById('origin-series').addEventListener('change',event=>{originId=event.target.value;drawOrigins();applyPhase('origins',sceneStates.get('origins')?.index||0);});
    applyPhase('origins',sceneStates.get('origins')?.index||0);
  }
  function createTimeline(){
    const el=document.getElementById('exhibit-body-timeline');
    el.innerHTML=`<div class="timeline-topline"><span class="timeline-month">7月</span><div class="timeline-live-values" aria-live="polite"></div></div><div id="moving-lines" class="moving-lines"></div><div class="timeline-scrubber"><div class="timeline-month-labels">${D.part45.novelty.map(row=>`<span>${month(row.month)}</span>`).join('')}</div><div class="timeline-auto-track"><i></i></div><button data-auto-pause type="button">暂停</button></div><p class="exhibit-evidence-note">7月—10月 · 首次入榜作品、系列与结构簇</p>`;
    const width=740,height=330,margin={left:46,right:35,top:35,bottom:35};
    const svg=d3.select('#moving-lines').append('svg').attr('viewBox',`0 0 ${width} ${height}`).attr('role','img').attr('aria-label','7至10月首次出现的作品、系列与结构簇折线图');
    const x=d3.scalePoint().domain([0,1,2,3]).range([margin.left,width-margin.right]),y=d3.scaleLinear().domain([0,110]).range([height-margin.bottom,margin.top]);
    const keys=[['new_work_count','作品','#343b3c'],['new_series_count','系列','#4d8172'],['new_cluster_count','结构簇','#b74655']];
    const clip=svg.append('defs').append('clipPath').attr('id','timeline-reveal').append('rect').attr('x',0).attr('y',0).attr('width',width).attr('height',height);
    [0,25,50,75,100].forEach(value=>{svg.append('line').attr('x1',margin.left).attr('x2',width-margin.right).attr('y1',y(value)).attr('y2',y(value)).attr('stroke','#ddd9d1').attr('stroke-dasharray','2 5');svg.append('text').attr('x',margin.left-13).attr('y',y(value)+4).attr('text-anchor','end').text(value);});
    D.part45.novelty.forEach((row,i)=>svg.append('text').attr('x',x(i)).attr('y',height-10).attr('text-anchor','middle').text(month(row.month)));
    const group=svg.append('g').attr('clip-path','url(#timeline-reveal)');
    keys.forEach(([key,label,color],index)=>{
      const g=group.append('g').attr('class',`timeline-series timeline-series-${index}`);
      g.append('path').datum(D.part45.novelty).attr('d',d3.line().x((r,i)=>x(i)).y(r=>y(r[key]))).attr('fill','none').attr('stroke',color).attr('stroke-width',3);
      g.selectAll('circle').data(D.part45.novelty).join('circle').attr('cx',(r,i)=>x(i)).attr('cy',r=>y(r[key])).attr('r',4).attr('fill',color).append('title').text(r=>`${month(r.month)} · 新${label} ${r[key]}`);
    });
    const focus=svg.append('g').attr('class','timeline-focus');focus.append('line').attr('y1',margin.top-10).attr('y2',height-margin.bottom).attr('stroke','#aaa394').attr('stroke-dasharray','3 4');
    const labels=keys.map(([key,label,color])=>{const g=focus.append('g');g.append('circle').attr('r',6).attr('fill',color).attr('stroke','#fffdf9').attr('stroke-width',2);g.append('text').attr('fill',color).attr('font-size',16).attr('font-weight',600);return g;});
    const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
    function update(index=0,selectedMonth=3,progress=null){
      keys.forEach((_,i)=>svg.select(`.timeline-series-${i}`).style('opacity',i<=Math.min(index,2)?1:.08));
      const row=D.part45.novelty[selectedMonth],position=x(selectedMonth);
      focus.select('line').interrupt().transition().duration(reduce?0:300).attr('x1',position).attr('x2',position);
      keys.forEach(([key,,color],i)=>{const labelX=selectedMonth===3?-12:12;labels[i].style('opacity',i<=Math.min(index,2)?1:0).interrupt().transition().duration(reduce?0:300).attr('transform',`translate(${position},${y(row[key])})`);labels[i].select('text').attr('x',labelX).attr('y',-11).attr('text-anchor',selectedMonth===3?'end':'start').text(row[key]);});
      document.querySelector('.timeline-month').textContent=month(row.month);
      document.querySelector('.timeline-live-values').innerHTML=keys.slice(0,Math.min(index,2)+1).map(([key,label,color])=>`<span style="--line-color:${color}"><i></i>${label}<b>${row[key]}</b></span>`).join('');
      el.querySelectorAll('.timeline-month-labels span').forEach((label,i)=>label.classList.toggle('active',i===selectedMonth));
      el.querySelector('.timeline-auto-track i').style.width=`${(selectedMonth+1)/4*100}%`;
      // 初次进入时从左向右揭开线条，随后保留同一坐标系。
      if(index===0&&progress!=null)clip.attr('width',margin.left+(width-margin.left)*(Math.min(1,progress*2+.12)));
      else clip.interrupt().transition().duration(reduce?0:550).attr('width',width);
    }
    const cycle=autoWindow({root:document.getElementById('exhibit-timeline').querySelector('.exhibit-frame'),count:4,active:()=>sceneStates.get('timeline').index===3,onChange:monthIndex=>{const state=sceneStates.get('timeline');state.month=monthIndex;update(state.index,monthIndex);}});
    update.sync=()=>{cycle.setIndex(sceneStates.get('timeline').month);cycle.refresh();};
    return update;
  }
  let updateTimeline;
  function applyPhase(id,index){
    const root=document.getElementById(`exhibit-${id}`);root.dataset.phase=index;
    root.querySelectorAll('.exhibit-step').forEach((node,i)=>node.classList.toggle('is-active',i===index));
    root.querySelectorAll('[data-exhibit-goto]').forEach((button,i)=>{button.classList.toggle('active',i===index);button.setAttribute('aria-pressed',String(i===index));});
    root.querySelector('.exhibit-page').textContent=`${String(index+1).padStart(2,'0')} / ${String(sequences[id].steps.length).padStart(2,'0')}`;
    root.querySelector('.exhibit-progress i').style.width=`${(index+1)/sequences[id].steps.length*100}%`;
    root.querySelector('[data-exhibit-prev]').disabled=index===0;root.querySelector('[data-exhibit-next]').disabled=index===sequences[id].steps.length-1;
    if(id==='origins'){root.querySelector('.origin-slide-track')?.style.setProperty('--origin',index);root.querySelectorAll('.origin-slide').forEach((slide,i)=>{slide.inert=i!==index;slide.setAttribute('aria-hidden',String(i!==index));});}
    if(id==='timeline'&&updateTimeline){updateTimeline(index,sceneStates.get(id)?.month??3);updateTimeline.sync();}
  }
  for(const id of Object.keys(sequences))sceneStates.set(id,{index:0,month:3});
  drawOrigins();updateTimeline=createTimeline();
  function go(id,index,scroll=false){const count=sequences[id].steps.length,i=Math.max(0,Math.min(count-1,index)),s=sceneStates.get(id);if(id==='timeline'&&i===3&&s.index!==3)s.month=0;s.index=i;applyPhase(id,i);if(scroll)document.querySelectorAll(`#exhibit-${id} .exhibit-step`)[i].scrollIntoView({block:'center',behavior:'instant'});}
  const scrollers=[];
  for(const [id,config] of Object.entries(sequences)){
    const root=document.getElementById(`exhibit-${id}`);if(!root)continue;
    go(id,0);const frame=root.querySelector('.exhibit-frame');
    const scroller=scrollama().setup({step:root.querySelectorAll('.exhibit-step'),offset:innerWidth<760?.78:.53,progress:true}).onStepEnter(({index})=>go(id,index)).onStepProgress(({index,progress})=>{if(id==='timeline'&&sceneStates.get(id).index===index){if(index===0)updateTimeline(index,3,progress);}});
    scrollers.push(scroller);
    frame.addEventListener('keydown',event=>{if(event.target.matches('input,select'))return;if(['ArrowLeft','ArrowRight'].includes(event.key)){event.preventDefault();go(id,sceneStates.get(id).index+(event.key==='ArrowRight'?1:-1),true);}});
    let touchStart=null;frame.addEventListener('touchstart',event=>{if(event.target.closest('input,select,button'))return;touchStart=[event.touches[0].clientX,event.touches[0].clientY];},{passive:true});frame.addEventListener('touchend',event=>{if(!touchStart)return;const dx=event.changedTouches[0].clientX-touchStart[0],dy=event.changedTouches[0].clientY-touchStart[1];if(Math.abs(dx)>55&&Math.abs(dx)>Math.abs(dy)*1.3)go(id,sceneStates.get(id).index+(dx<0?1:-1),true);touchStart=null;},{passive:true});
  }
  document.addEventListener('click',event=>{const next=event.target.closest('[data-exhibit-next]'),prev=event.target.closest('[data-exhibit-prev]'),target=event.target.closest('[data-exhibit-goto]');if(next)go(next.dataset.exhibitNext,sceneStates.get(next.dataset.exhibitNext).index+1,true);if(prev)go(prev.dataset.exhibitPrev,sceneStates.get(prev.dataset.exhibitPrev).index-1,true);if(target)go(target.dataset.exhibitGoto,+target.dataset.position,true);});
  window.addEventListener('resize',()=>scrollers.forEach(scroller=>scroller.resize()));
  window.exhibits={go,list:()=>Object.keys(sequences).filter(id=>document.getElementById(`exhibit-${id}`)),state:sceneStates};
}
