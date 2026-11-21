// Library: every reel across the brands, grid or table, filters, search, bulk scheduling.
import { h, api, post, state, loadReels, pill, brandDot, brandOf, fmtWhen, short, button, busy, toast, icon, jobToast, modal, istNow } from "../app.js";
import { openReel } from "./reel.js";

const ui = { view: "grid", brand: "", status: "", q: "", when: "", sel: new Set() };
try { Object.assign(ui, JSON.parse(localStorage.getItem("rs-lib") || "{}"), { sel: new Set() }); } catch { /* */ }
const remember = () => { try { localStorage.setItem("rs-lib", JSON.stringify({ view: ui.view, brand: ui.brand, status: ui.status, when: ui.when })); } catch { /* */ } };

export async function render(root, ctx) {
  const data = await loadReels(true);
  const head = h("header.page", {}, h("h1", {}, "Library"),
    h("span.muted", {}, `${data.count} reels · synced ${data.last_pull ? new Date(data.last_pull.at).toLocaleTimeString() : "never"}`),
    button("Sync from Sheet", (e) => busy(e.target, async () => { const r = await post("/api/sync", {}); jobToast(r.job, "Sync", () => render(root.replaceChildren() || root, ctx)); }), "", {}));
  const body = h("div");
  root.append(head, banners(data), filters(() => draw(body, data)), body);
  draw(body, data);
  if (ctx.params[0]) openReel(ctx.params[0], () => draw(body, state.reels));
}

function banners(data) {
  const out = h("div");
  const missing = data.reels.filter((r) => r.missing), pending = data.reels.filter((r) => Object.keys(r.pending || {}).length);
  const errs = Object.entries(data.last_pull?.summary || {}).filter(([, s]) => s.error);
  if (missing.length) out.append(h("div.banner.bad", {}, h("div", {}, h("b", {}, `${missing.length} row(s) missing in the Sheet: `), missing.map((r) => r["Video ID"]).join(", "), ". Kept locally; open one to restore it.")));
  if (pending.length) out.append(h("div.banner.warn", {}, h("div", {}, h("b", {}, `${pending.length} edit(s) pending sync: `), pending.map((r) => r["Video ID"]).join(", "), ". Retried on the next sync.")));
  for (const [tab, s] of errs) out.append(h("div.banner.warn", {}, `Last sync could not read ${tab}: ${short(s.error, 160)}`));
  if (data.unsynced?.length) {
    out.append(h("div.banner.info", {}, h("div", {}, h("b", {}, `${data.unsynced.length} rendered, not synced: `),
      data.unsynced.slice(0, 12).map((u) => h("span", {}, u["Video ID"], " ", u.spec_path ? h("button.btn.sm", {
        type: "button", onclick: (e) => syncRender(e.target, u),
      }, "Sync") : h("span.muted.small", {}, "(no spec)"), "  ")), data.unsynced.length > 12 ? "…" : "")));
  }
  return out;
}

async function syncRender(btn, u) {
  const dlg = modal(`Sync ${u["Video ID"]}`, [h("p", {}, `Uploads ${u.local_path} to a new Drive folder and writes its Sheet row in ${u.tab} with status Ready, using the schedule from ${u.spec_path}. Cron then posts it when due.`)],
    [button("Cancel", () => dlg.close()), button("Upload and add row", async (e) => busy(e.target, async () => {
      const r = await post("/api/jobs", { kind: "sync", params: { spec: u.spec_path, lang: u.lang, id: u["Video ID"] } });
      dlg.close(); jobToast(r.job, `Sync ${u["Video ID"]}`);
    }), "primary")]);
}

function filters(redraw) {
  const brands = h("select", { "aria-label": "Brand", onchange: (e) => { ui.brand = e.target.value; remember(); redraw(); } },
    h("option", { value: "" }, "All brands"), state.brands.map((b) => h("option", { value: b.key, selected: ui.brand === b.key }, b.name)));
  const status = h("select", { "aria-label": "Status", onchange: (e) => { ui.status = e.target.value; remember(); redraw(); } },
    [["", "Any status"], ["ready", "Ready"], ["hold", "Hold"], ["published", "Published"], ["failed", "Failed"], ["publishing", "Publishing"], ["other", "Other"]]
      .map(([v, l]) => h("option", { value: v, selected: ui.status === v }, l)));
  const when = h("select", { "aria-label": "Date", onchange: (e) => { ui.when = e.target.value; remember(); redraw(); } },
    [["", "Any date"], ["today", "Today"], ["week", "Next 7 days"], ["future", "Upcoming"], ["past", "Past"]].map(([v, l]) => h("option", { value: v, selected: ui.when === v }, l)));
  const q = h("input", { type: "search", placeholder: "Search caption, topic, tags…", value: ui.q, oninput: (e) => { ui.q = e.target.value; redraw(); } });
  const seg = h("div.seg", {}, ["grid", "table"].map((v) => h("button", { type: "button", class: ui.view === v ? "on" : "", onclick: (e) => {
    ui.view = v; remember(); e.target.parentNode.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === e.target)); redraw();
  } }, v === "grid" ? "Grid" : "Table")));
  return h("div.filters", {}, h("div.search", {}, icon("search"), q), brands, status, when, h("span.spacer"), seg);
}

function matches(r) {
  if (ui.brand && r.brand !== ui.brand) return false;
  const st = [r["Instagram Status"], r["YouTube Status"]].map((s) => (s || "").toLowerCase());
  if (ui.status === "other" && st.some((s) => ["ready", "hold", "publishing"].includes(s) || s.startsWith("published") || s.startsWith("failed"))) return false;
  if (ui.status && ui.status !== "other" && !st.some((s) => s.startsWith(ui.status))) return false;
  if (ui.when) {
    const t = r["Scheduled Time (IST)"] || "", now = istNow();
    const plus7 = new Date(Date.now() + 7 * 864e5 + 5.5 * 36e5).toISOString().slice(0, 16).replace("T", " ");
    if (ui.when === "today" && t.slice(0, 10) !== now.slice(0, 10)) return false;
    if (ui.when === "week" && !(t >= now && t <= plus7)) return false;
    if (ui.when === "future" && !(t >= now)) return false;
    if (ui.when === "past" && !(t && t < now)) return false;
  }
  if (ui.q) {
    const hay = JSON.stringify(r).toLowerCase();
    if (!ui.q.toLowerCase().split(/\s+/).filter(Boolean).every((w) => hay.includes(w))) return false;
  }
  return true;
}

function draw(body, data) {
  const list = data.reels.filter(matches);
  const redraw = () => draw(body, state.reels);
  body.replaceChildren(bulkBar(redraw), list.length ? (ui.view === "grid" ? grid(list, redraw) : table(list, redraw)) : h("div.empty", {}, h("h2", {}, "No reels match"), h("p", {}, "Change the filters or sync from the Sheet.")));
}

function bulkBar(redraw) {
  if (!ui.sel.size) return null;
  const start = h("input", { value: nextSlot(), size: 16, "aria-label": "First slot" });
  const every = h("input", { type: "number", value: 1, min: 1, max: 14, style: { width: "60px" }, "aria-label": "Days apart" });
  const run = (action) => async (e) => busy(e.target, async () => {
    const r = await post("/api/reels/bulk", { ids: [...ui.sel], action, start: start.value, every_days: +every.value });
    jobToast(r.job, `Bulk ${action}`, async () => { await loadReels(true); redraw(); });
    ui.sel.clear(); redraw();
  });
  return h("div.bulkbar", {}, h("b", {}, `${ui.sel.size} selected`), h("span.spacer"),
    button("Hold", run("hold"), "sm"), button("Ready", run("ready"), "sm"),
    h("span", {}, "Schedule from"), start, h("span", {}, "every"), every, h("span", {}, "day(s)"), button("Schedule", run("schedule"), "sm primary"),
    button("Clear", () => { ui.sel.clear(); redraw(); }, "sm ghost"));
}

function nextSlot() {
  const d = new Date(Date.now() + 864e5 + 5.5 * 36e5);
  return d.toISOString().slice(0, 10) + " 19:30";
}

function selBox(r, redraw) {
  return h("input.sel", { type: "checkbox", checked: ui.sel.has(r["Video ID"]), "aria-label": `Select ${r["Video ID"]}`,
    onclick: (e) => { e.stopPropagation(); e.target.checked ? ui.sel.add(r["Video ID"]) : ui.sel.delete(r["Video ID"]); redraw(); } });
}

function grid(list, redraw) {
  return h("div.reels", {}, list.map((r) => {
    const b = brandOf(r.brand);
    return h("article.card.reel", { tabindex: 0, onclick: () => openReel(r["Video ID"], redraw), onkeydown: (e) => e.key === "Enter" && openReel(r["Video ID"], redraw) },
      h("div.thumb", {}, h("img", { src: `/thumb/${r["Video ID"]}.jpg`, loading: "lazy", alt: "" }), selBox(r, redraw),
        r.Duration ? h("span.dur", {}, r.Duration) : null,
        r.missing ? h("span.flag.pill.failed", {}, "missing in sheet") : Object.keys(r.pending || {}).length ? h("span.flag.pill.warn", {}, "pending sync") : null),
      h("div.meta", {},
        h("div.id", {}, brandDot(r.brand), r["Video ID"]),
        h("div.topic", {}, r["Category / Topic"]),
        h("div.pills", {}, pill(r["Instagram Status"], "IG"), b.youtube ? pill(r["YouTube Status"], "YT") : null),
        h("div.when", {}, fmtWhen(r["Scheduled Time (IST)"]))));
  }));
}

function table(list, redraw) {
  return h("div.tbl-wrap", {}, h("table.tbl", {},
    h("thead", {}, h("tr", {}, ["", "ID", "Topic", "Brand", "IG", "YouTube", "Scheduled (IST)", "Duration", "Links"].map((t) => h("th", {}, t)))),
    h("tbody", {}, list.map((r) => h("tr", { onclick: () => openReel(r["Video ID"], redraw) },
      h("td", {}, selBox(r, redraw)), h("td", {}, h("b", {}, r["Video ID"])), h("td", {}, short(r["Category / Topic"], 60)),
      h("td", {}, h("span.row", {}, brandDot(r.brand), brandOf(r.brand).name)), h("td", {}, pill(r["Instagram Status"])), h("td", {}, pill(r["YouTube Status"])),
      h("td", {}, r["Scheduled Time (IST)"]), h("td", {}, r.Duration),
      h("td", { onclick: (e) => e.stopPropagation() }, [r["Instagram Post URL"] && h("a", { href: r["Instagram Post URL"], target: "_blank", rel: "noopener" }, "IG "),
        r["YouTube Shorts URL"] && h("a", { href: r["YouTube Shorts URL"], target: "_blank", rel: "noopener" }, "YT "),
        r["Google Drive Folder"] && h("a", { href: r["Google Drive Folder"], target: "_blank", rel: "noopener" }, "Drive")]))))));
}
