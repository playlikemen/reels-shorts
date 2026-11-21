// Script studio (CraftLayer "3 problems" reels): form for brands/craftlayer/reel_schema.md, live checks, then
// generate the spec, preview stills, render and schedule, each as a job.
import { h, api, post, button, busy, toast, jobToast, modal } from "../app.js";

const words = (s) => (s || "").replace(/\*/g, "").split(/\s+/).filter(Boolean).length;
const lines = (s) => (s || "").split("\n").map((x) => x.trim()).filter(Boolean);
const cells = (l) => l.split("|").map((x) => x.trim());

let scripts = [];

export async function render(root) {
  const data = await api("/api/scripts");
  scripts = data.scripts;
  const pick = h("select", { onchange: (e) => { const s = scripts.find((x) => `${x.file}#${x.id}` === e.target.value); if (s) fill(form, s.script); check(); } },
    h("option", { value: "" }, "Load an existing script…"), scripts.map((s) => h("option", { value: `${s.file}#${s.id}` }, `${s.id} · ${s.topic}`)));
  const form = buildForm();
  const checks = h("div.panel.checks", {}, h("h2", {}, "Checks"), h("div#chk", {}, "Fill the form."));
  let t = null;
  const check = () => { clearTimeout(t); t = setTimeout(async () => {
    const res = await post("/api/scripts/check", { script: collect(form) }).catch((e) => ({ errors: [e.message], words: 0, parts: [] }));
    const box = checks.querySelector("#chk");
    box.replaceChildren(
      h("div.stat", {}, h("span.muted.small", {}, "Spoken words (110 to 140)"), h("b", { style: { color: res.words >= 110 && res.words <= 140 ? "var(--ok)" : "var(--warn)" } }, res.words)),
      res.errors.length ? h("ul", {}, res.errors.map((e) => h("li", { style: { color: "var(--bad)" } }, e))) : h("p", { style: { color: "var(--ok)" } }, "Generator checks pass."),
      (res.warnings || []).map((w) => h("p.small.muted", {}, w)),
      h("div.list", {}, (res.parts || []).map((p) => h("div", {}, h("span", {}, p.part), h("span.spacer"), h("span", { style: { color: p.over ? "var(--bad)" : "" } }, `${p.words} words`)))));
  }, 350); };
  form.addEventListener("input", (e) => { const wc = e.target.closest("label")?.querySelector(".wc"); if (wc) { const n = words(e.target.value); wc.textContent = `${n} words`; wc.classList.toggle("over", n > 20); } check(); });

  const tomorrow = new Date(Date.now() + 864e5 + 5.5 * 36e5).toISOString().slice(0, 10);
  const start = h("input", { placeholder: "YYYY-MM-DD HH:MM", size: 16, value: `${tomorrow} 19:30` });
  const id = () => collect(form).id;
  const spec = () => `specs/craftlayer/${id()}.json`;
  const actions = h("div.panel", {}, h("h2", {}, "Steps"),
    h("div", { style: { display: "grid", gap: "8px" } },
      h("label.field", {}, "Slot for this reel (IST)", start),
      button("1 · Save and generate spec", (e) => busy(e.target, async () => {
        const other = scripts.find((x) => x.id === id() && !x.file.endsWith("/studio.json"));
        if (other && !confirm(`${id()} already exists in ${other.file}. Generating rewrites specs/craftlayer/${id()}.json with the slot above. Continue?`)) return;
        const s = await post("/api/scripts/save", { script: collect(form) }, { allow: [422] });
        if (s._status === 422) return toast(s.error, "error", 8000);
        const r = await post("/api/jobs", { kind: "generate", params: { files: [s.file], start: start.value, id: id() } });
        jobToast(r.job, `Generate ${id()}`);
      }), "primary"),
      button("2 · Preview stills", (e) => busy(e.target, async () => {
        const r = await post("/api/jobs", { kind: "render", params: { spec: spec(), lang: "en", mode: "stills", stills: "0.3,5,11,17,23,29,35", id: `${id()}-EN` } });
        jobToast(r.job, `Stills ${id()}`, (st) => st.status === "done" && (location.hash = `#/library/${id()}-EN`));
      })),
      button("3 · Render and verify", (e) => busy(e.target, async () => {
        const r = await post("/api/jobs", { kind: "render", params: { spec: spec(), lang: "en", mode: "full", id: `${id()}-EN` } });
        jobToast(r.job, `Render ${id()}`); location.hash = `#/jobs/${r.job}`;
      })),
      button("4 · Schedule (Drive + Sheet row, Ready)", () => {
        const dlg = modal(`Schedule ${id()}-EN`, [h("p", {}, `Uploads out/craftlayer/${id()}-EN to Drive and adds the Sheet row with status Ready at the spec's slot. Cron posts it when due.`)],
          [button("Cancel", () => dlg.close()), button("Schedule", (e) => busy(e.target, async () => {
            const r = await post("/api/jobs", { kind: "sync", params: { spec: spec(), lang: "en", id: `${id()}-EN` } });
            dlg.close(); jobToast(r.job, `Schedule ${id()}`);
          }), "primary")]);
      }),
      h("p.small.muted", {}, "Stills appear in the reel's drawer once rendered (Library → the reel).")));
  root.append(h("header.page", {}, h("h1", {}, "Script studio"), pick, h("div.sub", {}, "CraftLayer · 3 problems, 3 fixes, one CTA keyword. Rules: brands/craftlayer/reel_schema.md.")),
    h("div.script-layout", {}, form, h("div", { style: { display: "grid", gap: "16px" } }, checks, actions)));
  check();
}

const F = (label, name, kind = "input", extra = {}) => {
  const el = kind === "textarea" ? h("textarea", { name, rows: extra.rows || 2, placeholder: extra.ph || "" }) : h("input", { name, placeholder: extra.ph || "" });
  return h("label.field", {}, label, el, extra.wc ? h("div.wc", {}, "0 words") : null);
};

function buildForm() {
  const prob = (i) => h("fieldset", {}, h("legend", {}, `Problem ${i + 1}`),
    F("Problem say (≤ 20 words)", `p${i}.say`, "textarea", { wc: true }),
    h("div.two", {}, F("Screen", `p${i}.screen`, "input", { ph: "chat or rows" }), F("Screen title (one *accent*)", `p${i}.head`)),
    F("Chat messages (one per line, start with 'me:' for the owner)", `p${i}.chat`, "textarea", { rows: 3 }),
    F("Rows (t | s | v | icon | bad)", `p${i}.rows`, "textarea", { rows: 3, ph: "Unknown number | 9:12 PM · missed | | phone | bad" }),
    F("Chip", `p${i}.chip`),
    h("h3", {}, "Fix"),
    F("Fix say (≤ 20 words)", `p${i}.fix.say`, "textarea", { wc: true }),
    h("div.two", {}, F("Fix title", `p${i}.fix.head`), F("Fix subtitle", `p${i}.fix.sub`)),
    F("Fix rows (t | s | v | icon)", `p${i}.fix.rows`, "textarea", { rows: 3 }),
    h("div.two", {}, F("Button", `p${i}.fix.btn`), F("Chip", `p${i}.fix.chip`)));
  return h("form.script-form", { onsubmit: (e) => e.preventDefault() },
    h("fieldset", {}, h("legend", {}, "Reel"),
      h("div.two", {}, F("ID", "id", "input", { ph: "CR-135" }), F("Topic", "topic", "input", { ph: "Clinics: 3 problems" })),
      h("div.two", {}, F("Audience (lower case)", "audience"), F("Keyword (≤ 8 caps)", "keyword")),
      h("div.two", {}, F("Demo name (fictional)", "demo_name"), F("Domain", "domain")),
      F("Sources (one URL per line)", "sources", "textarea")),
    h("fieldset", {}, h("legend", {}, "Hook"),
      F("Hook say", "hook.say", "textarea", { wc: true }), F("Title (\\n for a line break, *accent*)", "hook.title"),
      h("div.two", {}, F("Tile 1 (icon | label)", "hook.t0", "input", { ph: "users | Your clinic" }), F("Tile 2 (icon | label | hot)", "hook.t1", "input", { ph: "cal | Next door | hot" }))),
    [0, 1, 2].map(prob),
    h("fieldset", {}, h("legend", {}, "Recap and CTA"),
      F("Recap say", "recap_say", "textarea", { wc: true }), F("Recap items (t | s, three lines)", "recap", "textarea", { rows: 3 }),
      F("CTA say", "cta_say", "textarea", { wc: true })),
    h("fieldset", {}, h("legend", {}, "Caption"),
      F("Instagram caption", "caption", "textarea", { rows: 8 }), F("Hashtags (space separated, last #craftlayer)", "hashtags"), F("YouTube tags (comma separated)", "tags")));
}

const val = (form, n) => form.querySelector(`[name="${n}"]`)?.value ?? "";
const set = (form, n, v) => { const el = form.querySelector(`[name="${n}"]`); if (el) el.value = v ?? ""; };

function collect(form) {
  const tile = (s) => { const c = cells(s); return { ic: c[0] || "users", label: c[1] || "", ...(c[2] === "hot" ? { hot: true } : {}) }; };
  const rows = (s, bad) => lines(s).map((l) => { const c = cells(l); return { t: c[0] || "", ...(c[1] ? { s: c[1] } : {}), ...(c[2] ? { v: c[2] } : {}), ...(c[3] ? { ic: c[3] } : {}), ...(bad && c[4] === "bad" ? { bad: true } : {}) }; });
  const prob = (i) => {
    const p = { say: val(form, `p${i}.say`), screen: val(form, `p${i}.screen`) || "rows", head: val(form, `p${i}.head`) };
    if (p.screen === "chat") p.chat = lines(val(form, `p${i}.chat`)).map((l) => (l.startsWith("me:") ? { t: l.slice(3).trim(), me: true } : { t: l }));
    else p.rows = rows(val(form, `p${i}.rows`), true);
    if (val(form, `p${i}.chip`)) p.chip = val(form, `p${i}.chip`);
    p.fix = { say: val(form, `p${i}.fix.say`), head: val(form, `p${i}.fix.head`) };
    for (const k of ["sub", "btn", "chip"]) if (val(form, `p${i}.fix.${k}`)) p.fix[k] = val(form, `p${i}.fix.${k}`);
    p.fix.rows = rows(val(form, `p${i}.fix.rows`));
    return p;
  };
  return {
    id: val(form, "id").trim(), topic: val(form, "topic"), audience: val(form, "audience"), demo_name: val(form, "demo_name"), domain: val(form, "domain"),
    keyword: val(form, "keyword").trim(), sources: lines(val(form, "sources")),
    hook: { say: val(form, "hook.say"), title: val(form, "hook.title").replace(/\\n/g, "\n"), tiles: [tile(val(form, "hook.t0")), tile(val(form, "hook.t1"))] },
    problems: [0, 1, 2].map(prob), recap_say: val(form, "recap_say"),
    recap: lines(val(form, "recap")).map((l) => { const c = cells(l); return { t: c[0], ...(c[1] ? { s: c[1] } : {}) }; }),
    cta_say: val(form, "cta_say"), caption: val(form, "caption"),
    hashtags: val(form, "hashtags").split(/\s+/).filter(Boolean), tags: val(form, "tags").split(",").map((s) => s.trim()).filter(Boolean),
  };
}

function fill(form, s) {
  for (const k of ["id", "topic", "audience", "demo_name", "domain", "keyword", "recap_say", "cta_say", "caption"]) set(form, k, s[k]);
  set(form, "sources", (s.sources || []).join("\n"));
  set(form, "hook.say", s.hook?.say); set(form, "hook.title", (s.hook?.title || "").replace(/\n/g, "\\n"));
  (s.hook?.tiles || []).slice(0, 2).forEach((t, i) => set(form, `hook.t${i}`, [t.ic, t.label, t.hot ? "hot" : ""].filter((x, j) => x || j < 2).join(" | ")));
  const rowTxt = (rs, bad) => (rs || []).map((r) => [r.t, r.s || "", r.v || "", r.ic || "", bad && r.bad ? "bad" : ""].join(" | ").replace(/( \| )+$/, "")).join("\n");
  (s.problems || []).forEach((p, i) => {
    set(form, `p${i}.say`, p.say); set(form, `p${i}.screen`, p.screen); set(form, `p${i}.head`, p.head); set(form, `p${i}.chip`, p.chip);
    set(form, `p${i}.chat`, (p.chat || []).map((m) => (m.me ? "me: " : "") + m.t).join("\n"));
    set(form, `p${i}.rows`, rowTxt(p.rows, true));
    for (const k of ["say", "head", "sub", "btn", "chip"]) set(form, `p${i}.fix.${k}`, p.fix?.[k]);
    set(form, `p${i}.fix.rows`, rowTxt(p.fix?.rows));
  });
  set(form, "recap", (s.recap || []).map((r) => [r.t, r.s || ""].join(" | ")).join("\n"));
  set(form, "hashtags", (s.hashtags || []).join(" ")); set(form, "tags", (s.tags || []).join(", "));
  form.querySelectorAll("textarea").forEach((t) => t.dispatchEvent(new Event("input", { bubbles: true })));
}
