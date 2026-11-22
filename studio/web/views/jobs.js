// Jobs: start renders, syncs, generators, insights and snapshots; watch the live log; cancel; history.
import { h, api, post, state, button, busy, toast, followJob, ago, modal } from "../app.js";

let es = null;

export async function render(root, ctx) {
  const list = h("div.joblist");
  const pane = h("div.panel", {}, h("div.empty", {}, "Pick a job to see its log."));
  root.append(h("header.page", {}, h("h1", {}, "Jobs"), button("New job", () => newJob(), "primary"),
    h("div.sub", {}, "Two run at a time. Logs stream live.")), h("div.jobs-layout", {}, h("div", {}, list), pane));
  const refresh = async () => {
    const { jobs } = await api("/api/jobs?limit=80");
    list.replaceChildren(...(jobs.length ? jobs.map((j) => h("div.job", { class: String(j.id) === ctx.params[0] ? "on" : "", onclick: () => { location.hash = `#/jobs/${j.id}`; } },
      h("span.t", {}, `#${j.id} ${j.title}`), statusPill(j.status), h("span.s", {}, `${j.kind} · ${j.who} · ${ago(j.created)}`))) : [h("div.empty", {}, "No jobs yet.")]));
  };
  await refresh();
  const timer = setInterval(() => { if (!document.body.contains(list)) return clearInterval(timer); refresh(); }, 5000);
  if (ctx.params[0]) show(+ctx.params[0], pane, refresh);
}

function statusPill(s) {
  const k = { done: "published", running: "busy", queued: "hold", failed: "failed", cancelled: "muted", interrupted: "warn" }[s] || "muted";
  return h("span.pill." + k, {}, h("b", {}, s));
}

async function show(jid, pane, refresh) {
  if (es) es.close();
  const j = await api(`/api/jobs/${jid}`);
  const pre = h("pre.log");
  const st = h("span", {}, statusPill(j.status));
  const cancel = ["queued", "running"].includes(j.status) ? button("Cancel", (e) => busy(e.target, async () => { await post(`/api/jobs/${jid}/cancel`); toast("Cancel sent"); }), "sm danger") : null;
  pane.replaceChildren(h("div.row", { style: { marginBottom: "10px" } }, h("h2", {}, `#${j.id} ${j.title}`), st, h("span.spacer"), cancel),
    h("p.small.muted", {}, `${j.kind} · by ${j.who} · created ${j.created}${j.started ? ` · started ${j.started.slice(11)}` : ""}${j.ended ? ` · ended ${j.ended.slice(11)}` : ""}${j.exit_code != null ? ` · exit ${j.exit_code}` : ""}`), pre);
  if (["queued", "running"].includes(j.status)) {
    es = followJob(jid, pre, (s) => { st.replaceChildren(statusPill(s.status)); cancel?.remove(); refresh(); });
  } else pre.textContent = j.log_tail || "(empty log)";
}

export function newJob(preset = {}) {
  const kinds = {
    render: "Render (no sync)", rerender: "Re-render with the brand's SFX pack", sync: "Sync: Drive + Sheet row", generate: "Generate specs from scripts",
    insights: "Fetch insights", push: "Mirror to the Sheet", snapshot: "Snapshot every tab", dryrun: "Scheduler dry run",
  };
  const kind = h("select", {}, Object.entries(kinds).map(([k, l]) => h("option", { value: k, selected: preset.kind === k }, l)));
  const fields = h("div", { style: { display: "grid", gap: "10px" } });
  const inp = {};
  const field = (name, label, el) => { inp[name] = el; return h("label.field", {}, label, el); };
  const draw = () => {
    const k = kind.value; const f = [];
    if (["render", "rerender", "sync"].includes(k)) {
      f.push(field("spec", "Spec file", h("input", { value: preset.spec || "", placeholder: "specs/craftlayer/CR-110.json" })));
      f.push(field("lang", "Language (bilingual specs)", h("input", { value: preset.lang || "", placeholder: "en, hi or empty" })));
      if (k !== "sync") {
        f.push(field("mode", "Mode", h("select", {}, [["full", "Full render + verify"], ["stills", "Preview stills only"], ["only", "Only some scenes"]].map(([v, l]) => h("option", { value: v, selected: preset.mode === v }, l)))));
        f.push(field("stills", "Stills (seconds)", h("input", { value: "0.3,7,14,21,28" })));
        f.push(field("only", "Scenes (for 'only')", h("input", { placeholder: "0,3" })));
      } else f.push(h("p.small.muted", {}, "Uploads the render to a new Drive folder and writes the Sheet row with status Ready. Cron posts it when due."));
    }
    if (k === "generate") {
      f.push(field("files", "Script files (comma separated)", h("input", { value: preset.files || "brands/craftlayer/scripts/studio.json" })));
      f.push(field("start", "First slot (IST)", h("input", { value: preset.start || "", placeholder: "YYYY-MM-DD HH:MM" })));
    }
    if (k === "insights") {
      f.push(field("brand", "Brand", h("select", {}, state.brands.map((b) => h("option", { value: b.key }, b.name)))));
      f.push(h("label.check", {}, (inp.sheet = h("input", { type: "checkbox" })), h("span", {}, "Also write the brand's insights tab in the Sheet")));
    }
    fields.replaceChildren(...f);
  };
  kind.addEventListener("change", draw); draw();
  const dlg = modal("New job", [h("label.field", {}, "Kind", kind), fields], [button("Cancel", () => dlg.close()), button("Start", (e) => busy(e.target, async () => {
    const p = {};
    for (const [k, el] of Object.entries(inp)) if (document.body.contains(el)) p[k] = el.type === "checkbox" ? el.checked : el.value.trim();
    if (p.files) p.files = p.files.split(",").map((s) => s.trim()).filter(Boolean);
    const r = await post("/api/jobs", { kind: kind.value, params: p });
    dlg.close(); location.hash = `#/jobs/${r.job}`;
  }), "primary")]);
}
