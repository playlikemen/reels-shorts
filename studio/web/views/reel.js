// Reel detail drawer (all metadata, editable fields, player, contact sheet) and the publish confirm dialog.
import { h, api, post, drawer, closeDrawer, modal, toast, pill, button, busy, HEAD, brandOf, fmtWhen, jobToast, loadReels, ApiError } from "../app.js";

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
    const wrap = h("label.field", {}, name, input, r.pending?.[name] ? h("span.pend", {}, `Pending sync: ${r.pending[name].conflict !== undefined ? "conflict with Sheet" : "waiting"}`) : null);
    input.addEventListener("input", () => { changed[name] = input.value; wrap.classList.toggle("changed", input.value !== val); save.disabled = !Object.keys(changed).length; });
    input.addEventListener("change", () => input.dispatchEvent(new Event("input")));
    return wrap;
  }));
  const save = button("Save to Sheet", () => busy(save, () => saveEdits(r, changed, d, onChange)), "primary", { disabled: true });

  const igReady = r["Instagram Status"] === "Ready", ytReady = r["YouTube Status"] === "Ready";
  const igBtn = button("Publish to Instagram now", () => publishDialog(r, "instagram", onChange), igReady ? "primary" : "",
    { disabled: !igReady, title: igReady ? "" : `Instagram Status is ${r["Instagram Status"] || "empty"}; only Ready rows are posted` });
  const ytBtn = b.youtube ? button("Upload to YouTube now", () => publishDialog(r, "youtube", onChange), "", { disabled: !ytReady }) : null;
  const hold = r["Instagram Status"] === "Hold" || r["YouTube Status"] === "Hold";
  const canHold = hold || igReady || ytReady;
  const holdBtn = !canHold ? null : button(hold ? "Unhold" : "Hold", () => busy(holdBtn, async () => {
    const res = await post(`/api/reels/${r["Video ID"]}/hold`, { hold: !hold }, { allow: [202, 409] });
    if (res.status === "conflict") return conflictDialog(r, res.conflicts, d, onChange);
    toast(res.status === "pending" ? "Sheet write failed; queued for the next sync" : (hold ? "Back to Ready" : "Held"), res.status === "pending" ? "error" : "ok");
    await refresh(r["Video ID"], d, onChange);
  }));

  const links = [
    r["Instagram Post URL"] && h("a", { href: r["Instagram Post URL"], target: "_blank", rel: "noopener" }, "Instagram post ↗"),
    r["YouTube Shorts URL"] && h("a", { href: r["YouTube Shorts URL"], target: "_blank", rel: "noopener" }, "YouTube ↗"),
    r["Google Drive Folder"] && h("a", { href: r["Google Drive Folder"], target: "_blank", rel: "noopener" }, "Drive folder ↗"),
    r["Direct MP4 Download Link"] && h("a", { href: r["Direct MP4 Download Link"], target: "_blank", rel: "noopener" }, "Drive MP4 ↗"),
    media && h("a", { href: media, download: "" }, "Local MP4"),
  ].filter(Boolean);

  const warn = [];
  if (r.missing) warn.push(h("div.banner.bad", {}, "This row is missing from the Sheet. The local copy is kept; restore it from a snapshot below."));
  for (const [k, p] of Object.entries(r.pending || {})) {
    warn.push(h("div.banner.warn", {}, h("div", {}, h("b", {}, `${k}: `), `“${p.value}” waits to reach the Sheet`, p.conflict !== undefined ? ` (Sheet now has “${p.conflict}”)` : "", p.error ? ` · ${p.error}` : ""),
      h("span.spacer"), button("Keep Sheet value", async () => { await post(`/api/reels/${r["Video ID"]}/pending/drop`, { field: k }); refresh(r["Video ID"], d, onChange); }, "sm")));
  }

  body.replaceChildren(
    ...warn,
    h("div.detail", {},
      h("div", {},
        media ? h("video", { src: media, controls: true, preload: "metadata", playsInline: true, poster: `/thumb/${r["Video ID"]}.jpg` }) : h("img.poster", { src: `/thumb/${r["Video ID"]}.jpg`, alt: "" }),
        h("div.actions", {}, igBtn, ytBtn, holdBtn, button("Dry run (what would post)", () => dryRun(r, "instagram"), "ghost sm"),
          r.spec_path ? button("Render or stills…", () => import("./jobs.js").then((m) => m.newJob({ kind: "rerender", spec: r.spec_path, lang: (r["Video ID"].match(/-([A-Z]{2})$/) || [])[1]?.toLowerCase() || "" })), "ghost sm") : null),
        h("div.row", { style: { marginTop: "10px" } }, links.map((a) => [a, " "]))),
      h("div", {},
        h("div.row", { style: { marginBottom: "12px" } }, pill(r["Instagram Status"], "IG"), b.youtube ? pill(r["YouTube Status"], "YT") : null,
          h("span.muted", {}, `${b.name} · ${b.instagram || ""}`)),
        h("dl.kv", {},
          h("dt", {}, "Scheduled"), h("dd", {}, `${r["Scheduled Time (IST)"] || "—"} IST`),
          h("dt", {}, "Duration / format"), h("dd", {}, `${r.Duration || "—"} · ${r.Format || "—"}`),
          h("dt", {}, "Sheet"), h("dd", {}, `${r.tab} row ${r.sheet_row || "?"} · synced ${fmtWhen((r.loaded_at || "").slice(0, 16).replace("T", " "))}`),
          h("dt", {}, "Spec"), h("dd", { class: "mono" }, r.spec_path || "—"),
          data.keyword ? [h("dt", {}, "CTA keyword"), h("dd", {}, data.keyword)] : null,
          data.spec?.sources?.length ? [h("dt", {}, "Sources"), h("dd", {}, data.spec.sources.map((s) => h("div", {}, h("a", { href: s, target: "_blank", rel: "noopener" }, s))))] : null),
        h("h3", { style: { margin: "18px 0 8px" } }, "Edit"),
        fieldsEl, h("div.row", { style: { marginTop: "10px" } }, save, h("span.muted.small", {}, "Writes the Sheet first, then the local copy.")),
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
  if (res.status === "pending") toast("The Sheet did not answer; the edit is queued and retried on the next sync", "error", 7000);
  else toast(res.status === "unchanged" ? "Nothing changed" : "Saved to the Sheet", "ok");
  await refresh(r["Video ID"], d, onChange);
}

function conflictDialog(r, conflicts, d, onChange, changed) {
  const rows = Object.entries(conflicts).map(([k, c]) => h("div", {}, h("b", {}, k),
    h("div.conflict", {}, h("div", {}, h("div.small.muted", {}, "Sheet now"), h("div.preview", {}, c.sheet || "—")),
      h("div", {}, h("div.small.muted", {}, "Yours"), h("div.preview", {}, c.yours || "—")))));
  const dlg = modal("Changed in the Sheet meanwhile", [h("p", {}, "Someone edited these cells after you opened the reel. Which value should stay?"), rows], [
    button("Keep the Sheet's", () => { dlg.close(); refresh(r["Video ID"], d, onChange); }),
    changed ? button("Keep mine", (e) => busy(e.target, async () => { dlg.close(); await saveEdits(r, changed, d, onChange, true); }), "primary") : null,
  ]);
}

async function dryRun(r, platform) {
  const res = await post("/api/publish", { id: r["Video ID"], platform, dry_run: true }, { allow: [409] });
  if (res._status === 409) return toast(res.error, "error", 7000);
  jobToast(res.job, "Dry run");
  location.hash = `#/jobs/${res.job}`;
}

export async function publishDialog(r, platform, onChange) {
  let p;
  try { p = await api(`/api/publish/preview?id=${encodeURIComponent(r["Video ID"])}&platform=${platform}`); } catch (e) { return toast(e.message, "error"); }
  const sure = h("input", { type: "checkbox" });
  const over = h("input", { type: "checkbox" });
  const go = button(`Publish to ${platform === "instagram" ? "Instagram" : "YouTube"}`, () => busy(go, async () => {
    const res = await post("/api/publish", { id: r["Video ID"], platform, confirm: true, override_cap: over.checked }, { allow: [409] });
    if (res._status === 409) return toast(res.error, "error", 8000);
    dlg.close(); closeDrawer();
    jobToast(res.job, `Publish ${r["Video ID"]}`, () => { loadReels(true).then(() => onChange && onChange()); });
    location.hash = `#/jobs/${res.job}`;
  }), "danger", { disabled: true });
  const update = () => { go.disabled = !(sure.checked && (!p.over_cap || over.checked) && !p.problems.length && !p.lock_busy); };
  sure.addEventListener("change", update); over.addEventListener("change", update);
  const dlg = modal(`Publish ${r["Video ID"]} now`, [
    p.problems.length ? h("div.banner.bad", {}, h("div", {}, p.problems.map((x) => h("div", {}, x)))) : null,
    p.lock_busy ? h("div.banner.warn", {}, "The scheduler (cron) is running right now. Wait a minute and try again.") : null,
    h("dl.kv", {},
      h("dt", {}, "Account"), h("dd", {}, h("b", {}, p.handle), ` · ${p.brand}`),
      h("dt", {}, "Status"), h("dd", {}, pill(p.status)),
      p.cap != null || p.posted_today != null ? [h("dt", {}, "Today"), h("dd", {}, `${p.posted_today ?? 0} posted` + (p.cap ? ` of a daily cap of ${p.cap}` : " (no daily cap)"))] : null,
      p.title ? [h("dt", {}, "Title"), h("dd", {}, p.title)] : null),
    h("div", {}, h("div.small.muted", {}, platform === "instagram" ? "Caption preview" : "Description preview"), h("div.preview", {}, p.caption || "—")),
    h("p.small.muted", {}, "This goes through the same scheduler code as cron: the row is marked Publishing first, then Published or Failed. Only this reel and platform are touched."),
    h("label.check", {}, sure, h("span", {}, `Post this reel publicly on ${p.handle} now.`)),
    p.over_cap ? h("label.check", {}, over, h("span", {}, `Post anyway: the daily cap of ${p.cap} is already reached.`)) : null,
  ], [button("Cancel", () => dlg.close()), go]);
}
