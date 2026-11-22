// Reels Studio: shell, router and shared helpers. Views live in /static/views/*.js and export render(root, ctx).

export const state = { csrf: null, brands: [], reels: null, user: null, channel: "" };

// Views pass optional parts as `cond ? el : null`; let append/replaceChildren skip those instead of printing "null".
for (const m of ["append", "replaceChildren", "prepend"]) {
  const orig = Element.prototype[m];
  Element.prototype[m] = function (...kids) { return orig.apply(this, kids.flat(Infinity).filter((k) => k != null && k !== false)); };
}

// ---------- DOM helpers (text is always set as text, never as HTML) ----------
export function h(tag, attrs = {}, ...kids) {
  const [head, ...cls] = tag.split(".");
  const [name, id] = head.split("#");
  const el = document.createElement(name || "div");
  if (id) el.id = id;
  if (cls.length) el.className = cls.join(" ");
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className += (el.className ? " " : "") + v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k === "dataset") Object.assign(el.dataset, v);
    else if (k in el && typeof v !== "string") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
export const $ = (s, r = document) => r.querySelector(s);
export function clear(el) { while (el.firstChild) el.firstChild.remove(); return el; }

// ---------- API ----------
export class ApiError extends Error {
  constructor(msg, status, data) { super(msg); this.status = status; this.data = data; }
}
export async function api(path, opts = {}) {
  const o = { method: opts.method || "GET", headers: { accept: "application/json" }, credentials: "same-origin" };
  if (opts.body !== undefined) { o.body = JSON.stringify(opts.body); o.headers["content-type"] = "application/json"; }
  if (o.method !== "GET") o.headers["x-csrf-token"] = state.csrf || "";
  const r = await fetch(path, o);
  if (r.status === 401) { location.href = "/login"; throw new ApiError("login required", 401, {}); }
  let data = {};
  try { data = await r.json(); } catch { /* empty */ }
  if (!r.ok && !opts.allow?.includes(r.status)) throw new ApiError(data.error || `HTTP ${r.status}`, r.status, data);
  data._status = r.status;
  return data;
}
export const post = (path, body, opts = {}) => api(path, { method: "POST", body: body || {}, ...opts });

// ---------- formatting ----------
export const HEAD = {
  id: "Video ID", date: "Date", topic: "Category / Topic", format: "Format", duration: "Duration", path: "Local Path",
  drive: "Google Drive Folder", mp4: "Direct MP4 Download Link", ytTitle: "YouTube Title", ytTags: "YouTube SEO Tags (Separated)",
  ytDesc: "YouTube Best SEO Description", caption: "Instagram Viral Caption", hashtags: "Instagram Hashtags",
  ig: "Instagram Status", igUrl: "Instagram Post URL", yt: "YouTube Status", ytUrl: "YouTube Shorts URL", when: "Scheduled Time (IST)",
};
export function statusKind(s) {
  s = (s || "").toLowerCase();
  if (s === "ready") return "ready";
  if (s.startsWith("published")) return "published";
  if (s.startsWith("failed") || s.startsWith("manual")) return "failed";
  if (s === "publishing") return "busy";
  if (s.startsWith("hold")) return "hold";
  if (s === "archived") return "archived";
  return "muted";
}
export function pill(s, label) {
  return h("span.pill." + statusKind(s), { title: s || "" }, label ? `${label} ` : "", h("b", {}, short(s || "—", 18)));
}
export const short = (s, n = 60) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s || "");
export function brandOf(key) { return state.brands.find((b) => b.key === key) || { name: key, key }; }
export function brandDot(key) { return h("span.bdot", { dataset: { brand: key || "" } }); }
export function fmtBytes(n) {
  if (n == null) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i ? 1 : 0)} ${u[i]}`;
}
export function fmtWhen(s) {
  if (!s) return "—";
  const d = new Date(s.replace(" ", "T") + (s.length === 16 ? ":00+05:30" : ""));
  if (isNaN(d)) return s;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" });
}
export function ago(iso) {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400 * 2) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}
export function istNow() {
  const p = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false })
    .formatToParts(new Date()).reduce((a, x) => ((a[x.type] = x.value), a), {});
  return `${p.year}-${p.month}-${p.day} ${p.hour === "24" ? "00" : p.hour}:${p.minute}`;
}

// ---------- UI pieces ----------
export function toast(msg, kind = "info", ms = 4200) {
  const t = h("div.toast." + kind, { role: "status" }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.classList.add("out"), ms);
  setTimeout(() => t.remove(), ms + 400);
}
// Static files are served under a versioned path (/static/v<ver>/), so resolve them next to this module.
const ICONS = new URL("./icons.svg", import.meta.url).pathname;
export function icon(name) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("class", "ic"); s.setAttribute("aria-hidden", "true");
  const u = document.createElementNS("http://www.w3.org/2000/svg", "use");
  u.setAttribute("href", `${ICONS}#${name}`);
  s.append(u);
  return s;
}
export function button(label, onclick, cls = "", attrs = {}) {
  return h("button.btn" + (cls ? "." + cls.split(" ").join(".") : ""), { type: "button", onclick, ...attrs }, label);
}
export async function busy(btn, fn) {
  const old = btn.textContent; btn.disabled = true; btn.classList.add("loading");
  try { return await fn(); } catch (e) { toast(e.message, "error", 7000); throw e; } finally { btn.disabled = false; btn.classList.remove("loading"); btn.textContent = old; }
}

export function modal(title, body, actions = []) {
  const dlg = h("dialog.modal", {},
    h("form.modal-box", { method: "dialog" },
      h("header", {}, h("h2", {}, title), h("button.icon-btn", { value: "x", "aria-label": "Close" }, "×")),
      h("div.modal-body", {}, body),
      actions.length ? h("footer", {}, actions) : null));
  document.body.append(dlg);
  dlg.addEventListener("close", () => dlg.remove());
  dlg.showModal();
  return dlg;
}

export function drawer(title, content) {
  closeDrawer();
  const d = h("aside.drawer", { role: "dialog", "aria-label": title },
    h("header", {}, h("h2", {}, title), h("button.icon-btn", { onclick: closeDrawer, "aria-label": "Close" }, "×")),
    h("div.drawer-body", {}, content));
  const back = h("div.scrim", { onclick: closeDrawer });
  document.body.append(back, d);
  requestAnimationFrame(() => { d.classList.add("in"); back.classList.add("in"); });
  return d;
}
export function closeDrawer() { document.querySelectorAll(".drawer,.scrim").forEach((e) => e.remove()); }

// Live job log in an element, over SSE. Calls onEnd(status) when the job finishes.
export function followJob(jid, pre, onEnd) {
  const es = new EventSource(`/api/jobs/${jid}/stream`);
  es.addEventListener("log", (e) => {
    const atEnd = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
    pre.textContent += JSON.parse(e.data);
    if (atEnd) pre.scrollTop = pre.scrollHeight;
  });
  es.addEventListener("end", (e) => { es.close(); onEnd && onEnd(JSON.parse(e.data)); });
  es.onerror = () => { /* the browser retries; the server ends the stream when the job is over */ };
  return es;
}
export function jobToast(jid, label, after) {
  toast(`${label}: job #${jid} queued`, "info");
  const es = new EventSource(`/api/jobs/${jid}/stream`);
  es.addEventListener("end", (e) => {
    es.close();
    const s = JSON.parse(e.data);
    toast(`${label}: ${s.status}`, s.status === "done" ? "ok" : "error", 6000);
    after && after(s);
  });
}

export async function loadReels(force = false) {
  if (!state.reels || force) state.reels = await api("/api/reels");
  return state.reels;
}

// ---------- channel switcher (one pill per brand; filters every page; kept in the URL as ?ch= and in localStorage) ----------
export function hashParts() {
  const raw = (location.hash || "#/library").slice(1);
  const [path, query = ""] = raw.split("?");
  return { parts: path.split("/").filter(Boolean), query: new URLSearchParams(query) };
}
export function setChannel(key) {
  state.channel = state.brands.some((b) => b.key === key) ? key : "";
  try { localStorage.setItem("rs-ch", state.channel); } catch { /* private mode */ }
  const { parts, query } = hashParts();
  if (state.channel) query.set("ch", state.channel); else query.delete("ch");
  const q = query.toString();
  const next = `#/${(parts.length ? parts : ["library"]).join("/")}${q ? "?" + q : ""}`;
  if (location.hash !== next) location.hash = next; else route();
}
export function hrefWithCh(path) { return state.channel ? `${path}?ch=${state.channel}` : path; }
function revealActiveChip() {
  const on = document.querySelector("#chbar .chip.on"), row = document.querySelector("#chbar .chips");
  if (on && row) row.scrollLeft = Math.max(0, on.offsetLeft - row.offsetLeft - 24);
}
export async function reloadBrands() { state.brands = (await api("/api/brands")).brands; drawChannels(); }

function avatar(b) { return h("span.avatar", { dataset: { brand: b.key }, "aria-hidden": "true" }, (b.name || "?").slice(0, 1)); }

export function drawChannels() {
  const bar = $("#chbar");
  if (!bar) return;
  const cur = state.brands.find((b) => b.key === state.channel);
  const off = state.brands.filter((b) => b.auto_publish === false && (!cur || cur.key === b.key));
  const pills = [h("button.chip", { type: "button", class: !state.channel ? "on" : "", "aria-pressed": String(!state.channel), title: "All channels (0)", onclick: () => setChannel("") }, "All")]
    .concat(state.brands.map((b, i) => h("button.chip", {
      type: "button", class: state.channel === b.key ? "on" : "", "aria-pressed": String(state.channel === b.key),
      title: `${b.name} ${b.instagram} (${i + 1}) · auto-publish ${b.auto_publish === false ? "off" : "on"}`, onclick: () => setChannel(b.key),
    }, avatar(b), h("span.handle", {}, b.instagram || b.name), h("span.apdot", { class: b.auto_publish === false ? "off" : "", "aria-label": b.auto_publish === false ? "auto-publish off" : "auto-publish on" }))));
  bar.replaceChildren(
    h("div.chips", { role: "toolbar", "aria-label": "Channel" }, pills),
    h("div.chtools", {},
      off.map((b) => h("a.chip.bad", { href: "#/settings", title: "Cron posts nothing for this channel until it is switched on" }, `Auto-publish OFF${cur ? "" : ` · ${b.name}`}`)),
      cur ? [cur.instagram_url && h("a.btn.ghost.sm", { href: cur.instagram_url, target: "_blank", rel: "noopener" }, "Instagram ↗"),
        cur.youtube_url && h("a.btn.ghost.sm", { href: cur.youtube_url, target: "_blank", rel: "noopener" }, "YouTube ↗"),
        h("a.btn.ghost.sm", { href: "#/settings", title: "Channel settings", "aria-label": "Channel settings" }, icon("gear"))] : null));
  requestAnimationFrame(revealActiveChip);
}

// ---------- shell and router ----------
const NAV = [
  ["library", "Library", "grid"], ["calendar", "Calendar", "cal"], ["board", "Board", "board"], ["jobs", "Jobs", "play"],
  ["scripts", "Scripts", "pen"], ["insights", "Insights", "chart"], ["comments", "Comments", "chat"],
  ["files", "Files", "stack"], ["health", "Health", "pulse"], ["sound", "Sound", "wave"], ["audit", "Audit log", "list"], ["settings", "Settings", "gear"],
];
const MOBILE = ["library", "calendar", "board", "jobs"];

function shell() {
  const nav = h("nav.side", { "aria-label": "Main" },
    h("a.logo", { href: "#/library" }, h("span.mark", {}, "R"), h("span", {}, "Reels Studio")),
    NAV.map(([k, label, ic]) => h("a.nav", { href: `#/${k}`, dataset: { view: k } }, icon(ic), h("span", {}, label))),
    h("a.nav", { href: "/editor/", target: "_blank", rel: "noopener" }, icon("film"), h("span", {}, "Editor ↗")),
    h("div.side-foot", {},
      h("button.btn.ghost.sm", { type: "button", onclick: toggleTheme, title: "Light or dark" }, icon("moon"), "Theme"),
      h("button.btn.ghost.sm", { type: "button", onclick: logout }, "Log out")));
  const tabs = h("nav.tabs", { "aria-label": "Main (mobile)" },
    MOBILE.map((k) => { const n = NAV.find((x) => x[0] === k); return h("a", { href: `#/${k}`, dataset: { view: k } }, icon(n[2]), h("span", {}, n[1])); }),
    h("a", { href: "#/more", dataset: { view: "more" } }, icon("dots"), h("span", {}, "More")));
  document.body.append(nav, h("div#chbar"), h("main#view", { tabindex: "-1" }), tabs, h("div#toasts", { "aria-live": "polite" }));
}

function toggleTheme() {
  const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("rs-theme", next); } catch { /* private mode */ }
}
async function logout() { await post("/api/logout"); location.href = "/login"; }

const cache = {};
async function route() {
  const { parts, query } = hashParts();
  const [view = "library", ...rest] = parts;
  const ch = query.get("ch");
  if (ch !== null && ch !== state.channel && state.brands.some((b) => b.key === ch)) {
    state.channel = ch;
    try { localStorage.setItem("rs-ch", ch); } catch { /* */ }
  }
  drawChannels();
  document.querySelectorAll("[data-view]").forEach((a) => a.classList.toggle("on", a.dataset.view === view));
  closeDrawer();
  const root = clear($("#view"));
  if (view === "more") return renderMore(root);
  const known = NAV.some((n) => n[0] === view);
  try {
    const mod = cache[view] || (cache[view] = await import(new URL(`./views/${known ? view : "library"}.js`, import.meta.url).href));
    await mod.render(root, { params: rest.map(decodeURIComponent), query, channel: state.channel });
  } catch (e) {
    console.error(e);
    root.append(h("div.empty", {}, h("h2", {}, "Something went wrong"), h("p", {}, e.message)));
  }
  root.focus({ preventScroll: true });
}

function renderMore(root) {
  root.append(h("header.page", {}, h("h1", {}, "More")),
    h("div.more-grid", {}, NAV.filter((n) => !MOBILE.includes(n[0])).map(([k, l, ic]) => h("a.card.more", { href: `#/${k}` }, icon(ic), l)),
      h("a.card.more", { href: "/editor/", target: "_blank" }, icon("film"), "Editor ↗"),
      h("button.card.more", { type: "button", onclick: toggleTheme }, icon("moon"), "Theme"),
      h("button.card.more", { type: "button", onclick: logout }, icon("gear"), "Log out")));
}

async function boot() {
  try { const t = localStorage.getItem("rs-theme"); if (t) document.documentElement.dataset.theme = t; } catch { /* */ }
  const s = await api("/api/session");
  state.csrf = s.csrf; state.user = s.user;
  state.brands = (await api("/api/brands")).brands;
  try { const c = localStorage.getItem("rs-ch"); if (c && state.brands.some((b) => b.key === c)) state.channel = c; } catch { /* */ }
  shell();
  addEventListener("hashchange", route);
  addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;
    if (typing || e.ctrlKey || e.metaKey || e.altKey || document.querySelector("dialog[open]")) return;
    if (e.key === "0") setChannel("");
    else if (/^[1-9]$/.test(e.key) && state.brands[+e.key - 1]) setChannel(state.brands[+e.key - 1].key);
  });
  route();
}
boot();
