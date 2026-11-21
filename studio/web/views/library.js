// Library: folders (Queue, Due/Failed, Drafts, Published, Archive, All) on a left rail, a sticky toolbar, cards with a
// hover preview and one-click publish, a Queue timeline with drag-to-swap, bulk actions and the Upload modal.
// Folders come from the server (sync.folder_of), so the Sheet stays the source of truth.
import { h, api, post, state, loadReels, pill, brandDot, brandOf, fmtWhen, short, button, busy, toast, icon, jobToast, modal, istNow } from "../app.js";
import { openReel } from "./reel.js";
import { publishButton, canPublish, scheduleDialog, archiveReel, holdReel, undoToast } from "./publish.js";

const FOLDERS = [
  ["queue", "Queue", "clock", "Ready, scheduled in the future"],
  ["due", "Due / Failed", "alert", "Ready and overdue, failed or waiting for a manual upload"],
  ["drafts", "Drafts", "draft", "On hold, or rendered but not in the Sheet yet"],
  ["published", "Published", "check", "Posted on Instagram"],
  ["archive", "Archive", "archive", "Hidden from the queue; nothing is deleted"],
  ["all", "All", "stack", "Every reel"],
];
const EMPTY = {
  queue: ["Nothing queued", "Schedule a draft or upload a reel; it shows up here in slot order."],
  due: ["Nothing overdue or failed", "Every Ready reel is on time."],
  drafts: ["No drafts", "Held reels and fresh renders land here."],
  published: ["Nothing published yet", "Posted reels move here with their Instagram link."],
  archive: ["Archive is empty", "Archived reels keep their row, files and Drive folder."],
  all: ["No reels", "Sync from the Sheet or upload a reel."],
};
const ui = { folder: "queue", view: "grid", sort: "slot", q: "", sel: new Set(), last: null };
try { Object.assign(ui, JSON.parse(localStorage.getItem("rs-lib2") || "{}"), { sel: new Set(), last: null, q: "" }); } catch { /* */ }
const remember = () => { try { localStorage.setItem("rs-lib2", JSON.stringify({ folder: ui.folder, view: ui.view, sort: ui.sort })); } catch { /* */ } };

let root$, data$, body$, rail$, keyHandler;

export async function render(root, ctx) {
  root$ = root;
  const f = ctx.query?.get("f");
  if (f && FOLDERS.some((x) => x[0] === f)) ui.folder = f;
  data$ = await loadReels(true);
  const head = h("header.page", {}, h("h1", {}, "Library"),
    h("span.muted.small.lib-head-meta", {}, `${data$.count} reels · synced ${data$.last_pull ? new Date(data$.last_pull.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "never"}`),
    button([icon("refresh"), "Sync"], (e) => busy(e.target, async () => { const r = await post("/api/sync", {}); jobToast(r.job, "Sync", () => refresh()); }), "ghost sm", { title: "Pull every tab from the Sheet" }),
    button([icon("upload"), "Upload"], () => uploadModal(), "primary"));
  rail$ = h("nav.rail", { "aria-label": "Folders" });
  body$ = h("div.lib-main");
  root.append(head, banners(data$), h("div.lib", {}, rail$, body$));
  draw();
  if (ctx.params[0]) openReel(ctx.params[0], refresh);
  if (keyHandler) removeEventListener("keydown", keyHandler);
  keyHandler = (e) => {
    if (!document.body.contains(body$)) return removeEventListener("keydown", keyHandler);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a" && !/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) && !document.querySelector("dialog[open],.drawer")) {
      e.preventDefault();
      visible().forEach((r) => ui.sel.add(r["Video ID"]));
      draw();
    }
  };
  addEventListener("keydown", keyHandler);
}

async function refresh() {
  data$ = await loadReels(true);
  if (document.body.contains(body$)) draw();
}

// ---------- data ----------

function inChannel(r) { return !state.channel || r.brand === state.channel; }

function allRows() {
  const rows = data$.reels.filter(inChannel);
  const uns = (data$.unsynced || []).filter(inChannel).map((u) => ({ ...u, folder: "drafts", unsynced: true, "Instagram Status": "Not in Sheet", "Category / Topic": u.spec_path || u.local_path }));
  return rows.concat(uns);
}

function counts() {
  const c = Object.fromEntries(FOLDERS.map(([k]) => [k, 0]));
  for (const r of allRows()) { c[r.folder] = (c[r.folder] || 0) + 1; c.all++; }
  return c;
}

function matchesQ(r) {
  if (!ui.q) return true;
  const hay = JSON.stringify(r).toLowerCase();
  return ui.q.toLowerCase().split(/\s+/).filter(Boolean).every((w) => hay.includes(w));
}

function sorted(list) {
  const t = (r) => r["Scheduled Time (IST)"] || "";
  const by = {
    slot: (a, b) => (ui.folder === "published" || ui.folder === "archive" ? t(b).localeCompare(t(a)) : t(a).localeCompare(t(b))) || a["Video ID"].localeCompare(b["Video ID"]),
    newest: (a, b) => (b.updated_at || b.mtime || "").localeCompare(a.updated_at || a.mtime || "") || b["Video ID"].localeCompare(a["Video ID"]),
    topic: (a, b) => (a["Category / Topic"] || "").localeCompare(b["Category / Topic"] || ""),
  }[ui.sort] || (() => 0);
  return list.slice().sort(by);
}

function visible() {
  return sorted(allRows().filter((r) => (ui.folder === "all" || r.folder === ui.folder) && matchesQ(r)));
}

// ---------- layout ----------

function draw() {
  const c = counts();
  rail$.replaceChildren(...FOLDERS.map(([k, label, ic, tip]) => h("button.folder", {
    type: "button", class: ui.folder === k ? "on" : "", "aria-current": ui.folder === k ? "true" : null, title: tip,
    onclick: () => { ui.folder = k; ui.sel.clear(); if (k !== "queue" && ui.view === "timeline") ui.view = "grid"; remember(); draw(); },
  }, icon(ic), h("span.lbl", {}, label), h("span.count", { class: k === "due" && c[k] ? "bad" : "" }, String(c[k] || 0)))));
  const list = visible();
  const views = [["grid", "Grid"], ["list", "List"]].concat(ui.folder === "queue" ? [["timeline", "Timeline"]] : []);
  if (!views.some((v) => v[0] === ui.view)) ui.view = "grid";
  const q = h("input", { type: "search", placeholder: "Search caption, topic, id…", value: ui.q, "aria-label": "Search",
    oninput: (e) => { ui.q = e.target.value; drawContent(content); } });
  const sort = h("select", { "aria-label": "Sort", onchange: (e) => { ui.sort = e.target.value; remember(); drawContent(content); } },
    [["slot", "By slot"], ["newest", "Newest"], ["topic", "Topic"]].map(([v, l]) => h("option", { value: v, selected: ui.sort === v }, l)));
  const seg = h("div.seg", { role: "group", "aria-label": "View" }, views.map(([v, l]) => h("button", {
    type: "button", class: ui.view === v ? "on" : "", "aria-pressed": String(ui.view === v), onclick: () => { ui.view = v; remember(); draw(); },
  }, l)));
  const toolbar = h("div.toolbar", {}, h("div.search", {}, icon("search"), q), sort, seg);
  const content = h("div.lib-content");
  body$.replaceChildren(toolbar, content, bulkBar());
  drawContent(content, list);
}

function drawContent(content, list) {
  list = list || visible();
  if (!list.length) {
    const [t, p] = ui.q ? ["No reels match", "Try another search."] : EMPTY[ui.folder];
    content.replaceChildren(h("div.empty", {}, h("h2", {}, t), h("p", {}, p),
      ui.folder === "drafts" || ui.folder === "queue" || ui.folder === "all" ? button([icon("upload"), "Upload a reel"], () => uploadModal(), "sm") : null));
    return;
  }
  content.replaceChildren(ui.view === "list" ? table(list) : ui.view === "timeline" ? timeline(list) : grid(list));
}

function banners(data) {
  const out = h("div");
  const missing = data.reels.filter((r) => r.missing), pending = data.reels.filter((r) => Object.keys(r.pending || {}).length);
  const errs = Object.entries(data.last_pull?.summary || {}).filter(([, s]) => s.error);
  if (missing.length) out.append(h("div.banner.bad", {}, h("div", {}, h("b", {}, `${missing.length} row(s) missing in the Sheet: `), missing.map((r) => r["Video ID"]).join(", "), ". Kept locally; open one to restore it.")));
  if (pending.length) out.append(h("div.banner.warn", {}, h("div", {}, h("b", {}, `${pending.length} edit(s) pending sync: `), pending.map((r) => r["Video ID"]).join(", "), ". Retried on the next sync.")));
  for (const [tab, s] of errs) out.append(h("div.banner.warn", {}, `Last sync could not read ${tab}: ${short(s.error, 160)}`));
  return out;
}

// ---------- selection ----------

function toggleSel(vid, e) {
  const list = visible().map((r) => r["Video ID"]);
  if (e.shiftKey && ui.last && list.includes(ui.last)) {
    const [a, b] = [list.indexOf(ui.last), list.indexOf(vid)].sort((x, y) => x - y);
    const on = !ui.sel.has(vid);
    list.slice(a, b + 1).forEach((v) => (on ? ui.sel.add(v) : ui.sel.delete(v)));
  } else if (ui.sel.has(vid)) ui.sel.delete(vid);
  else ui.sel.add(vid);
  ui.last = vid;
  draw();
}

function selBox(r) {
  if (r.unsynced) return null;
  return h("input.sel", { type: "checkbox", checked: ui.sel.has(r["Video ID"]), "aria-label": `Select ${r["Video ID"]}`,
    onclick: (e) => { e.stopPropagation(); e.preventDefault(); toggleSel(r["Video ID"], e); } });
}

// ---------- cards ----------

const lang = (vid) => (vid.match(/-([A-Z]{2})$/) || [])[1] || "";

function countdown(t) {
  if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(t || "")) return "";
  const ms = new Date(t.replace(" ", "T") + ":00+05:30").getTime() - Date.now();
  const m = Math.round(Math.abs(ms) / 60000);
  const s = m < 60 ? `${m} min` : m < 48 * 60 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} d`;
  return ms >= 0 ? `in ${s}` : `${s} ago`;
}

function mediaUrl(r) {
  const p = r["Local Path"] || r.local_path;
  return p ? `/media/${p.replace(/^out\//, "")}` : "";
}

function preview(thumb, r) {
  const src = mediaUrl(r);
  if (!src) return;
  let v = null, t = null;
  const start = () => {
    if (v || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    v = h("video.pv", { src, muted: true, playsInline: true, loop: true, preload: "auto", "aria-hidden": "true" });
    v.muted = true;
    thumb.append(v);
    v.play().catch(() => {});
  };
  const stop = () => { clearTimeout(t); if (v) { v.pause(); v.remove(); v = null; } };
  thumb.addEventListener("mouseenter", () => { t = setTimeout(start, 250); });
  thumb.addEventListener("mouseleave", stop);
  thumb.addEventListener("touchstart", () => { t = setTimeout(start, 450); }, { passive: true });
  thumb.addEventListener("touchend", () => clearTimeout(t));
  thumb.addEventListener("touchmove", stop, { passive: true });
}

function quick(r) {
  if (r.unsynced) return [h("button.btn.sm", { type: "button", onclick: (e) => { e.stopPropagation(); syncRender(r); } }, "Add to Sheet")];
  const out = [];
  const pub = (r["Instagram Status"] || "").startsWith("Published");
  const arch = r.folder === "archive";
  if (!pub && !(arch && r["Instagram Post URL"])) out.push(qa("clock", "Schedule", () => scheduleDialog(r, refresh)));
  const ig = r["Instagram Status"] || "";
  if (ig === "Ready") out.push(qa("pause", "Hold", () => optimistic(r, "drafts", () => holdReel(r, true, refresh))));
  else if (ig.startsWith("Hold")) out.push(qa("play", "Unhold (Ready)", () => optimistic(r, "queue", () => holdReel(r, false, refresh))));
  out.push(qa("archive", arch ? "Unarchive" : "Archive", () => optimistic(r, arch ? "drafts" : "archive", () => archiveReel(r, !arch, refresh))));
  if (r["Instagram Post URL"]) out.push(h("a.qa", { href: r["Instagram Post URL"], target: "_blank", rel: "noopener", title: "Open on Instagram", "aria-label": "Open on Instagram", onclick: (e) => e.stopPropagation() }, icon("ext")));
  return out;
}

function qa(ic, label, fn) {
  return h("button.qa", { type: "button", title: label, "aria-label": label, onclick: async (e) => {
    e.stopPropagation();
    const b = e.currentTarget; b.disabled = true;
    try { await fn(); } catch (x) { toast(x.message, "error", 7000); } finally { b.disabled = false; }
  } }, icon(ic));
}

// Move the card at once, then let the server answer; on an error the reload puts it back.
async function optimistic(r, folder, fn) {
  const row = data$.reels.find((x) => x["Video ID"] === r["Video ID"]);
  const old = row?.folder;
  if (row) { row.folder = folder; draw(); }
  try { await fn(); } catch (e) { if (row) row.folder = old; toast(e.message, "error", 7000); }
  await refresh();
}

function card(r) {
  const b = brandOf(r.brand);
  const vid = r["Video ID"];
  const thumb = h("div.thumb", {}, h("img", { src: r.unsynced && !r.thumb ? "/static/no-thumb.svg" : `/thumb/${vid}.jpg`, loading: "lazy", alt: "" }), selBox(r),
    lang(vid) ? h("span.lang", {}, lang(vid)) : null,
    r.Duration ? h("span.dur", {}, r.Duration) : null,
    r.missing ? h("span.flag.pill.failed", {}, "missing in sheet") : Object.keys(r.pending || {}).length ? h("span.flag.pill.warn", {}, "pending sync") : null,
    h("div.qas", {}, quick(r)));
  preview(thumb, r);
  const when = r["Scheduled Time (IST)"];
  const open = () => (r.unsynced ? syncRender(r) : openReel(vid, refresh));
  const el = h("article.card.reel", {
    tabindex: 0, class: ui.sel.has(vid) ? "picked" : "", dataset: { vid },
    onclick: open, onkeydown: (e) => { if (e.key === "Enter" && e.target === el) open(); },
  }, thumb,
    h("div.meta", {},
      h("div.id", {}, brandDot(r.brand), h("span", {}, vid), r.folder === "queue" && when ? h("span.cd", {}, countdown(when)) : null),
      h("div.topic", {}, r["Category / Topic"]),
      h("div.pills", {}, pill(r["Instagram Status"], "IG"), b.youtube ? pill(r["YouTube Status"], "YT") : null),
      h("div.when", {}, when ? `${fmtWhen(when)} IST` : "no time set"),
      pubRow(r)));
  return el;
}

function pubRow(r) {
  if (r.unsynced) return null;
  const ig = canPublish(r, "instagram") ? publishButton(r, "instagram", { compact: true, onDone: refresh }) : null;
  const yt = canPublish(r, "youtube") ? publishButton(r, "youtube", { compact: true, onDone: refresh }) : null;
  return ig || yt ? h("div.pubrow", {}, ig, yt) : null;
}

function grid(list) {
  return h("div.reels", {}, list.map(card));
}

function table(list) {
  return h("div.tbl-wrap", {}, h("table.tbl", {},
    h("thead", {}, h("tr", {}, ["", "ID", "Topic", "IG", "YouTube", "Scheduled (IST)", "Publish", ""].map((t) => h("th", {}, t)))),
    h("tbody", {}, list.map((r) => {
      const b = brandOf(r.brand);
      return h("tr", { class: ui.sel.has(r["Video ID"]) ? "picked" : "", onclick: () => (r.unsynced ? syncRender(r) : openReel(r["Video ID"], refresh)) },
        h("td", {}, selBox(r)), h("td", {}, h("span.row.nowrap", {}, brandDot(r.brand), h("b", {}, r["Video ID"]))), h("td", {}, short(r["Category / Topic"], 64)),
        h("td", {}, pill(r["Instagram Status"])), h("td", {}, b.youtube ? pill(r["YouTube Status"]) : h("span.muted.small", {}, "—")),
        h("td.nowrap", {}, r["Scheduled Time (IST)"] || "—", r.folder === "queue" ? h("div.small.muted", {}, countdown(r["Scheduled Time (IST)"])) : null),
        h("td", { onclick: (e) => e.stopPropagation() }, pubRow(r)),
        h("td", { onclick: (e) => e.stopPropagation() }, h("div.qas.inline", {}, quick(r))));
    }))));
}

// ---------- queue timeline: one row per day, each channel slot as a lane; drag a reel onto another to swap ----------

function timeline(list) {
  const brands = state.channel ? [brandOf(state.channel)] : state.brands.filter((b) => list.some((r) => r.brand === b.key));
  const today = istNow().slice(0, 10);
  const last = list.reduce((m, r) => ((r["Scheduled Time (IST)"] || "") > m ? r["Scheduled Time (IST)"] : m), today).slice(0, 10);
  const byKey = {};
  for (const r of list) (byKey[`${r.brand}|${r["Scheduled Time (IST)"]}`] ||= []).push(r);
  const days = [];
  for (let d = today, i = 0; d <= last && i < 120; d = addDay(d), i++) days.push(d);
  return h("div.timeline", {}, days.map((d) => {
    const lanes = [];
    for (const b of brands) {
      const slots = new Set(b.slots?.length ? b.slots : ["19:30"]);
      list.filter((r) => r.brand === b.key && (r["Scheduled Time (IST)"] || "").startsWith(d)).forEach((r) => slots.add(r["Scheduled Time (IST)"].slice(11)));
      for (const s of [...slots].sort()) {
        const t = `${d} ${s}`;
        if (t <= istNow()) continue;
        const here = byKey[`${b.key}|${t}`] || [];
        lanes.push(h("div.slot", { class: here.length > 1 ? "clash" : here.length ? "" : "free", dataset: { brand: b.key, t } },
          h("div.slot-t", {}, s, state.channel ? null : brandDot(b.key)),
          here.length ? h("div.slot-items", {}, here.map((r) => slotItem(r))) : fillTarget(b, t),
          here.length > 1 ? h("span.pill.warn", {}, "double-booked") : null));
      }
    }
    const dt = new Date(d + "T12:00:00+05:30");
    return lanes.length ? h("section.day", {}, h("h3", {}, dt.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", timeZone: "Asia/Kolkata" }), d === today ? h("span.pill.ready", {}, "today") : null), h("div.slots", {}, lanes)) : null;
  }));
}

const addDay = (d) => { const x = new Date(d + "T00:00:00Z"); x.setUTCDate(x.getUTCDate() + 1); return x.toISOString().slice(0, 10); };

function slotItem(r) {
  const vid = r["Video ID"];
  const el = h("div.titem", {
    draggable: true, tabindex: 0, title: `${vid} · drag onto another reel to swap slots, or onto a free slot to move it`,
    onclick: () => openReel(vid, refresh), onkeydown: (e) => e.key === "Enter" && openReel(vid, refresh),
    ondragstart: (e) => { e.dataTransfer.setData("text/plain", vid); el.classList.add("dragging"); },
    ondragend: () => el.classList.remove("dragging"),
    ondragover: (e) => { e.preventDefault(); el.classList.add("over"); },
    ondragleave: () => el.classList.remove("over"),
    ondrop: (e) => { e.preventDefault(); el.classList.remove("over"); const from = e.dataTransfer.getData("text/plain"); if (from && from !== vid) swap(from, vid); },
  }, selBox(r), h("img", { src: `/thumb/${vid}.jpg`, alt: "", loading: "lazy" }),
    h("div.tmeta", {}, h("b", {}, vid, lang(vid) ? h("span.lang.inline", {}, lang(vid)) : null), h("span.small.muted", {}, short(r["Category / Topic"], 54))),
    h("div.tact", { onclick: (e) => e.stopPropagation() }, pubRow(r)));
  return el;
}

function fillTarget(b, t) {
  const el = h("button.fill", {
    type: "button", title: `Put a draft in ${t}`,
    onclick: () => fillDialog(b, t),
    ondragover: (e) => { e.preventDefault(); el.classList.add("over"); },
    ondragleave: () => el.classList.remove("over"),
    ondrop: async (e) => {
      e.preventDefault(); el.classList.remove("over");
      const vid = e.dataTransfer.getData("text/plain");
      const r = data$.reels.find((x) => x["Video ID"] === vid);
      if (!r) return;
      if (r.brand !== b.key) return toast(`${vid} belongs to ${brandOf(r.brand).name}; drop it on one of its own slots`, "error");
      await moveTo(r, t);
    },
  }, "+ fill");
  return el;
}

async function moveTo(r, t) {
  const old = r["Scheduled Time (IST)"];
  const res = await post(`/api/reels/${encodeURIComponent(r["Video ID"])}/schedule`, { when: t, auto: true }, { allow: [202, 409] });
  if (res._status === 409) return toast(res.error || "changed in the Sheet meanwhile", "error", 7000);
  await refresh();
  undoToast(`${r["Video ID"]} moved to ${fmtWhen(t)} IST`, () => post(`/api/reels/${encodeURIComponent(r["Video ID"])}/schedule`, { when: old, auto: true }).then(refresh));
}

async function swap(a, b) {
  try {
    const r = await post("/api/reels/bulk", { ids: [a, b], action: "swap" });
    jobToast(r.job, `Swap ${a} ↔ ${b}`, () => refresh());
  } catch (e) { toast(e.message, "error", 7000); }
}

function fillDialog(b, t) {
  const drafts = data$.reels.filter((r) => r.brand === b.key && (r.folder === "drafts" || r.folder === "due") && !(r["Instagram Status"] || "").startsWith("Publishing"));
  const dlg = modal(`Fill ${fmtWhen(t)} IST · ${b.name}`, [
    drafts.length ? h("div.picklist", {}, drafts.map((r) => h("button.pick", { type: "button", onclick: async (e) => { e.target.disabled = true; dlg.close(); await moveTo(r, t); } },
      h("img", { src: `/thumb/${r["Video ID"]}.jpg`, alt: "", loading: "lazy" }), h("span", {}, h("b", {}, r["Video ID"]), h("span.small.muted", {}, short(r["Category / Topic"], 60))), pill(r["Instagram Status"]))))
      : h("p.muted", {}, `No drafts for ${b.name}. Upload one or unarchive a reel.`),
    h("p.small.muted", {}, "The reel becomes Ready at that time and cron posts it."),
  ], [button("Close", () => dlg.close())]);
}

// ---------- bulk bar (sticky at the bottom) ----------

function bulkBar() {
  const ids = [...ui.sel].filter((v) => data$.reels.some((r) => r["Video ID"] === v));
  if (!ids.length) return null;
  const rows = ids.map((v) => data$.reels.find((r) => r["Video ID"] === v));
  const start = h("input", { value: nextDaySlot(), size: 16, "aria-label": "First slot" });
  const every = h("input", { type: "number", value: 1, min: 1, max: 14, style: { width: "56px" }, "aria-label": "Days apart" });
  const run = (action, extra = {}) => async (e) => busy(e.target, async () => {
    const r = await post("/api/reels/bulk", { ids, action, start: start.value, every_days: +every.value, ...extra });
    jobToast(r.job, `Bulk ${action}`, async () => { await refresh(); });
    ui.sel.clear(); draw();
  });
  const pushables = rows.filter((r) => canPublish(r, "instagram"));
  const archived = rows.filter((r) => r.folder === "archive");
  return h("div.bulkbar", { role: "region", "aria-label": "Bulk actions" },
    h("b", {}, `${ids.length} selected`),
    button("Hold", run("hold"), "sm"), button("Ready", run("ready"), "sm"),
    button("Fill next free slots", run("fill"), "sm", { title: "Each reel gets its channel's next free slot and becomes Ready" }),
    h("span.grp", {}, h("span.small", {}, "from"), start, h("span.small", {}, "every"), every, h("span.small", {}, "d"), button("Schedule", run("schedule"), "sm")),
    archived.length === rows.length ? button("Unarchive", run("unarchive"), "sm") : button("Archive", run("archive"), "sm"),
    pushables.length ? button(`Publish ${pushables.length} now`, () => bulkPublish(pushables), "sm danger") : null,
    h("span.spacer"),
    button("Clear", () => { ui.sel.clear(); draw(); }, "sm ghost"));
}

function bulkPublish(rows) {
  const ids = rows.map((r) => r["Video ID"]);
  const handles = [...new Set(rows.map((r) => brandOf(r.brand).instagram))].join(", ");
  const sure = h("input", { type: "checkbox" });
  const go = button(`Publish ${ids.length} now`, (e) => busy(e.target, async () => {
    const r = await post("/api/reels/bulk", { ids, action: "publish", platform: "instagram", confirm: true }, { allow: [409] });
    if (r._status === 409) throw new Error(r.error);
    dlg.close(); ui.sel.clear(); draw();
    jobToast(r.job, `Publish ${ids.length} reels`, () => refresh());
  }), "danger", { disabled: true });
  sure.addEventListener("change", () => { go.disabled = !sure.checked; });
  const dlg = modal(`Publish ${ids.length} reels now`, [
    h("p", {}, "They post one after another, through the same scheduler code and lock as cron. The daily cap is overridden."),
    h("div.preview", {}, ids.join("\n")),
    h("label.check", {}, sure, h("span", {}, `Post these publicly on ${handles} now.`)),
  ], [button("Cancel", () => dlg.close()), go]);
}

function nextDaySlot() {
  const b = state.channel ? brandOf(state.channel) : null;
  const d = new Date(Date.now() + 864e5 + 5.5 * 36e5);
  return d.toISOString().slice(0, 10) + " " + (b?.slots?.[0] || "19:30");
}

// ---------- unsynced render -> Sheet ----------

function syncRender(u) {
  if (!u.spec_path) return toast(`${u["Video ID"]} has no spec, so it can not be added from here`, "error");
  const dlg = modal(`Add ${u["Video ID"]} to the Sheet`, [h("p", {}, `Uploads ${u.local_path} to a new Drive folder and writes its Sheet row in ${u.tab} with status Ready, using the schedule from ${u.spec_path}. Cron then posts it when due.`)],
    [button("Cancel", () => dlg.close()), button("Upload and add row", async (e) => busy(e.target, async () => {
      const r = await post("/api/jobs", { kind: "sync", params: { spec: u.spec_path, lang: u.lang, id: u["Video ID"] } });
      dlg.close(); jobToast(r.job, `Sync ${u["Video ID"]}`, () => refresh());
    }), "primary")]);
}

// ---------- upload ----------

const MAX = 1024 ** 3;

function uploadModal() {
  let file = null;
  const brands = state.brands;
  const ch = h("select", { "aria-label": "Channel" }, brands.map((b) => h("option", { value: b.key, selected: (state.channel || "craftlayer") === b.key }, `${b.name} ${b.instagram}`)));
  const langSel = h("select", { "aria-label": "Language" }, [["EN", "English"], ["HI", "Hindi"], ["", "None"]].map(([v, l]) => h("option", { value: v }, l)));
  const topic = h("input", { placeholder: "What is it about?", maxlength: 200 });
  const caption = h("textarea", { rows: 5, placeholder: "Instagram caption", maxlength: 2200 });
  const tags = h("input", { placeholder: "#tag #tag" });
  const ytTitle = h("input", { maxlength: 100 }), ytDesc = h("textarea", { rows: 3 });
  const ytBox = h("div.ytbox", {}, h("label.field", {}, "YouTube title", ytTitle), h("label.field", {}, "YouTube description", ytDesc));
  const when = h("input", { type: "datetime-local", step: 60, "aria-label": "Schedule at (IST)" });
  const after = h("div.choice", { role: "radiogroup", "aria-label": "After upload" });
  const opts = [["draft", "Save as draft (Hold)"], ["next", "Next free slot"], ["schedule", "Schedule at…"], ["now", "Publish now"]];
  let mode = "draft";
  after.append(...opts.map(([v, l]) => h("label.check", {}, h("input", { type: "radio", name: "after", value: v, checked: v === mode, onchange: () => { mode = v; sync(); } }), h("span", {}, l))));
  const sure = h("input", { type: "checkbox" });
  const sureRow = h("label.check", {}, sure, h("span", {}, "Post it publicly as soon as it is processed."));
  const fileInfo = h("div.small.muted", {}, "MP4 or MOV, up to 1 GB, at most 90 seconds. It is checked and, if needed, re-encoded to 1080×1920 at −14 LUFS.");
  const input = h("input", { type: "file", accept: "video/mp4,video/quicktime,.mp4,.mov", hidden: true, onchange: (e) => pick(e.target.files[0]) });
  const drop = h("div.dropzone", { tabindex: 0, role: "button", "aria-label": "Choose a video file", onclick: () => input.click(), onkeydown: (e) => (e.key === "Enter" || e.key === " ") && input.click(),
    ondragover: (e) => { e.preventDefault(); drop.classList.add("over"); }, ondragleave: () => drop.classList.remove("over"),
    ondrop: (e) => { e.preventDefault(); drop.classList.remove("over"); pick(e.dataTransfer.files[0]); } },
  icon("upload"), h("b", {}, "Drop a video here"), h("span.small.muted", {}, "or click to choose"), input);
  const bar = h("progress", { max: 100, value: 0, hidden: true });
  const fillTags = () => { const b = brands.find((x) => x.key === ch.value); if (!tags.value.trim() && b?.hashtags?.length) tags.value = b.hashtags.join(" "); };
  const sync = () => {
    const b = brands.find((x) => x.key === ch.value);
    ytBox.hidden = !b?.youtube;
    when.hidden = mode !== "schedule";
    sureRow.hidden = mode !== "now";
    go.textContent = mode === "now" ? "Upload and publish" : "Upload";
    go.classList.toggle("danger", mode === "now"); go.classList.toggle("primary", mode !== "now");
  };
  function pick(f) {
    if (!f) return;
    if (!/\.(mp4|mov)$/i.test(f.name)) return toast("Only MP4 or MOV files", "error");
    if (f.size > MAX) return toast("The file is over 1 GB", "error");
    file = f;
    drop.classList.add("has");
    drop.replaceChildren(icon("film"), h("b", {}, f.name), h("span.small.muted", {}, `${(f.size / 1048576).toFixed(1)} MB · click to change`), input);
    if (!topic.value) topic.value = f.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").slice(0, 120);
  }
  ch.addEventListener("change", () => { fillTags(); sync(); });
  const go = button("Upload", () => send(), "primary");
  async function send() {
    if (!file) return toast("Choose a video first", "error");
    if (mode === "now" && !sure.checked) return toast("Tick the box to post it publicly", "error");
    const fd = new FormData();
    fd.append("brand", ch.value); fd.append("lang", langSel.value); fd.append("topic", topic.value.trim());
    fd.append("caption", caption.value.trim()); fd.append("hashtags", tags.value.trim());
    fd.append("yt_title", ytTitle.value.trim()); fd.append("yt_desc", ytDesc.value.trim());
    fd.append("after", mode); fd.append("when", when.value.replace("T", " ").slice(0, 16));
    if (mode === "now") fd.append("confirm", "true");
    fd.append("file", file, file.name);
    go.disabled = true; bar.hidden = false;
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload");
    xhr.setRequestHeader("x-csrf-token", state.csrf || "");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) bar.value = Math.round((100 * e.loaded) / e.total); };
    xhr.onload = () => {
      let res = {};
      try { res = JSON.parse(xhr.responseText); } catch { /* */ }
      if (xhr.status !== 202) { go.disabled = false; bar.hidden = true; return toast(res.error || `upload failed (HTTP ${xhr.status})`, "error", 8000); }
      dlg.close();
      jobToast(res.job, "Upload", async () => {
        await refresh();
        try {
          const j = await api(`/api/jobs/${res.job}`);
          const m = (j.log_tail || "").match(/DONE ([A-Z]{2,4}-U\d+(?:-[A-Z]{2})?)/);
          if (m) { ui.folder = mode === "draft" ? "drafts" : mode === "now" ? "published" : "queue"; draw(); openReel(m[1], refresh); }
        } catch { /* */ }
      });
      location.hash.startsWith("#/library") || (location.hash = "#/library");
    };
    xhr.onerror = () => { go.disabled = false; bar.hidden = true; toast("upload failed: network error", "error"); };
    xhr.send(fd);
  }
  const dlg = modal("Upload a reel", [
    drop, fileInfo, bar,
    h("div.two", {}, h("label.field", {}, "Channel", ch), h("label.field", {}, "Language", langSel)),
    h("label.field", {}, "Topic", topic),
    h("label.field", {}, "Caption", caption),
    h("label.field", {}, h("span.row", {}, "Hashtags", h("button.linkbtn", { type: "button", onclick: () => { tags.value = ""; fillTags(); } }, "use the brand's")), tags),
    ytBox,
    h("fieldset.choice", {}, h("legend.small.muted", {}, "After upload"), after, when, sureRow),
  ], [button("Cancel", () => dlg.close()), go]);
  dlg.classList.add("wide");
  fillTags(); sync();
  return dlg;
}
