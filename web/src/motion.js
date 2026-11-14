const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

/** 轮换只在窗口进入视野时推进；悬停、键盘聚焦及读详情时停留。 */
export function autoWindow({root, count, onChange, duration=5500, active=()=>true}) {
  let index=0,visible=false,hovered=false,focused=false,timer;
  function sync(){clearInterval(timer);if(visible&&!reduced()&&!hovered&&!focused&&!document.hidden)timer=setInterval(()=>{if(active()&&!document.querySelector('dialog[open]')){index=(index+1)%count;onChange(index);}},duration);}
  const observer=new IntersectionObserver(entries=>{visible=entries.some(entry=>entry.isIntersecting);sync();},{threshold:.25});observer.observe(root);
  root.addEventListener('mouseenter',()=>{hovered=true;sync();});root.addEventListener('mouseleave',()=>{hovered=false;sync();});
  root.addEventListener('focusin',()=>{focused=true;sync();});root.addEventListener('focusout',event=>{focused=Boolean(event.relatedTarget&&root.contains(event.relatedTarget));sync();});
  document.addEventListener('visibilitychange',sync);
  window.addEventListener('pagehide',()=>{clearInterval(timer);observer.disconnect();},{once:true});
  return {setIndex(value){index=Math.max(0,Math.min(count-1,value));},refresh:sync};
}

export function initMotion() {
  const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{entry.target.classList.toggle('is-revealed',entry.isIntersecting);}),{threshold:.08});
  const observe=root=>{
    const groups=root.matches?.('[data-reveal],.adaptation-bars,.reuse-bars,.phrase-bars,.monthly-comparison,#attitude-chart')?[root]:[];
    groups.push(...root.querySelectorAll('[data-reveal],.adaptation-bars,.reuse-bars,.phrase-bars,.monthly-comparison,#attitude-chart'));
    for(const group of groups){if(!group.dataset.motionObserved){group.dataset.motionObserved='true';group.classList.add('motion-ready');observer.observe(group);}group.querySelectorAll('.bar-row,.reuse-row,.attitude-row,.board-cover,.monthly-comparison>div').forEach((row,index)=>row.style.setProperty('--reveal-order',index%8));}
  };
  observe(document.getElementById('app'));
  const changes=new MutationObserver(entries=>{for(const entry of entries)for(const node of entry.addedNodes)if(node.nodeType===1)observe(node);});
  changes.observe(document.getElementById('app'),{subtree:true,childList:true});
  window.addEventListener('pagehide',()=>{observer.disconnect();changes.disconnect();},{once:true});
}
