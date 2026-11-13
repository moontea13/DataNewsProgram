import * as d3 from './vendor/d3.js';
import scrollama from './vendor/scrollama.js';
import { applyTheme, deepMerge, INK, showTip, hideTip, DUR } from './vendor/scrollytelling-kit/util.js';
import { createWaffle } from './vendor/scrollytelling-kit/charts/waffle.js';
import { createBar } from './vendor/scrollytelling-kit/charts/bar.js';
import { esc, pct, month } from './components.js';

const accent='#bc412f', sage='#6c8175', ink='#292c28', gold='#b39a68';
const resolve=value=>value;
const registry=[];
let themeReady=false;
function theme() {if(!themeReady){applyTheme({preset:'paper',accent,palette:[accent,sage,gold,ink]});themeReady=true;}}

export function kitBar(container,values,title,subtitle) {
  theme();
  const chart=createBar(container,{format:'.0f',color:sage,valueLabel:'覆盖系列数'}, {},{resolve});
  const state={title,subtitle,values,highlight:[values[0]?.category],highlightColor:accent};
  let visible=false;
  const render=immediate=>{chart.render(state,immediate);if(!visible)d3.select(container).selectAll('g.bar rect').interrupt().attr('width',0);};
  render(true);
  const observer=new IntersectionObserver(entries=>{visible=entries.some(entry=>entry.isIntersecting);if(visible){d3.select(container).selectAll('g.bar rect').interrupt().attr('width',0);render(false);}},{threshold:.15});
  observer.observe(container);
  registry.push(()=>render(!visible));
  window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});
}

// 复用Kit的幂等步状态机制：defaults + 当前step，不累计上一步的状态。
export function initScenes(D, configs) {
  theme();
  const waffleElement=document.getElementById('cover-waffle');
  const waffle=waffleElement?createWaffle(waffleElement,{cells:100,color:accent,format:'.0f'}, {},{resolve}):null;
  const coverStates={
    whole:{value:0,total:169,label:'达到整图主阈值的系列',sublabel:'DINOv2中心裁切 ≥ 0.85',title:'完整封面：0 / 169',subtitle:'排除关联疑点后的跨系列比较'},
    layout:{value:95,total:162,label:'文字布局与区域颜色接近',sublabel:'95 / 162张OCR有效封面',title:'文字排版：95 / 162',subtitle:'至少与另一系列满足布局及区域颜色条件'},
    joint:{value:9,total:162,label:'布局、颜色与图像联合候选',sublabel:'9 / 162张OCR有效封面',title:'联合规则：9 / 162',subtitle:'同一对封面再要求DINOv2完整图 ≥ 0.70'},
  };
  let currentCover='whole';
  function coverRender(state, immediate) {
    if(!waffle)return;
    currentCover=state.mode;
    waffle.render(coverStates[state.mode],immediate);
    const rates={whole:'0.00%',layout:'58.64%',joint:'5.56%'};
    document.getElementById('cover-metric').innerHTML=`<span>${rates[state.mode]}</span><small>在对应有效样本中涉及的系列占比<br>方格按百分比取整；精确值以数字为准</small>`;
  }
  const renewalContainer=document.getElementById('renewal-chart');
  const renewalSvg=d3.select(renewalContainer).append('svg').attr('role','img');
  let currentLevel='work';
  function renewalRender(state,immediate=false) {
    currentLevel=state.level;
    const bounds=renewalContainer.getBoundingClientRect(),w=Math.max(300,bounds.width),h=Math.max(300,bounds.height);
    renewalSvg.attr('viewBox',`0 0 ${w} ${h}`);
    const fields={work:'new_work_count',series:'new_series_count',cluster:'new_cluster_count'};
    const labels={work:'分季作品',series:'独立系列',cluster:'全局结构簇'};
    const rows=D.part45.novelty.slice(1);
    const x=d3.scaleBand().domain(rows.map(r=>r.month)).range([48,w-20]).padding(.5);
    const y=d3.scaleLinear().domain([0,100]).range([h-62,38]);
    renewalSvg.selectAll('.gridline').data([0,25,50,75,100]).join('g').attr('class','gridline').each(function(value){const group=d3.select(this);group.selectAll('line').data([value]).join('line').attr('x1',43).attr('x2',w-16).attr('y1',y(value)).attr('y2',y(value)).attr('stroke','#ddd9cf').attr('stroke-dasharray','2 4');group.selectAll('text').data([value]).join('text').attr('x',30).attr('y',y(value)+4).attr('text-anchor','end').text(value);});
    const bars=renewalSvg.selectAll('g.renewal-bar').data(rows,row=>row.month).join(enter=>{const g=enter.append('g').attr('class','renewal-bar');g.append('rect').attr('y',y(0)).attr('height',0).attr('rx',2);g.append('text').attr('class','bar-value');g.append('text').attr('class','bar-month');return g;});
    bars.select('rect').attr('x',r=>x(r.month)).attr('width',x.bandwidth()).attr('fill',state.level==='work'?ink:state.level==='series'?sage:accent).interrupt().transition().duration(immediate?0:DUR()).attr('y',r=>y(r[fields[state.level]])).attr('height',r=>y(0)-y(r[fields[state.level]]));
    bars.select('.bar-value').attr('x',r=>x(r.month)+x.bandwidth()/2).attr('text-anchor','middle').text(r=>r[fields[state.level]]).interrupt().transition().duration(immediate?0:DUR()).attr('y',r=>y(r[fields[state.level]])-13);
    bars.select('.bar-month').attr('x',r=>x(r.month)+x.bandwidth()/2).attr('y',h-31).attr('text-anchor','middle').text(r=>month(r.month));
    document.getElementById('renewal-stage').innerHTML=`<i style="background:${state.level==='work'?ink:state.level==='series'?sage:accent}"></i>${labels[state.level]}<small>7月作为基线，图中呈现8—10月</small>`;
  }
  const renewalObserver=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){const baseline=Math.max(300,renewalContainer.getBoundingClientRect().height)-62;renewalSvg.selectAll('g.renewal-bar rect').interrupt().attr('y',baseline).attr('height',0);renewalRender({level:currentLevel},false);}},{threshold:.2});
  renewalObserver.observe(renewalContainer);
  window.addEventListener('pagehide',()=>renewalObserver.disconnect(),{once:true});
  const field=document.getElementById('comment-dot-field');
  const dotSvg=d3.select(field).append('svg').attr('viewBox','0 0 610 500').attr('aria-hidden','true');
  const dots=dotSvg.selectAll('circle').data(d3.range(D.part45.counts.validComments)).join('circle').attr('cx',value=>(value%61)*10+5).attr('cy',value=>Math.floor(value/61)*10+5).attr('r',3);
  function feedbackRender(state) {
    field.dataset.mode=state.mode;
    dots.classed('is-mention',value=>value<27);
    document.getElementById('feedback-figure-number').textContent=state.mode==='all'?'3,049':'27';
    document.getElementById('feedback-figure-label').textContent=state.mode==='all'?'条有效观众热评':'条跨系列相似反馈 · 占0.89%';
  }
  const scenes=[
    {id:'cover',steps:configs.coverSteps,render:coverRender,defaults:{mode:'whole'}},
    {id:'renewal',steps:configs.renewalSteps,render:renewalRender,defaults:{level:'work'}},
    {id:'feedback',steps:configs.feedbackSteps,render:feedbackRender,defaults:{mode:'all'}},
  ].filter(scene=>document.getElementById(`scrolly-${scene.id}`));
  const scrollers=[];
  function goto(id,index,scroll=false) {
    const scene=scenes.find(scene=>scene.id===id);if(!scene)return false;
    const i=Math.max(0,Math.min(scene.steps.length-1,Number(index)||0));
    const element=document.getElementById(`scrolly-${id}`);
    element.querySelectorAll('.step').forEach((step,j)=>step.classList.toggle('is-active',j===i));
    element.querySelectorAll('.scene-dots button').forEach((button,j)=>{button.classList.toggle('active',j===i);button.setAttribute('aria-pressed',String(j===i));});
    scene.lastIndex=i;scene.render(deepMerge(scene.defaults,scene.steps[i].state),false);
    if(scroll)element.querySelectorAll('.step')[i].scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
    return true;
  }
  for(const scene of scenes) {
    scene.render(deepMerge(scene.defaults,scene.steps[0].state),true);
    const element=document.getElementById(`scrolly-${scene.id}`);
    const steps=element.querySelectorAll('.step');
    steps[0].classList.add('is-active');
    const scroller=scrollama();
    scroller.setup({step:steps,offset:innerWidth<760?.78:.55}).onStepEnter(({index})=>goto(scene.id,index)).onStepExit(({index,direction})=>{if(index===0&&direction==='up')goto(scene.id,0);});
    scrollers.push(scroller);
  }
  document.querySelectorAll('.scene-dots button').forEach(button=>button.addEventListener('click',()=>goto(button.dataset.scene,+button.dataset.index,true)));
  // 保留Kit提供的深链/确定性跳步接口，方便逐场景验收。
  window.scrolly={goto,list:()=>scenes.map(scene=>({scene:scene.id,steps:scene.steps.length})),scenes};
  let timer;window.addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(()=>{coverRender({mode:currentCover},true);renewalRender({level:currentLevel},true);registry.forEach(render=>render());scrollers.forEach(scroller=>scroller.resize());},180);});
}

export function drawHeatmap(container,rows) {
  const genres=[...new Set(rows.map(row=>row.genre))];
  const reversals=[...new Set(rows.map(row=>row.reversal))].slice(0,7);
  const w=850,left=104,top=85,cellW=(w-left-20)/reversals.length,cellH=43,h=top+genres.length*cellH+40;
  const svg=d3.select(container).append('svg').attr('viewBox',`0 0 ${w} ${h}`).attr('role','img').attr('aria-label','不同题材中翻盘表述的占比热力图');
  const color=d3.scaleSequential().domain([0,100]).interpolator(d3.interpolateRgb('#eee8dd',accent));
  genres.forEach((genre,i)=>svg.append('text').attr('x',left-15).attr('y',top+i*cellH+cellH/2+4).attr('text-anchor','end').text(genre));
  reversals.forEach((reversal,i)=>svg.append('text').attr('transform',`translate(${left+i*cellW+cellW/2},${top-14})`).attr('text-anchor','middle').text(reversal.replace('金手指','优势').replace('优势优势','优势')));
  for(const row of rows.filter(row=>reversals.includes(row.reversal))) {
    const x=left+reversals.indexOf(row.reversal)*cellW,y=top+genres.indexOf(row.genre)*cellH;
    const g=svg.append('g');
    g.append('rect').attr('x',x+2).attr('y',y+2).attr('width',cellW-5).attr('height',cellH-5).attr('rx',2).attr('fill',row.denominator?color(row.percent):'#e7e4dd');
    g.append('text').attr('x',x+cellW/2).attr('y',y+cellH/2+4).attr('text-anchor','middle').attr('fill',row.percent>55?'#fff':'#504c44').text(row.denominator?`${row.percent.toFixed(0)}%`:'—');
    const valueLabel=row.percent==null?'暂无有效分母':`${row.percent.toFixed(1)}%`;
    g.append('title').text(`${row.genre} × ${row.reversal}：${row.count} / ${row.denominator}，${valueLabel}`);
    g.on('mousemove',event=>showTip(`<b>${esc(row.genre)} × ${esc(row.reversal)}</b><p>${row.count} / ${row.denominator} 个系列 · ${valueLabel}</p>`,event)).on('mouseleave',hideTip);
  }
}

export function drawNovelty(container,D) {
  container.innerHTML='';
  const w=920,h=305,left=45,top=32,bottom=47;
  const svg=d3.select(container).append('svg').attr('viewBox',`0 0 ${w} ${h}`).attr('role','img').attr('aria-label','四个月新增作品、系列和结构簇数量的分组柱形图');
  const x=d3.scaleBand().domain(D.novelty.map(row=>row.month)).range([left,w-20]).padding(.4),y=d3.scaleLinear().domain([0,110]).range([h-bottom,top]);
  [0,25,50,75,100].forEach(value=>{svg.append('line').attr('x1',left).attr('x2',w-20).attr('y1',y(value)).attr('y2',y(value)).attr('stroke','#dfdbd2');svg.append('text').attr('x',left-12).attr('y',y(value)+4).attr('text-anchor','end').text(value);});
  const kinds=[['new_work_count','作品',ink],['new_series_count','系列',sage],['new_cluster_count','结构簇',accent]];
  D.novelty.forEach(row=>{kinds.forEach(([field,label,color],i)=>{const width=x.bandwidth()/3-5,xx=x(row.month)+i*(width+5);svg.append('rect').attr('x',xx).attr('y',y(row[field])).attr('width',width).attr('height',y(0)-y(row[field])).attr('fill',color).append('title').text(`${month(row.month)}新增${label}：${row[field]}`);svg.append('text').attr('x',xx+width/2).attr('y',y(row[field])-8).attr('text-anchor','middle').text(row[field]);});svg.append('text').attr('x',x(row.month)+x.bandwidth()/2).attr('y',h-21).attr('text-anchor','middle').text(`${month(row.month)}${row.baseline?' · 基线':''}`);});
  const legend=d3.select(container).append('div').attr('class','chart-html-legend');kinds.forEach(([,label,color])=>legend.append('span').html(`<i style="background:${color}"></i>${label}`));
}

export function drawConcentration(container,D,m,basis) {
  const clusterMap=new Map(D.clusters.map(row=>[row.cluster_id,row]));
  const clusterColor=id=>clusterMap.get(id)?.color || '#d9d5ca';
  container.innerHTML=`<div class="node-panels">${['head','tail'].map(group=>{
    let nodes=D.nodes.filter(row=>row.month===m&&row.rank_group===group).sort((a,b)=>a.rank-b.rank);
    if(basis==='系列去重')nodes=nodes.filter((row,i,all)=>all.findIndex(other=>other.series_id===row.series_id)===i);
    nodes.sort((a,b)=>(a.cluster_id||'ZZZ').localeCompare(b.cluster_id||'ZZZ')||a.rank-b.rank);
    const stats=D.concentration.find(row=>row.month===m&&row.rank_group===group&&row.counting_basis===basis);
    return `<div class="node-panel"><div class="node-heading"><h4>${group==='head'?'头部':'尾部'}<small>${group==='head'?'第1—20名':'第81—100名'}</small></h4><span>${nodes.length}个${basis==='榜位'?'榜位':'系列'}</span></div><div class="node-grid">${nodes.map(row=>`<button style="--node-color:${clusterColor(row.cluster_id)}" data-node="${esc(row.ranking_id)}" aria-label="第${row.rank}名，${esc(row.title)}，${esc(row.cluster_name||'未分簇')}" title="${esc(row.title)} · ${esc(row.cluster_name||'未分簇')}">${row.rank}</button>`).join('')}</div><div class="node-stat"><span><b>${stats.cluster_count}</b>结构簇</span><span><b>${pct(stats.pair_ratio)}</b>同簇配对</span><span><b>${pct(stats.top3_share,0)}</b>前三簇占比</span></div></div>`;
  }).join('')}</div><div class="concentration-bottom"><p>同簇配对越多，简介核心结构越集中。<br>系列去重后，续季占据的多个榜位合并计一次。</p><div><span>四个月头部－尾部平均差</span><strong>${(D.meanDifferences.find(row=>row.counting_basis===basis).pair_ratio_mean_difference*100).toFixed(2)}<small>个百分点</small></strong></div></div>`;
}

export function drawModelCurve(container,D,key,threshold=.85) {
  const animateModel=container.dataset.variant!==key;
  container.dataset.variant=key;
  const rows=D.variants[key].thresholds;
  const selected=rows.find(row=>Math.abs(row.threshold-threshold)<.001);
  document.getElementById('threshold-output').textContent=threshold.toFixed(2);
  document.getElementById('threshold-rate').textContent=`${selected.series_rate.percent.toFixed(2)}%`;
  document.getElementById('threshold-count').textContent=`${selected.series_rate.numerator} / ${selected.series_rate.denominator} 个系列`;
  container.innerHTML='';
  const width=900,height=240,M={left:55,right:25,top:20,bottom:43};
  const svg=d3.select(container).append('svg').attr('viewBox',`0 0 ${width} ${height}`).attr('role','img').attr('aria-label',`${D.variants[key].label}各阈值下的涉及系列比例`);
  const x=d3.scaleLinear().domain([.5,.95]).range([M.left,width-M.right]),y=d3.scaleLinear().domain([0,100]).range([height-M.bottom,M.top]);
  [0,25,50,75,100].forEach(value=>{svg.append('line').attr('x1',M.left).attr('x2',width-M.right).attr('y1',y(value)).attr('y2',y(value)).attr('stroke','#ded9d0').attr('stroke-dasharray','3 4');svg.append('text').attr('x',M.left-12).attr('y',y(value)+4).attr('text-anchor','end').text(`${value}%`);});
  rows.forEach(row=>svg.append('text').attr('x',x(row.threshold)).attr('y',height-19).attr('text-anchor','middle').text(row.threshold.toFixed(2)));
  const line=d3.line().x(row=>x(row.threshold)).y(row=>y(row.series_rate.percent));
  const curve=svg.append('path').datum(rows).attr('d',line).attr('fill','none').attr('stroke',sage).attr('stroke-width',2.5);
  if(animateModel&&!matchMedia('(prefers-reduced-motion: reduce)').matches){const length=curve.node().getTotalLength();curve.attr('stroke-dasharray',`${length} ${length}`).attr('stroke-dashoffset',length).transition().duration(750).ease(d3.easeCubicOut).attr('stroke-dashoffset',0);}
  svg.selectAll('circle').data(rows).join('circle').attr('cx',row=>x(row.threshold)).attr('cy',row=>y(row.series_rate.percent)).attr('r',row=>Math.abs(row.threshold-threshold)<.001?6:3).attr('fill',row=>Math.abs(row.threshold-threshold)<.001?accent:sage).append('title').text(row=>`${row.threshold.toFixed(2)}：${row.series_rate.numerator}/${row.series_rate.denominator}，${row.series_rate.percent.toFixed(2)}%`);
  svg.append('line').attr('x1',x(threshold)).attr('x2',x(threshold)).attr('y1',M.top).attr('y2',height-M.bottom).attr('stroke',accent).attr('stroke-dasharray','3 4').attr('opacity',.5);
}
