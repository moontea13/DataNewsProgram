export const chapters = [
  ['opening', '序', '进入片场'], ['appearance', '一', '第一眼的相似'],
  ['stories', '二', '故事的配方'], ['origins', '三', '故事从哪里来'],
  ['renewal', '四', '榜单的换新'], ['audience', '五', '观众的回声'], ['ending', '终', '下一部故事'],
];

// 图表与文字分开：每一步完整描述状态，支持反向滚动。
export const coverSteps = [
  { heading:'看起来熟悉，能被测量吗？', text:'我们为169个系列各选取一张固定代表封面，比较不同系列之间的图像。续季和跨月上榜不会重复计入。', label:'先看完整图像', state:{ mode:'whole' } },
  { heading:'相像的，也许是文字的摆法。', text:'在162张能有效识别标题的封面中，95张至少与另一张封面的文字位置、面积、方向、框数及区域颜色同时接近。', label:'把视线移向标题', state:{ mode:'layout' } },
  { heading:'排版相近，不代表整张图相同。', text:'继续要求同一对封面的完整图DINOv2分数达到0.70，联合候选只涉及9个系列。衡量的层次不同，答案也不同。', label:'再把两种证据合起来', state:{ mode:'joint' } },
];

export const renewalSteps = [
  { heading:'新作品上榜情况。', text:'8—10月，每月首次进入hot100榜单的作品分别有91、91、86部。榜单在不断换新？', label:'按作品看', state:{ level:'work' } },
  { heading:'合并续季之后，新出现的系列变少了。', text:'将同系列的不同季合并，新入榜系列减少为为23、48、55个。', label:'按独立系列看', state:{ level:'series' } },
  { heading:'接着我们看看熟悉的故事结构。', text:'大模型按简介语义划分故事结构簇。8—10月首次出现的结构簇为11、20、16个。', label:'按全局结构簇看', state:{ level:'cluster' } },
];

export const feedbackSteps = [
  { heading:'评论会提到“像”吗？', text:'3,260条公开页热评经筛选，得到3,049条有效观众评论。其中27条明确提及不同系列之间的相似。', label:'吐槽并不多见', state:{ mode:'all' } },
  { heading:'27条占s0.89%。', text:'这些反馈涉及24部作品，占有有效热评的361部作品的6.65%。', label:'找出明确的相似反馈', state:{ mode:'highlight' } },
  { heading:'观众对于同质化有不同的态度', text:'有人反感重复，有人接受熟悉的配方，也有人专门赞赏对套路的改变。继续读原句，看“相似”和“评价”怎样交织。', label:'回到观众的原话', state:{ mode:'focus' } },
];
