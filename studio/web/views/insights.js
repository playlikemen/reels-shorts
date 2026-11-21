// Insights: per-reel Instagram metrics, top and bottom 5 per brand, weekly trend.
import { h, api, post, state, button, busy, jobToast, brandDot, short, ago } from "../app.js";

const ui = { brand: "" };

export async function render(root) {
  const body = h("div");
  const brand = h("select", { onchange: (e) => { ui.brand = e.target.value; load(); } }, h("option", { value: "" }, "All brands"),
    state.brands.map((b) => h("option", { value: b.key, selected: ui.brand === b.key }, b.name)));
  const sheet = h("input", { type: "checkbox" });
  const fetchBtn = button("Fetch now", (e) => busy(e.target, async () => {
    const keys = ui.brand ? [ui.brand] : state.brands.map((b) => b.key);
    for (const k of keys) { const r = await post("/api/insights/fetch", { brand: k, sheet: sheet.checked }); jobToast(r.job, `Insights ${k}`, load); }
  }), "primary");
  root.append(h("header.page", {}, h("h1", {}, "Insights"), brand, h("label.check", {}, sheet, h("span.small", {}, "also write the insights tab")), fetchBtn,
    h("div.sub", {}, "Shares per 1,000 views is the number to watch: it moves a reel to people who do not follow the account.")), body);
  async function load() {
    const d = await api(`/api/insights${ui.brand ? `?brand=${ui.brand}` : ""}`);
    if (!d.rows.length) { body.replaceChildren(h("div.empty", {}, h("h2", {}, "No insights yet"), h("p", {}, "Press Fetch now. It reads the latest reels of each Instagram account."))); return; }
    const tot = (k) => d.rows.reduce((a, r) => a + (r[k] || 0), 0);
    const views = tot("views");
    body.replaceChildren(
      h("div.stats", {}, [["Reels", d.rows.length], ["Views", views.toLocaleString()], ["Shares", tot("shares")], ["Shares / 1k", views ? (1000 * tot("shares") / views).toFixed(1) : "—"], ["Saves", tot("saves")]]
        .map(([k, v]) => h("div.panel.stat", {}, h("span.muted.small", {}, k), h("b", {}, v)))),
      h("div.panel", {}, h("h2", {}, "Views by week posted"), chart(d.weeks)),
      h("div.grid2", { style: { marginTop: "16px" } }, h("div.panel", {}, h("h2", {}, "Top 5"), tbl(d.top)), d.bottom.length ? h("div.panel", {}, h("h2", {}, "Bottom 5"), tbl(d.bottom)) : null),
      h("div.panel", {}, h("h2", {}, "Every reel"), tbl(d.rows)),
      h("p.small.muted", {}, "Fetched: ", Object.entries(d.fetched).map(([k, v]) => `${k} ${v ? ago(v) : "never"}`).join(" · ")));
  }
  await load();
}

function tbl(rows) {
  return h("div.tbl-wrap", {}, h("table.tbl", {}, h("thead", {}, h("tr", {}, ["Posted", "Reel", "Views", "Reach", "Shares", "/1k", "Saves", "Likes", "Watch"].map((t) => h("th", {}, t)))),
    h("tbody", {}, rows.map((r) => h("tr", { onclick: () => r.video_id ? (location.hash = `#/library/${r.video_id}`) : window.open(r.permalink, "_blank", "noopener") },
      h("td", {}, r.posted), h("td", {}, h("span.row", {}, brandDot(r.brand), r.video_id || short(r.caption, 40))),
      ...[r.views, r.reach, r.shares, r.views ? (1000 * r.shares / r.views).toFixed(1) : "—", r.saves, r.likes, `${r.avg_watch}s`].map((v) => h("td.num-cell", {}, v)))))));
}

function chart(weeks) {
  const W = 640, H = 200, P = 28;
  const max = Math.max(1, ...weeks.map((w) => w.views));
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "Views per week");
  const el = (n, a, text) => { const e = document.createElementNS(ns, n); for (const [k, v] of Object.entries(a)) e.setAttribute(k, v); if (text != null) e.textContent = text; svg.append(e); return e; };
  for (let i = 0; i <= 4; i++) { const y = P + (H - 2 * P) * i / 4; el("line", { x1: P, x2: W - 6, y1: y, y2: y, class: "grid" }); el("text", { x: 2, y: y + 3 }, Math.round(max * (1 - i / 4)).toLocaleString()); }
  const bw = (W - P - 10) / Math.max(1, weeks.length);
  weeks.forEach((w, i) => {
    const bh = (H - 2 * P) * w.views / max, x = P + 4 + i * bw;
    el("rect", { x, y: H - P - bh, width: Math.max(4, bw - 8), height: bh, rx: 3, class: "bar" }).append(Object.assign(document.createElementNS(ns, "title"), { textContent: `${w.week}: ${w.views} views, ${w.shares} shares, ${w.reels} reels` }));
    el("text", { x: x + 2, y: H - P + 14 }, w.week.slice(5));
  });
  return h("div.chart", {}, svg);
}
