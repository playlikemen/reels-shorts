// Reel detail drawer (all metadata, editable fields, player, contact sheet) and the publish confirm dialog.
import { h, api, post, drawer, modal, toast, pill, button, busy, brandOf, fmtWhen, jobToast, loadReels, ApiError, icon } from "../app.js";
import { publishButton, canPublish, scheduleDialog, archiveReel, holdReel } from "./publish.js";

const EDIT = [
  ["Category / Topic", "input"], ["Scheduled Time (IST)", "input"], ["Instagram Status", "status"], ["YouTube Status", "status"],
  ["Instagram Viral Caption", "textarea", 7], ["Instagram Hashtags", "textarea", 2], ["YouTube Title", "input"],
  ["YouTube SEO Tags (Separated)", "textarea", 2], ["YouTube Best SEO Description", "textarea", 6],
];
const STATUSES = ["Ready", "Hold", "Published", "No channel", "Manual upload needed"];

export async function openReel(vid, onChange) {
  const d = drawer(vid, h("div.empty", {}, "Loading…"));
  let data;
  try { data = await api(`/api/reels/${encodeURIComponent(vid)}`); } catch (e) { d.querySelector(".drawer-body").replaceChildren(h("div.empty", {}, e.message)); return; }
  render(d, data, onChange);
}

function render(d, data, onChange) {
  const r = data.reel, b = brandOf(r.brand);
  const media = r["Local Path"] ? `/media/${r["Local Path"].replace(/^out\//, "")}` : null;
  const body = d.querySelector(".drawer-body");
  const changed = {};
  const fieldsEl = h("div.fields", {}, EDIT.map(([name, kind, rows]) => {
    const val = r[name] || "";
    let input;
    if (kind === "status") {
      input = h("select", {}, [...new Set([val, ...STATUSES])].filter((x) => x !== undefined).map((s) => h("option", { value: s, selected: s === val }, s || "(empty)")));
    } else if (kind === "textarea") input = h("textarea", { rows: rows || 3 }, val);
    else input = h("input", { value: val, placeholder: name === "Scheduled Time (IST)" ? "YYYY-MM-DD HH:MM" : "" });
    const wrap = h("label.field", {}, name, input, r.pending?.[name]?.error ? h("span.pend", {}, "Not mirrored to the Sheet yet") : null);
    input.addEventListener("input", () => { changed[name] = input.value; wrap.classList.toggle("changed", input.value !== val); save.disabled = !Object.keys(changed).length; });
    input.addEventListener("change", () => input.dispatchEvent(new Event("input")));
    return wrap;
  }));
  const save = button("Save to Sheet", () => busy(save, () => saveEdits(r, changed, d, onChange)), "primary", { disabled: true });

  const refreshMe = () => refresh(r["Video ID"], d, onChange);
  const igBtn = canPublish(r, "instagram") ? publishButton(r, "instagram", { onDone: refreshMe }) : null;
  const ytBtn = canPublish(r, "youtube") ? publishButton(r, "youtube", { onDone: refreshMe }) : null;
  const archived = r.folder === "archive";
  const published = (r["Instagram Status"] || "").startsWith("Published");
  const hold = (r["Instagram Status"] || "").startsWith("Hold") || r["YouTube Status"] === "Hold";
  const canHold = r["Instagram Status"] === "Hold" || r["YouTube Status"] === "Hold" || r["Instagram Status"] === "Ready" || r["YouTube Status"] === "Ready";
  const holdBtn = !canHold ? null : button(hold ? "Unhold" : "Hold", (e) => busy(e.target, () => holdReel(r, !hold, refreshMe)), "ghost sm");
  const schedBtn = published || archived && r["Instagram Post URL"] ? null
    : button([icon("clock"), "Schedule…"], () => scheduleDialog(r, refreshMe), "sm");
  const archBtn = button([icon("archive"), archived ? "Unarchive" : "Archive"], (e) => busy(e.target, () => archiveReel(r, !archived, refreshMe)), "ghost sm",
    { title: archived ? "Put back the status it had before" : "Hide it from the queue; nothing is deleted and cron never posts it" });

  const links = [
    r["Instagram Post URL"] && h("a", { href: r["Instagram Post URL"], target: "_blank", rel: "noopener" }, "Instagram post ↗"),
    r["YouTube Shorts URL"] && h("a", { href: r["YouTube Shorts URL"], target: "_blank", rel: "noopener" }, "YouTube ↗"),
    r["Google Drive Folder"] && h("a", { href: r["Google Drive Folder"], target: "_blank", rel: "noopener" }, "Drive folder ↗"),
    r["Direct MP4 Download Link"] && h("a", { href: r["Direct MP4 Download Link"], target: "_blank", rel: "noopener" }, "Drive MP4 ↗"),
    media && h("a", { href: media, download: "" }, "Local MP4"),
  ].filter(Boolean);

  const warn = [];
  const waiting = Object.entries(r.pending || {}).filter(([, p]) => p.error);
  if (waiting.length) warn.push(h("div.banner.warn", {}, h("div", {}, h("b", {}, "Not in the Sheet mirror yet: "), waiting.map(([k]) => k).join(", "), ` · ${waiting[0][1].error}. The studio has the change; the next push retries.`)));

  body.replaceChildren(
    ...warn,
    h("div.detail", {},
      h("div", {},
        media ? h("video", { src: media, controls: true, preload: "metadata", playsInline: true, poster: `/thumb/${r["Video ID"]}.jpg` }) : h("img.poster", { src: `/thumb/${r["Video ID"]}.jpg`, alt: "" }),
        h("div.actions", {}, igBtn, ytBtn, schedBtn, holdBtn, archBtn, button("Dry run (what would post)", () => dryRun(r, "instagram"), "ghost sm"),
          r.spec_path ? button("Render or stills…", () => import("./jobs.js").then((m) => m.newJob({ kind: "rerender", spec: r.spec_path, lang: (r["Video ID"].match(/-([A-Z]{2})$/) || [])[1]?.toLowerCase() || "" })), "ghost sm") : null),
        h("div.row", { style: { marginTop: "10px" } }, links.map((a) => [a, " "]))),
      h("div", {},
        h("div.row", { style: { marginBottom: "12px" } }, pill(r["Instagram Status"], "IG"), b.youtube ? pill(r["YouTube Status"], "YT") : null,
          h("span.muted", {}, `${b.name} · ${b.instagram || ""}`)),
        h("dl.kv", {},
          h("dt", {}, "Scheduled"), h("dd", {}, `${r["Scheduled Time (IST)"] || "—"} IST`),
          h("dt", {}, "Duration / format"), h("dd", {}, `${r.Duration || "—"} · ${r.Format || "—"}`),
          h("dt", {}, "Sheet mirror"), h("dd", {}, `${r.tab} row ${r.sheet_row || "?"} · ${Object.keys(r.pending || {}).length ? "waiting" : "up to date"}`),
          h("dt", {}, "Spec"), h("dd", { class: "mono" }, r.spec_path || "—"),
          data.keyword ? [h("dt", {}, "CTA keyword"), h("dd", {}, data.keyword)] : null,
          data.spec?.sources?.length ? [h("dt", {}, "Sources"), h("dd", {}, data.spec.sources.map((s) => h("div", {}, h("a", { href: s, target: "_blank", rel: "noopener" }, s))))] : null),
        h("h3", { style: { margin: "18px 0 8px" } }, "Edit"),
        fieldsEl, h("div.row", { style: { marginTop: "10px" } }, save, h("span.muted.small", {}, "Saved in the studio, then mirrored to the Sheet.")),
        data.publish_log.length ? [h("h3", { style: { margin: "18px 0 8px" } }, "Publish log"),
          h("div.list", {}, data.publish_log.map((e) => h("div", {}, pill(e.status === "published" ? "Published" : e.status.startsWith("canary") ? "Ready" : "Failed", e.platform), h("span.small", {}, e.at?.slice(0, 16).replace("T", " ")), h("span.small.muted", {}, e.error ? e.error.slice(0, 140) : e.permalink || e.url || ""))))] : null,
        data.insights.length ? [h("h3", { style: { margin: "18px 0 8px" } }, "Insights"), insightLine(data.insights.at(-1))] : null,
        data.files.includes("contact.jpg") ? [h("h3", { style: { margin: "18px 0 8px" } }, "Contact sheet"), h("img.contact", { src: `/media/${data.out_dir.replace(/^out\//, "")}/contact.jpg`, alt: "contact sheet", loading: "lazy" })] : null,
        data.stills.length ? [h("h3", { style: { margin: "18px 0 8px" } }, "Stills"), h("div.stills", {}, data.stills.map((s) => h("a", { href: `/media/${data.out_dir.replace(/^out\//, "")}/${s}`, target: "_blank" }, h("img", { src: `/media/${data.out_dir.replace(/^out\//, "")}/${s}`, loading: "lazy", alt: s }))))] : null,
        restoreBox(r, data.snapshots, d, onChange))));
}

function insightLine(i) {
  return h("div.stats", {}, [["Views", i.views], ["Reach", i.reach], ["Shares", i.shares], ["Saves", i.saves], ["Avg watch", `${i.avg_watch}s`]]
    .map(([k, v]) => h("div.panel.stat", {}, h("span.muted.small", {}, k), h("b", {}, v ?? "—"))));
}

function restoreBox(r, snaps, d, onChange) {
  if (!snaps?.length) return null;
  const sel = h("select", {}, snaps.map((s) => h("option", { value: s }, s)));
  const out = h("div");
  const look = button("Compare", () => busy(look, async () => {
    const res = await api(`/api/reels/${r["Video ID"]}/restore?date=${sel.value}`);
    const keys = Object.keys(res.diff || {});
    out.replaceChildren(keys.length ? h("div", {},
      h("p.small.muted", {}, `${keys.length} cell(s) differ. Status and post links that already hold a value are never rolled back.`),
      keys.map((k) => h("div.conflict", {}, h("div", {}, h("div.small.muted", {}, `${k} now`), h("div.preview", {}, res.current?.[k] || "—")),
        h("div", {}, h("div.small.muted", {}, `${k} in ${sel.value}`), h("div.preview", {}, res.diff[k] || "—")))),
      button("Restore these cells", async (e) => busy(e.target, async () => {
        const x = await post(`/api/reels/${r["Video ID"]}/restore`, { date: sel.value, dry_run: false }, { allow: [202, 409] });
        toast(`Restore: ${x.status}`, x.status === "ok" ? "ok" : "error"); refresh(r["Video ID"], d, onChange);
      }), "danger sm")) : h("p.small.muted", {}, "No difference."));
  }), "sm");
  return [h("h3", { style: { margin: "18px 0 8px" } }, "Restore from snapshot"), h("div.row", {}, sel, look), out];
}

async function refresh(vid, d, onChange) {
  const data = await api(`/api/reels/${encodeURIComponent(vid)}`);
  render(d, data, onChange);
  await loadReels(true);
  onChange && onChange();
}

async function saveEdits(r, changed, d, onChange, force = false) {
  const base = Object.fromEntries(Object.keys(changed).map((k) => [k, r[k]]));
  const res = await api(`/api/reels/${r["Video ID"]}`, { method: "PATCH", body: { fields: changed, base, force }, allow: [202, 409] });
  if (res._status === 409 && res.status === "conflict") return conflictDialog(r, res.conflicts, d, onChange, changed);
  if (res._status === 409) throw new ApiError(res.error, 409, res);
  toast(res.status === "unchanged" ? "Nothing changed" : "Saved", "ok");
  await refresh(r["Video ID"], d, onChange);
}

function conflictDialog(r, conflicts, d, onChange, changed) {
  const rows = Object.entries(conflicts).map(([k, c]) => h("div", {}, h("b", {}, k),
    h("div.conflict", {}, h("div", {}, h("div.small.muted", {}, "Now"), h("div.preview", {}, c.current ?? c.sheet ?? "—")),
      h("div", {}, h("div.small.muted", {}, "Yours"), h("div.preview", {}, c.yours || "—")))));
  const dlg = modal("Changed meanwhile", [h("p", {}, "These cells changed in the studio after you opened the reel. Which value should stay?"), rows], [
    button("Keep the current", () => { dlg.close(); refresh(r["Video ID"], d, onChange); }),
    changed ? button("Keep mine", (e) => busy(e.target, async () => { dlg.close(); await saveEdits(r, changed, d, onChange, true); }), "primary") : null,
  ]);
}

async function dryRun(r, platform) {
  const res = await post("/api/publish", { id: r["Video ID"], platform, dry_run: true }, { allow: [409] });
  if (res._status === 409) return toast(res.error, "error", 7000);
  jobToast(res.job, "Dry run");
  location.hash = `#/jobs/${res.job}`;
}
