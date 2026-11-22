// Files: temporary file hosting. A folder tree, drag-and-drop upload (up to 1 GB), copy-link, expiry badges, storage bar.
// Only the owner (or the API key) can list or change files; each file's public link is /f/<token>/<name>.
import { h, api, post, state, button, busy, toast, icon, modal, fmtBytes } from "../app.js";

const ui = { folder: null, q: "" };
let data = null;
let root$ = null;

const del = (path) => api(path, { method: "DELETE" });
const patch = (path, body) => api(path, { method: "PATCH", body });

function left(iso) {
  if (!iso) return { text: "never expires", cls: "ready" };
  const ms = new Date(iso) - Date.now();
  if (ms <= 0) return { text: "expired", cls: "failed" };
  const hrs = ms / 3600e3;
  const text = hrs < 1 ? `${Math.max(1, Math.round(ms / 60e3))} min left` : hrs < 48 ? `${Math.round(hrs)} h left` : `${Math.round(hrs / 24)} days left`;
  return { text, cls: hrs < 24 ? "warn" : "" };
}

function copy(text, what = "Link") {
  navigator.clipboard.writeText(text).then(() => toast(`${what} copied`, "ok"), () => toast("could not copy; select it by hand", "error"));
}

async function load() {
  const q = new URLSearchParams();
  if (ui.folder) q.set("folder", ui.folder);
  if (ui.q) q.set("q", ui.q);
  data = await api(`/api/files?${q}`);
  draw();
}

function expiryPicker(value = "7d") {
  const sel = h("select", { "aria-label": "Expires" },
    [["1d", "1 day"], ["7d", "1 week"], ["custom", "Custom date…"], ["never", "Never"]].map(([v, l]) => h("option", { value: v, selected: v === value }, l)));
  const max = new Date(Date.now() + 90 * 864e5 - 6e4);
  const when = h("input", { type: "datetime-local", hidden: true, "aria-label": "Expires at (IST)",
    min: new Date(Date.now() + 36e5).toISOString().slice(0, 16), max: max.toISOString().slice(0, 16) });
  sel.onchange = () => { when.hidden = sel.value !== "custom"; };
  const value$ = () => (sel.value === "custom" ? when.value.replace("T", " ") : sel.value);
  return { el: h("span.row", {}, sel, when), value: value$ };
}

function upload(fileList, exp) {
  const files = [...fileList];
  if (!files.length) return;
  const big = files.find((f) => f.size > data.max_upload);
  if (big) return toast(`${big.name} is over 1 GB`, "error", 7000);
  const room = data.usage.quota - data.usage.used;
  const total = files.reduce((n, f) => n + f.size, 0);
  if (total > room) return toast(`Not enough room: ${fmtBytes(total)} to upload, ${fmtBytes(room)} free`, "error", 8000);
  const expiry = exp.value();
  if (!expiry) return toast("pick the expiry date and time", "error");
  const bar = h("progress", { max: 100, value: 0, style: { width: "100%" } });
  const label = h("span.small", {}, `Uploading ${files.length} file(s)…`);
  const box = h("div.banner", {}, h("div", { style: { width: "100%" } }, label, bar));
  root$.querySelector(".files-up").append(box);
  let i = 0;
  const next = () => {
    if (i >= files.length) { box.remove(); toast(`Uploaded ${files.length} file(s)`, "ok"); load(); return; }
    const f = files[i++];
    label.textContent = `Uploading ${f.name} (${i}/${files.length})…`;
    const fd = new FormData();
    fd.append("file", f, f.name);
    fd.append("expiry", expiry);
    if (ui.folder) fd.append("folder_id", ui.folder);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/files");
    xhr.setRequestHeader("x-csrf-token", state.csrf || "");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) bar.value = Math.round((100 * e.loaded) / e.total); };
    xhr.onload = () => {
      let res = {};
      try { res = JSON.parse(xhr.responseText); } catch { /* */ }
      if (xhr.status !== 201) { box.remove(); toast(`${f.name}: ${res.error || `upload failed (HTTP ${xhr.status})`}`, "error", 9000); load(); return; }
      bar.value = 0; next();
    };
    xhr.onerror = () => { box.remove(); toast("upload failed: network error", "error"); };
    xhr.send(fd);
  };
  next();
}

function tree() {
  const kids = (pid) => data.folders.filter((f) => (f.parent_id || null) === pid);
  const item = (f, depth) => [
    h("button.frow" + (String(ui.folder) === String(f.id) ? ".on" : ""), { type: "button", style: { paddingLeft: `${10 + depth * 14}px` },
      onclick: () => { ui.folder = f.id; ui.q = ""; load(); } }, icon("stack"), h("span", {}, f.name), h("span.small.muted", {}, f.files || "")),
    ...kids(f.id).flatMap((k) => item(k, depth + 1)),
  ];
  return h("nav.ftree", { "aria-label": "Folders" },
    h("button.frow" + (!ui.folder ? ".on" : ""), { type: "button", onclick: () => { ui.folder = null; load(); } }, icon("grid"), h("span", {}, "All top-level files")),
    ...kids(null).flatMap((f) => item(f, 0)),
    button([icon("draft"), "New folder"], () => folderDialog(), "ghost sm"));
}

function folderDialog(f) {
  const name = h("input", { value: f ? f.name : "", placeholder: "Folder name", "aria-label": "Folder name" });
  const parent = h("select", { "aria-label": "Inside" }, h("option", { value: "" }, "Top level"),
    data.folders.filter((x) => !f || x.id !== f.id).map((x) => h("option", { value: x.id, selected: f ? x.id === f.parent_id : String(x.id) === String(ui.folder) }, x.path)));
  const dlg = modal(f ? `Folder ${f.name}` : "New folder", [h("label.field", {}, "Name", name), h("label.field", {}, "Inside", parent)], [
    f ? button("Delete folder", (e) => busy(e.target, async () => {
      let r = await del(`/api/folders/${f.id}`).catch((x) => x);
      if (r instanceof Error && r.status === 409) {
        if (!confirm(`${r.message}\n\nDelete the folder and everything in it?`)) return;
        r = await del(`/api/folders/${f.id}?confirm=true`);
      } else if (r instanceof Error) throw r;
      toast(`Deleted ${r.deleted_files} file(s), ${r.deleted_folders} folder(s)`, "ok");
      if (String(ui.folder) === String(f.id)) ui.folder = null;
      dlg.close(); load();
    }), "danger") : null,
    button("Cancel", () => dlg.close()),
    button(f ? "Save" : "Create", (e) => busy(e.target, async () => {
      const pid = parent.value ? +parent.value : null;
      if (f) await patch(`/api/folders/${f.id}`, { name: name.value, parent_id: pid });
      else { const r = await post("/api/folders", { name: name.value, parent_id: pid }); ui.folder = r.id; }
      dlg.close(); load();
    }), "primary"),
  ]);
  name.focus();
}

function fileDialog(f) {
  const name = h("input", { value: f.name, "aria-label": "Name" });
  const folder = h("select", { "aria-label": "Folder" }, h("option", { value: "" }, "Top level"),
    data.folders.map((x) => h("option", { value: x.id, selected: x.id === f.folder_id }, x.path)));
  const exp = expiryPicker("");
  exp.el.querySelector("select").prepend(h("option", { value: "", selected: true }, `Keep (${left(f.expires_at).text})`));
  const replaceIn = h("input", { type: "file", "aria-label": "Replace the content" });
  const dlg = modal(f.name, [
    h("label.field", {}, "Name", name), h("label.field", {}, "Folder", folder), h("label.field", {}, "Expires", exp.el),
    h("label.field", {}, "Replace the content (same link)", replaceIn),
    h("p.small.muted", {}, `${fmtBytes(f.size)} · ${f.mime} · uploaded ${f.created.slice(0, 16).replace("T", " ")} by ${f.who}`),
  ], [
    button("New link", (e) => busy(e.target, async () => {
      if (!confirm("Make a new link? The old link stops working at once.")) return;
      const r = await patch(`/api/files/${f.id}`, { new_link: true }); copy(r.url, "New link"); dlg.close(); load();
    }), "ghost"),
    button("Cancel", () => dlg.close()),
    button("Save", (e) => busy(e.target, async () => {
      const body = {};
      if (name.value !== f.name) body.name = name.value;
      const fid = folder.value ? +folder.value : null;
      if (fid !== (f.folder_id || null)) body.folder_id = fid;
      if (exp.value()) body.expiry = exp.value();
      if (Object.keys(body).length) await patch(`/api/files/${f.id}`, body);
      if (replaceIn.files[0]) {
        const fd = new FormData(); fd.append("file", replaceIn.files[0]);
        const r = await fetch(`/api/files/${f.id}/content`, { method: "PUT", body: fd, headers: { "x-csrf-token": state.csrf || "" }, credentials: "same-origin" });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
      }
      dlg.close(); load();
    }), "primary"),
  ]);
}

function row(f) {
  const t = left(f.expires_at);
  return h("div.fitem", {},
    h("div.fmain", {}, h("b", { title: f.name }, f.name),
      h("span.small.muted", {}, `${fmtBytes(f.size)} · ${f.mime}${ui.q ? ` · ${f.folder_path}` : ""}`)),
    h("span.pill." + (t.cls || "plain"), { title: f.expires_at ? `Expires ${new Date(f.expires_at).toLocaleString()}` : "" }, t.text),
    h("div.factions", {},
      button([icon("ext"), "Copy link"], () => copy(f.url), "sm"),
      h("a.btn.sm.ghost", { href: f.url, target: "_blank", rel: "noopener noreferrer", title: "Open the public link" }, "Open"),
      button([icon("pen")], () => fileDialog(f), "sm ghost", { title: "Rename, move, expiry, replace", "aria-label": `Edit ${f.name}` }),
      button("Delete", (e) => busy(e.target, async () => {
        if (!confirm(`Delete ${f.name}? Its link stops working.`)) return;
        await del(`/api/files/${f.id}`); toast(`Deleted ${f.name}`, "ok"); load();
      }), "sm danger")));
}

function draw() {
  const u = data.usage;
  const pct = Math.min(100, (100 * u.used) / u.quota);
  const exp = expiryPicker("7d");
  const input = h("input", { type: "file", multiple: true, hidden: true, onchange: (e) => upload(e.target.files, exp) });
  const drop = h("div.dropzone", { tabindex: 0, role: "button", "aria-label": "Choose files to upload",
    onclick: () => input.click(), onkeydown: (e) => (e.key === "Enter" || e.key === " ") && input.click(),
    ondragover: (e) => { e.preventDefault(); drop.classList.add("over"); }, ondragleave: () => drop.classList.remove("over"),
    ondrop: (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files, exp); } },
  icon("upload"), h("b", {}, "Drop files here"), h("span.small.muted", {}, "or click to choose · any type, up to 1 GB each"), input);
  const cur = data.folders.find((f) => String(f.id) === String(ui.folder));
  const q = h("input", { type: "search", placeholder: "Search every folder…", value: ui.q, "aria-label": "Search files",
    onkeydown: (e) => { if (e.key === "Enter") { ui.q = e.target.value.trim(); load(); } } });
  root$.replaceChildren(
    h("header.page", {}, h("h1", {}, "Files"),
      h("div.fusage", { title: `${fmtBytes(u.used)} of ${fmtBytes(u.quota)}` },
        h("div.fbar", { role: "meter", "aria-valuemin": 0, "aria-valuemax": u.quota, "aria-valuenow": u.used, "aria-label": "Storage used" },
          h("span", { style: { width: `${pct}%` }, class: pct > 90 ? "full" : "" })),
        h("span.small.muted", {}, `${fmtBytes(u.used)} of ${fmtBytes(u.quota)} · ${u.files} file(s)`),
        button("Quota", () => quotaDialog(), "ghost sm"))),
    h("p.small.muted", {}, "Anyone with a link can download that one file until it expires. Pictures, audio, video, PDF and text open in the browser; everything else downloads. Nothing here is listed publicly."),
    h("div.files", {}, tree(), h("section.fpane", {},
      h("div.toolbar", {}, h("div.search", {}, icon("search"), q),
        h("span.small.muted", {}, ui.q ? `Results for “${ui.q}”` : cur ? cur.path : "Top level"),
        cur ? button("Folder…", () => folderDialog(cur), "ghost sm") : null),
      h("div.files-up", {}, drop, h("div.row", { style: { marginTop: "8px" } }, h("span.small.muted", {}, "Expires after"), exp.el)),
      data.files.length ? h("div.flist", {}, data.files.map(row)) : h("p.muted", { style: { marginTop: "14px" } }, ui.q ? "No files match." : "No files here yet."))));
}

function quotaDialog() {
  const gb = h("input", { type: "number", min: 1, max: 2048, value: Math.round(data.usage.quota / 1024 ** 3), "aria-label": "Quota in GB" });
  const dlg = modal("Storage quota", [h("label.field", {}, "Total for all files (GB)", gb),
    h("p.small.muted", {}, `Disk free: ${fmtBytes(data.usage.disk_free)}.`)], [
    button("Cancel", () => dlg.close()),
    button("Save", (e) => busy(e.target, async () => { await post("/api/files/quota", { quota_gb: +gb.value }); dlg.close(); load(); }), "primary")]);
}

export async function render(root) {
  root$ = root;
  root.append(h("p.muted", {}, "Loading…"));
  await load();
}
