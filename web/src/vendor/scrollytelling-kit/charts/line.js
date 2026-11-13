import * as d3 from "../../d3.js";
import { fmt, DUR, size, INK, chrome, colorFor, labelFor, drawAnnotations, showTip, hideTip, rowsHtml, num, where } from "../util.js";
/** Lines. Long form: spec {data, x, y, series (column whose values are the lines)} or wide: {data, x, ys:[cols]}.
 *  Optional facet: {facet: col, facets:[values]} → small multiples grid, one panel per facet value, shared y.
 *  state: {title, subtitle, series:[keys to show], highlight:[keys], focus: facetValue, annotations:[{facet?, x, y|series, text}], yDomain, where} */
export function createLine(container, spec, datasets) {
  const el = d3.select(container), svg = el.append("svg"); const ch = chrome(el, svg);
  const gPanels = svg.append("g"); const f = fmt(spec.format), fx = spec.xFormat ? d3.format(spec.xFormat) : d3.format("d");
  const base = datasets[spec.data];
  function seriesFor(rows) {
    if (spec.ys) return spec.ys.map((k) => ({ key: k, rows: rows.map((r) => ({ x: +r[spec.x], v: num(r[k]) })).filter((d) => d.v != null).sort((a, b) => a.x - b.x) }));
    return [...d3.group(rows, (r) => r[spec.series])].map(([key, rs]) => ({ key, rows: rs.map((r) => ({ x: +r[spec.x], v: num(r[spec.y]) })).filter((d) => d.v != null).sort((a, b) => a.x - b.x) }));
  }
  return {
    render(state, immediate) {
      const { width, height } = size(container); svg.attr("viewBox", `0 0 ${width} ${height}`);
      const t = immediate ? 0 : DUR();
      ch.set(state.title ?? spec.title, state.subtitle ?? spec.subtitle);
      const rows = where(base, state.where ?? spec.where);
      const facets = spec.facet ? (spec.facets || [...new Set(rows.map((r) => r[spec.facet]))]) : [null];
      const panels = facets.map((fv) => ({ facet: fv, series: seriesFor(fv == null ? rows : rows.filter((r) => r[spec.facet] === fv)) }));
      const keys = state.series || spec.seriesOrder || [...new Set(panels.flatMap((p) => p.series.map((s) => s.key)))];
      const keyIdx = (k) => (spec.seriesOrder || keys).indexOf(k);
      const hi = state.highlight ? new Set(state.highlight) : null;
      const cols = facets.length > 1 ? 2 : 1, rowsN = Math.ceil(facets.length / cols);
      const narrow = width < 640; const top = 78, gapX = narrow ? 24 : 44, gapY = 56, padR = facets.length > 1 ? 8 : narrow ? 60 : 130;
      const pw = (width - gapX * (cols - 1) - 40) / cols, ph = (height - top - gapY * (rowsN - 1) - 20) / rowsN;
      const M = { l: narrow ? 36 : 48, r: padR, t: facets.length > 1 ? 26 : 10, b: 24 };
      const allPts = panels.flatMap((p) => p.series.filter((s) => keys.includes(s.key)).flatMap((s) => s.rows));
      const x = d3.scaleLinear().domain(d3.extent(allPts, (d) => d.x)).range([M.l, pw - M.r]);
      const yShared = spec.yShared !== false;
      const yFor = (pts) => d3.scaleLinear().domain(state.yDomain || spec.yDomain || [Math.min(0, d3.min(pts, (d) => d.v)), d3.max(pts, (d) => d.v)]).nice().range([ph - M.b, M.t]);
      let y = yFor(allPts);
      let line = d3.line().x((d) => x(d.x)).y((d) => y(d.v)).curve(d3.curveMonotoneX);
      const P = gPanels.selectAll("g.panel").data(panels, (d) => d.facet);
      const pe = P.enter().append("g").attr("class", "panel");
      pe.append("rect").attr("class", "bg").attr("fill", "transparent"); pe.append("text").attr("class", "label strong ptitle").attr("x", M.l).attr("y", 14);
      pe.append("g").attr("class", "axis x"); pe.append("g").attr("class", "axis y"); pe.append("g").attr("class", "lines"); pe.append("g").attr("class", "direct-labels"); pe.append("g").attr("class", "annot"); pe.append("line").attr("class", "crosshair").attr("opacity", 0);
      const pm = pe.merge(P);
      pm.attr("transform", (d, i) => `translate(${20 + (i % cols) * (pw + gapX)},${top + Math.floor(i / cols) * (ph + gapY)})`);
      pm.select("rect.bg").attr("width", pw).attr("height", ph); pm.select("text.ptitle").text((d) => (d.facet == null ? "" : labelFor(spec, d.facet)));
      pm.select("g.axis.x").attr("transform", `translate(0,${ph - M.b})`).call(d3.axisBottom(x).ticks(narrow ? (facets.length > 1 ? 2 : 4) : facets.length > 1 ? 4 : 6).tickFormat(fx).tickSize(0).tickPadding(6));
      pm.transition().duration(t).attr("opacity", (d) => (state.focus && d.facet !== state.focus ? 0.3 : 1));
      pm.each(function (p) {
        const ser = p.series.filter((s) => keys.includes(s.key));
        if (!yShared) { y = yFor(ser.flatMap((s) => s.rows)); line = d3.line().x((d) => x(d.x)).y((d) => y(d.v)).curve(d3.curveMonotoneX); }
        d3.select(this).select("g.axis.y").attr("transform", `translate(${M.l},0)`).call(d3.axisLeft(y).ticks(narrow ? 3 : 4).tickFormat((v) => (Math.abs(v) >= 1000 ? d3.format(",.0f")(v / 1000) + "k" : d3.format(",.1f")(v).replace(/\.0$/, ""))).tickSize(-(pw - M.l - M.r)).tickPadding(6));
        d3.select(this).select("g.axis.y").selectAll("line").attr("stroke", INK.grid);
        const ls = d3.select(this).select("g.lines").selectAll("path").data(ser, (d) => d.key);
        ls.enter().append("path").attr("fill", "none").attr("stroke-width", 2).attr("stroke-linejoin", "round").attr("stroke", (d) => colorFor(spec, d.key, keyIdx(d.key))).attr("d", (d) => line(d.rows))
          .attr("stroke-dasharray", function () { const L = this.getTotalLength(); return `${L} ${L}`; }).attr("stroke-dashoffset", function () { return this.getTotalLength(); })
          .transition().duration(immediate ? 0 : 1600).ease(d3.easeCubicOut).attr("stroke-dashoffset", 0).on("end", function () { d3.select(this).attr("stroke-dasharray", null); });
        ls.attr("stroke-dasharray", null).transition().duration(t).attr("d", (d) => line(d.rows)).attr("stroke-opacity", (d) => (hi && !hi.has(d.key) ? 0.35 : 1)).attr("stroke-width", (d) => (hi && hi.has(d.key) ? 3 : 2));
        ls.exit().remove();
        // end labels for single-panel
        const lbl = facets.length > 1 || state.endLabels === false ? [] : ser.map((s) => ({ key: s.key, lx: x(s.rows[s.rows.length - 1].x) + 8, ly: y(s.rows[s.rows.length - 1].v) + 4, v: s.rows[s.rows.length - 1].v })).sort((a, b) => a.ly - b.ly);
        for (let i = 1; i < lbl.length; i++) if (lbl[i].ly - lbl[i - 1].ly < 14) lbl[i].ly = lbl[i - 1].ly + 14;
        const dl = d3.select(this).select("g.direct-labels").selectAll("text").data(lbl, (d) => d.key);
        dl.enter().append("text").attr("class", "label strong").attr("opacity", 0).merge(dl).text((d) => (width < 640 ? f(d.v) : `${labelFor(spec, d.key)} ${f(d.v)}`)).transition().duration(t).attr("x", (d) => d.lx).attr("y", (d) => d.ly).attr("opacity", 1); dl.exit().remove();
        const anns = (state.annotations || []).filter((a) => a.facet == null || a.facet === p.facet).map((a) => { if (a.series) { const s = p.series.find((s) => s.key === a.series); const r = s && s.rows.find((r) => r.x === +a.x); return { ...a, y: r ? r.v : 0, dot: true, text: (a.text || "{value}").replace("{value}", r ? f(r.v) : "–") }; } return a; });
        drawAnnotations(d3.select(this).select("g.annot"), anns, x, y, t, { top: M.t, bottom: ph - M.b });
        const ch2 = d3.select(this).select("line.crosshair").attr("y1", M.t).attr("y2", ph - M.b);
        d3.select(this).select("rect.bg").on("mousemove", (ev) => { const [mx] = d3.pointer(ev); const xv = Math.round(x.invert(mx)); ch2.attr("x1", x(xv)).attr("x2", x(xv)).attr("opacity", 1);
          showTip(`<b>${p.facet != null ? labelFor(spec, p.facet) + ", " : ""}${fx(xv)}</b>` + rowsHtml(ser.map((s) => { const r = s.rows.find((r) => r.x === xv); return [labelFor(spec, s.key), r ? f(r.v) : "–", colorFor(spec, s.key, keyIdx(s.key))]; })), ev); }).on("mouseleave", () => { ch2.attr("opacity", 0); hideTip(); });
      });
      P.exit().remove();
      const legendRedundant = facets.length > 1 && spec.facet && (spec.series === spec.facet || keys.every((k) => facets.includes(k)));
      ch.legend(legendRedundant ? [] : keys.map((k) => [labelFor(spec, k), colorFor(spec, k, keyIdx(k))])); ch.legendLeft(20);
    }, resize() {}, progress() {},
  };
}
