import * as d3 from "../../d3.js";
import { fmt, DUR, size, INK, chrome, CATEGORICAL, drawAnnotations, showTip, hideTip, rowsHtml, num, where } from "../util.js";
/** Histogram — distribution of one numeric column over many rows.
 *  spec: {data, x, bins: 20 | [thresholds], xDomain, format, xLabel, color, where}
 *  state: {title, subtitle, where, bins, normalize:bool (share of rows), highlightRange:[lo,hi], highlightColor, showMean, showMedian, annotations:[{x,text}], compareWhere: {…} (overlay a second filtered distribution as outline)} */
export function createHistogram(container, spec, datasets) {
  const el = d3.select(container), svg = el.append("svg"); const ch = chrome(el, svg);
  const gAxes = svg.append("g"), gx = gAxes.append("g").attr("class", "axis x"), gy = gAxes.append("g").attr("class", "axis y"), gGrid = gAxes.append("g").attr("class", "grid");
  const xLab = gAxes.append("text").attr("class", "chart-sub").attr("text-anchor", "end");
  const gBars = svg.append("g"), gCmp = svg.append("g"), gAnn = svg.append("g").attr("class", "annot"); const f = fmt(spec.format);
  const vals = (w) => where(datasets[spec.data], w).map((r) => num(r[spec.x])).filter((v) => v != null);
  return {
    render(state, immediate) {
      const { width, height } = size(container); svg.attr("viewBox", `0 0 ${width} ${height}`); const t = immediate ? 0 : DUR();
      ch.set(state.title ?? spec.title, state.subtitle ?? spec.subtitle);
      const v = vals(state.where ?? spec.where); const M = { top: 84, right: 30, bottom: 44, left: 56 }; const iw = width - M.left - M.right, ih = height - M.top - M.bottom;
      const dom = spec.xDomain || d3.extent(v); const x = d3.scaleLinear().domain(dom).nice().range([M.left, M.left + iw]);
      const b = state.bins ?? spec.bins ?? 20; const binner = d3.bin().domain(x.domain()).thresholds(Array.isArray(b) ? b : x.ticks(b));
      const bins = binner(v); const share = !!state.normalize; const n = v.length;
      const val = (d) => (share ? d.length / Math.max(1, n) : d.length);
      const cmp = state.compareWhere ? binner(vals(state.compareWhere)) : null; const ncmp = cmp ? d3.sum(cmp, (d) => d.length) : 0;
      const cval = (d) => (share ? d.length / Math.max(1, ncmp) : d.length);
      const y = d3.scaleLinear().domain([0, d3.max([...bins.map(val), ...(cmp ? cmp.map(cval) : [])]) || 1]).nice().range([M.top + ih, M.top]);
      gx.attr("transform", `translate(0,${M.top + ih})`).transition().duration(t).call(d3.axisBottom(x).ticks(8).tickFormat(f).tickSize(0).tickPadding(10));
      gy.attr("transform", `translate(${M.left},0)`).transition().duration(t).call(d3.axisLeft(y).ticks(5).tickFormat(share ? d3.format(".0%") : d3.format(",.0f")).tickSize(0).tickPadding(8));
      gGrid.attr("transform", `translate(${M.left},0)`).transition().duration(t).call(d3.axisLeft(y).ticks(5).tickSize(-iw).tickFormat("")); gGrid.selectAll(".domain").remove();
      xLab.attr("x", M.left + iw).attr("y", M.top + ih + 40).text(spec.xLabel || spec.x);
      const hr = state.highlightRange; const hiC = state.highlightColor || CATEGORICAL[1];
      const bars = gBars.selectAll("rect").data(bins, (d) => d.x0);
      bars.enter().append("rect").attr("x", (d) => x(d.x0) + 1).attr("y", y(0)).attr("height", 0).attr("width", (d) => Math.max(0, x(d.x1) - x(d.x0) - 2)).attr("rx", 2)
        .merge(bars)
        .on("mousemove", (ev, d) => showTip(`<b>${f(d.x0)} – ${f(d.x1)}</b>` + rowsHtml([["Rows", d3.format(",")(d.length)], ["Share", d3.format(".1%")(d.length / Math.max(1, n))]]), ev)).on("mouseleave", hideTip)
        .transition().duration(t).attr("x", (d) => x(d.x0) + 1).attr("width", (d) => Math.max(0, x(d.x1) - x(d.x0) - 2)).attr("y", (d) => y(val(d))).attr("height", (d) => y(0) - y(val(d)))
        .attr("fill", (d) => (hr && d.x0 >= hr[0] && d.x1 <= hr[1] + 1e-9 ? hiC : spec.color || CATEGORICAL[0])).attr("opacity", (d) => (hr && !(d.x0 >= hr[0] && d.x1 <= hr[1] + 1e-9) ? 0.35 : 0.9));
      bars.exit().transition().duration(t / 2).attr("height", 0).attr("y", y(0)).remove();
      // comparison outline
      const step = d3.line().x((d) => x(d.x0)).y((d) => y(cval(d))).curve(d3.curveStepAfter);
      const c = gCmp.selectAll("path").data(cmp ? [cmp.concat([{ x0: cmp[cmp.length - 1].x1, length: 0 }])] : []);
      c.enter().append("path").attr("fill", "none").attr("stroke", INK.ink).attr("stroke-width", 2).attr("opacity", 0).merge(c).attr("d", step).transition().duration(t).attr("opacity", 0.9);
      c.exit().transition().duration(t / 2).attr("opacity", 0).remove();
      const anns = [...(state.annotations || [])];
      if (state.showMean) anns.push({ id: "__mean", x: d3.mean(v), xRule: true, text: `mean ${f(d3.mean(v))}`, anchor: "start" });
      if (state.showMedian) anns.push({ id: "__median", x: d3.median(v), xRule: true, text: `median ${f(d3.median(v))}`, anchor: "start", level: 1 });
      drawAnnotations(gAnn, anns, x, y, t, { top: M.top, bottom: M.top + ih });
      ch.legend([[state.legend || `${d3.format(",")(n)} rows`, spec.color || CATEGORICAL[0]], ...(hr ? [[state.highlightLabel || `${f(hr[0])}–${f(hr[1])}`, hiC]] : []), ...(cmp ? [[state.compareLabel || "comparison", INK.ink]] : [])]); ch.legendLeft(M.left);
    }, resize() {}, progress() {},
  };
}
