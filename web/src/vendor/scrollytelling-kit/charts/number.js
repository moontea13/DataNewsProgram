import * as d3 from "../../d3.js";
import { fmt, DUR, size, INK, CATEGORICAL } from "../util.js";
/** Hero number(s).
 *  spec: {format, color}
 *  state (single):  {value: ref, label, sublabel, from}                     → big number, no circle (add dot:true to force one)
 *  state (compare): {values: [{value: ref, label, color}, {…}], sublabel}   → 2–3 circles side by side, area ∝ value, number above each */
export function createNumber(container, spec, datasets, { resolve }) {
  const svg = d3.select(container).append("svg");
  const g = svg.append("g");
  const sub = svg.append("text").attr("class", "chart-sub").attr("text-anchor", "middle");
  const f = fmt(spec.format);
  const last = new Map();
  function tweenText(sel, key, to, from, t) {
    sel.transition().duration(t).tween("text", function () { const i = d3.interpolateNumber(from ?? last.get(key) ?? 0, to); return (k) => (this.textContent = f(i(k))); }).on("end", () => last.set(key, to));
  }
  return {
    render(state, immediate) {
      const { width, height } = size(container); svg.attr("viewBox", `0 0 ${width} ${height}`);
      const t = immediate ? 0 : Math.max(DUR(), 1200);
      const cy = height * 0.42;
      const items = state.values ? state.values.map((d, i) => ({ key: d.key || d.label || String(i), v: resolve(d.value), label: d.label || "", color: d.color || CATEGORICAL[i % CATEGORICAL.length] })) : [{ key: "single", v: resolve(state.value), label: state.label || "", color: spec.color || CATEGORICAL[3] }];
      const compare = !!state.values && items.length > 1;
      const dots = compare || state.dot === true;
      const maxV = compare ? d3.max(items, (d) => Math.abs(d.v || 0)) : (resolve(state.max) ?? Math.abs(items[0].v || 0));
      const R = Math.min(width / (items.length * 2.6), height * 0.2);
      const r = d3.scaleSqrt().domain([0, Math.max(1e-9, maxV)]).range([0, R]);
      const slot = width / (items.length + 1);
      const sel = g.selectAll("g.item").data(items, (d) => d.key);
      const en = sel.enter().append("g").attr("class", "item").attr("opacity", 0);
      en.append("circle").attr("r", 0);
      en.append("text").attr("class", "hero-num").attr("text-anchor", "middle");
      en.append("text").attr("class", "label").attr("text-anchor", "middle");
      const m = en.merge(sel);
      m.transition().duration(t).attr("opacity", 1);
      m.select("circle").attr("cx", (d, i) => slot * (i + 1)).attr("cy", cy).attr("fill", (d) => d.color).transition().duration(t).attr("r", (d) => (dots ? Math.max(4, r(Math.abs(d.v || 0))) : 0));
      const numY = dots ? cy - R - 40 : cy, fs = compare ? Math.min(56, width / (items.length * 5)) : Math.min(72, width / 9);
      m.select("text.hero-num").attr("x", (d, i) => slot * (i + 1)).attr("y", numY).attr("font-size", fs).each(function (d) { tweenText(d3.select(this), d.key, d.v || 0, state.from, t); });
      m.select("text.label").attr("x", (d, i) => slot * (i + 1)).attr("y", dots ? cy - R - 16 : cy + 26).text((d) => d.label);
      sel.exit().transition().duration(t / 2).attr("opacity", 0).remove();
      sub.attr("x", width / 2).attr("y", dots ? cy + R + 28 : cy + 48).text(state.sublabel || "");
    },
    resize() {}, progress() {},
  };
}
