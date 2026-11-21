// Calendar: month and week view of scheduled reels. Drag a reel to another day to reschedule it (keeps its time).
import { h, api, state, loadReels, brandOf, brandDot, button, busy, toast, modal, istNow, short } from "../app.js";
import { openReel } from "./reel.js";

const ui = { mode: "month", anchor: null, brand: "" };
const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parse = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };

export async function render(root) {
  ui.brand = state.channel;
  ui.anchor = ui.anchor || istNow().slice(0, 10);
  const data = await loadReels(true);
  const body = h("div");
  const draw = () => drawCal(body, state.reels.reels);
  const title = h("h1");
  const nav = (step) => () => {
    const d = parse(ui.anchor);
    if (ui.mode === "month") d.setMonth(d.getMonth() + step, 1); else d.setDate(d.getDate() + 7 * step);
    ui.anchor = iso(d); draw(); setTitle();
  };
  const setTitle = () => {
    const d = parse(ui.anchor);
    title.textContent = ui.mode === "month" ? d.toLocaleDateString(undefined, { month: "long", year: "numeric" }) : `Week of ${weekStart(d).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
  };
  setTitle();
  const seg = h("div.seg", {}, ["month", "week"].map((m) => h("button", { type: "button", class: ui.mode === m ? "on" : "", onclick: (e) => {
    ui.mode = m; e.target.parentNode.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === e.target)); draw(); setTitle();
  } }, m === "month" ? "Month" : "Week")));
  const brandSel = h("select", { onchange: (e) => { ui.brand = e.target.value; draw(); } }, h("option", { value: "" }, "All brands"),
    state.brands.map((b) => h("option", { value: b.key, selected: ui.brand === b.key }, b.name)));
  root.append(
    h("header.page", {}, title, button("‹", nav(-1), "sm"), button("Today", () => { ui.anchor = istNow().slice(0, 10); draw(); setTitle(); }, "sm"), button("›", nav(1), "sm"), brandSel, seg,
      h("div.sub", {}, "Slots (IST): ", state.brands.map((b) => h("span.row", { style: { display: "inline-flex", marginRight: "12px" } }, brandDot(b.key), `${b.name} ${b.slots.join(", ") || "—"}`)),
        " · Drag a reel to another day to reschedule it.")),
    body);
  draw();
}

function weekStart(d) { const x = new Date(d); x.setDate(x.getDate() - ((x.getDay() + 6) % 7)); return x; }

function drawCal(body, reels) {
  const a = parse(ui.anchor);
  let start, days;
  if (ui.mode === "month") { start = weekStart(new Date(a.getFullYear(), a.getMonth(), 1)); days = 42; } else { start = weekStart(a); days = 7; }
  const byDay = {};
  for (const r of reels) {
    const t = r["Scheduled Time (IST)"];
    if (!t || (ui.brand && r.brand !== ui.brand)) continue;
    (byDay[t.slice(0, 10)] ||= []).push(r);
  }
  const today = istNow().slice(0, 10);
  const clashes = [];
  const cells = [];
  for (let i = 0; i < days; i++) {
    const d = new Date(start); d.setDate(start.getDate() + i);
    const key = iso(d);
    const list = (byDay[key] || []).sort((x, y) => x["Scheduled Time (IST)"].localeCompare(y["Scheduled Time (IST)"]));
    const perBrand = {};
    list.forEach((r) => { if (!isDone(r)) perBrand[r.brand] = (perBrand[r.brand] || 0) + 1; });
    const clash = Object.entries(perBrand).filter(([, n]) => n > 1);
    if (clash.length) clashes.push(`${key}: ${clash.map(([b, n]) => `${n} ${brandOf(b).name}`).join(", ")}`);
    const cell = h("div.day", { class: [ui.mode === "month" && d.getMonth() !== a.getMonth() ? "other" : "", key === today ? "today" : "", clash.length ? "clash" : ""].join(" "), dataset: { day: key } },
      h("span.num", {}, d.getDate()), list.map((r) => ev(r)));
    cell.addEventListener("dragover", (e) => { e.preventDefault(); cell.classList.add("over"); });
    cell.addEventListener("dragleave", () => cell.classList.remove("over"));
    cell.addEventListener("drop", (e) => { e.preventDefault(); cell.classList.remove("over"); const vid = e.dataTransfer.getData("text/plain"); if (vid) move(vid, key, body); });
    cells.push(cell);
  }
  body.replaceChildren(
    clashes.length ? h("div.banner.warn", {}, h("div", {}, h("b", {}, "Two reels for one brand on the same day: "), clashes.join(" · "))) : null,
    h("div.cal", { class: ui.mode === "week" ? "week" : "" }, DOW.map((x) => h("div.dow", {}, x)), cells));
}

const isDone = (r) => (r["Instagram Status"] || "").startsWith("Published") || r["Instagram Status"] === "Publishing";

function ev(r) {
  const done = isDone(r);
  const e = h("div.ev", { class: done ? "published" : "", draggable: !done, dataset: { brand: r.brand }, title: `${r["Video ID"]} · ${r["Category / Topic"]} · IG ${r["Instagram Status"]}`,
    onclick: () => done ? openReel(r["Video ID"]) : quickMove(r) },
    brandDot(r.brand), h("span", {}, r["Video ID"]), h("span.t.muted", {}, r["Scheduled Time (IST)"].slice(11)));
  e.addEventListener("dragstart", (x) => { x.dataTransfer.setData("text/plain", r["Video ID"]); e.classList.add("dragging"); });
  e.addEventListener("dragend", () => e.classList.remove("dragging"));
  return e;
}

function quickMove(r) {
  const input = h("input", { value: r["Scheduled Time (IST)"], placeholder: "YYYY-MM-DD HH:MM" });
  const dlg = modal(`${r["Video ID"]}`, [h("p.muted", {}, short(r["Category / Topic"], 100)), h("label.field", {}, "Scheduled time (IST)", input)], [
    button("Open reel", () => { dlg.close(); openReel(r["Video ID"]); }, "ghost"),
    button("Reschedule", (e) => busy(e.target, async () => { await save(r["Video ID"], input.value); dlg.close(); }), "primary")]);
}

async function save(vid, when) {
  const r = state.reels.reels.find((x) => x["Video ID"] === vid);
  const res = await api(`/api/reels/${vid}`, { method: "PATCH", body: { fields: { "Scheduled Time (IST)": when }, base: { "Scheduled Time (IST)": r["Scheduled Time (IST)"] } }, allow: [202, 409] });
  if (res.status === "conflict") { toast("The Sheet changed meanwhile; open the reel to choose a value", "error", 7000); return; }
  if (res._status === 409) { toast(res.error, "error", 7000); return; }
  toast(res.status === "pending" ? `${vid}: queued (Sheet did not answer)` : `${vid} → ${when}`, res.status === "pending" ? "error" : "ok");
  await loadReels(true);
  location.hash === "#/calendar" ? window.dispatchEvent(new HashChangeEvent("hashchange")) : null;
}

async function move(vid, day, body) {
  const r = state.reels.reels.find((x) => x["Video ID"] === vid);
  if (!r) return;
  const time = r["Scheduled Time (IST)"].slice(11) || brandOf(r.brand).slots?.[0] || "19:30";
  const when = `${day} ${time}`;
  if (when === r["Scheduled Time (IST)"]) return;
  const old = r["Scheduled Time (IST)"];
  r["Scheduled Time (IST)"] = when;          // optimistic
  drawCal(body, state.reels.reels);
  r["Scheduled Time (IST)"] = old;
  toast(`Moving ${vid} to ${when}…`);
  await save(vid, when).catch((e) => toast(e.message, "error"));
}
