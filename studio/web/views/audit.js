// Audit log: every edit, publish, render and login, with before and after values.
import { h, api, short } from "../app.js";

export async function render(root) {
  const { audit } = await api("/api/audit?limit=500");
  const q = h("input", { type: "search", placeholder: "Filter…", oninput: () => draw() });
  const body = h("div");
  root.append(h("header.page", {}, h("h1", {}, "Audit log"), q), body);
  const fmt = (s) => { if (!s) return ""; try { const v = JSON.parse(s); return typeof v === "object" ? Object.entries(v).map(([k, x]) => `${k}: ${typeof x === "string" ? x : JSON.stringify(x)}`).join("\n") : String(v); } catch { return s; } };
  const draw = () => {
    const f = q.value.toLowerCase();
    const rows = audit.filter((a) => !f || JSON.stringify(a).toLowerCase().includes(f));
    body.replaceChildren(h("div.tbl-wrap", {}, h("table.tbl", {}, h("thead", {}, h("tr", {}, ["When", "Who", "Action", "Target", "Before", "After"].map((t) => h("th", {}, t)))),
      h("tbody", {}, rows.map((a) => h("tr", { style: { cursor: "default" } }, h("td.small", {}, a.at.slice(0, 16).replace("T", " ")), h("td.small", {}, a.who, a.ip ? h("div.muted", {}, a.ip) : null),
        h("td", {}, h("b", {}, a.action)), h("td", {}, a.target), h("td.small", { style: { whiteSpace: "pre-wrap" } }, short(fmt(a.before), 400)), h("td.small", { style: { whiteSpace: "pre-wrap" } }, short(fmt(a.after), 400))))))));
  };
  draw();
}
