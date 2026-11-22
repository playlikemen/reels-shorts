// One-click publishing: a two-step button (click, then "Confirm?" within 4 s) used on cards, table rows and the drawer.
// It posts through /api/publish (confirm + override_cap), so the server's checks and the scheduler lock still apply
// and a double post is impossible. Also: the schedule popover and Archive with Undo, shared by the Library and drawer.
import { h, api, post, toast, brandOf, button, busy, icon, loadReels, modal, fmtWhen, state, istNow } from "../app.js";

const NEVER = ["Published", "Publishing", "Archived", "No channel"];
export const pushable = (s) => !!(s || "").trim() && !NEVER.some((x) => (s || "").startsWith(x));
const COL = { instagram: "Instagram Status", youtube: "YouTube Status" };
const URLCOL = { instagram: "Instagram Post URL", youtube: "YouTube Shorts URL" };
const LABEL = { instagram: ["Publish to IG", "Publish to Instagram now"], youtube: ["Upload to YT", "Upload to YouTube now"] };

export function canPublish(r, platform) {
  const b = brandOf(r.brand);
  if (platform === "youtube" && !b.youtube) return false;
  return pushable(r[COL[platform]]) && !r.missing;
}

// Wait for a job to end over SSE; resolves {status, exit_code}.
function waitJob(jid, onLog) {
  return new Promise((resolve) => {
    const es = new EventSource(`/api/jobs/${jid}/stream`);
    if (onLog) es.addEventListener("log", (e) => onLog(JSON.parse(e.data)));
    es.addEventListener("end", (e) => { es.close(); resolve(JSON.parse(e.data)); });
  });
}

// The publish job prints one line per step; show the newest on the spinner.
const STEP = /^(the scheduler .*waiting|uploading video|Instagram container|publishing…|published |cancel noted)/;
function progressLine(text) {
  const lines = text.split("\n").map((l) => l.trim()).filter((l) => STEP.test(l));
  if (!lines.length) return "";
  const l = lines[lines.length - 1];
  if (l.startsWith("uploading")) return "Uploading video…";
  if (l.startsWith("Instagram container")) return "Instagram is processing…";
  if (l.startsWith("publishing")) return "Publishing…";
  if (l.startsWith("published")) return "Published";
  if (l.startsWith("cancel")) return "Finishing the post…";
  return "Waiting for the scheduler…";
}

function lastLines(text, n = 2) {
  return (text || "").trim().split("\n").filter((l) => l && !l.startsWith("{")).slice(-n).join(" · ").slice(0, 220);
}

// A reel stuck at "Publishing" (its job died): ask Instagram whether it went live.
export function checkButton(r, onDone) {
  const wrap = h("span.pub", { onclick: (e) => e.stopPropagation() });
  const b = h("button.btn.sm", { type: "button", title: "Look for this reel on Instagram and settle its status" }, icon("search"), "Check Instagram");
  b.onclick = () => busy(b, async () => {
    const res = await post(`/api/reels/${encodeURIComponent(r["Video ID"])}/check-instagram`, {}, { allow: [409] });
    if (res._status === 409) throw new Error(res.error || "refused");
    toast(`${r["Video ID"]}: ${res.result}`, res.result.startsWith("published") ? "ok" : "info", 7000);
    await loadReels(true);
    onDone && onDone(res.reel);
  });
  wrap.append(b);
  return wrap;
}

// The button. opts: {compact, onDone(reel)}. Returns an element that manages its own states.
export function publishButton(r, platform, opts = {}) {
  const b = brandOf(r.brand);
  const handle = platform === "instagram" ? b.instagram : b.youtube;
  const wrap = h("span.pub", { onclick: (e) => e.stopPropagation(), onkeydown: (e) => e.stopPropagation() });
  let timer = null;
  const idle = () => {
    clearTimeout(timer);
    const btn = h("button.btn.pubbtn" + (opts.compact ? ".sm" : ""), {
      type: "button", title: `${LABEL[platform][1]} on ${handle}`, onclick: () => arm(),
    }, icon("send"), opts.compact ? LABEL[platform][0] : LABEL[platform][1]);
    wrap.replaceChildren(btn);
    return btn;
  };
  const arm = () => {
    const btn = h("button.btn.pubbtn.armed" + (opts.compact ? ".sm" : ""), {
      type: "button", "aria-live": "polite", title: "Click again within 4 seconds to post publicly", onclick: () => go(),
    }, `Confirm? ${handle}`);
    wrap.replaceChildren(btn);
    btn.focus({ preventScroll: true });
    timer = setTimeout(idle, 4000);
  };
  const fail = (msg) => {
    wrap.replaceChildren(h("span.puberr", { role: "alert" }, icon("alert"), h("span", {}, msg)),
      h("button.btn.sm", { type: "button", onclick: () => arm() }, "Retry"));
  };
  const go = async () => {
    clearTimeout(timer);
    const label = h("span", {}, "Starting…");
    wrap.replaceChildren(h("span.pubbusy", { role: "status", "aria-live": "polite" }, h("span.spin"), label));
    let res;
    try {
      res = await post("/api/publish", { id: r["Video ID"], platform, confirm: true, override_cap: true }, { allow: [409] });
    } catch (e) { return fail(e.message); }
    if (res._status === 409) return fail(res.error || "refused");
    let log = "";
    const end = await waitJob(res.job, (chunk) => { log += chunk; const t = progressLine(log); if (t && label.textContent !== t) label.textContent = t; });
    let reel = null;
    try { reel = (await api(`/api/reels/${encodeURIComponent(r["Video ID"])}`)).reel; } catch { /* */ }
    const url = reel?.[URLCOL[platform]];
    if (url && (reel?.[COL[platform]] || "").startsWith("Published")) {
      wrap.replaceChildren(h("a.btn.sm.ok", { href: url, target: "_blank", rel: "noopener" }, icon("ext"), platform === "instagram" ? "Open IG" : "Open YT"));
      toast(`${r["Video ID"]} is live on ${handle}`, "ok", 6000);
      await loadReels(true);
      opts.onDone && opts.onDone(reel);
      return;
    }
    let why = reel?.[COL[platform]]?.startsWith("Failed") ? reel[COL[platform]] : "";
    if (!why) { try { why = lastLines((await api(`/api/jobs/${res.job}`)).log_tail); } catch { /* */ } }
    fail(why || `job ${end.status}`);
    await loadReels(true);
  };
  idle();
  return wrap;
}

// ---------- schedule popover ----------

const addDays = (d, n) => { const x = new Date(d + "T00:00:00Z"); x.setUTCDate(x.getUTCDate() + n); return x.toISOString().slice(0, 10); };

export function scheduleDialog(r, onDone) {
  const b = brandOf(r.brand);
  const slots = b.slots?.length ? b.slots : ["19:30"];
  const now = istNow();
  const cur = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(r["Scheduled Time (IST)"] || "") ? r["Scheduled Time (IST)"] : "";
  const input = h("input", { type: "datetime-local", value: (cur && cur > now ? cur : "").replace(" ", "T"), step: 60, "aria-label": "Date and time (IST)" });
  const auto = h("input", { type: "radio", name: "sched-mode", value: "auto", checked: true });
  const plan = h("input", { type: "radio", name: "sched-mode", value: "plan" });
  const set = (v) => { input.value = v.replace(" ", "T"); };
  const today = now.slice(0, 10), tomorrow = addDays(today, 1);
  const chip = (label, fn) => h("button.chip", { type: "button", onclick: fn }, label);
  const nextChip = chip("Next free slot", async (e) => {
    e.target.disabled = true;
    try { const s = await api(`/api/slots/next?brand=${r.brand}&exclude=${encodeURIComponent(r["Video ID"])}`); set(s.next); } catch (x) { toast(x.message, "error"); }
    e.target.disabled = false;
  });
  const lastSlot = slots[slots.length - 1], firstSlot = slots[0];
  const chips = h("div.chips.wrap", {}, nextChip,
    `${today} ${lastSlot}` > now ? chip(`Today ${lastSlot}`, () => set(`${today} ${lastSlot}`)) : null,
    chip(`Tomorrow ${firstSlot}`, () => set(`${tomorrow} ${firstSlot}`)),
    slots.length > 1 ? chip(`Tomorrow ${lastSlot}`, () => set(`${tomorrow} ${lastSlot}`)) : null);
  const pub = canPublish(r, "instagram") ? h("div.row", {}, h("span.small.muted", {}, "Or post right now:"), publishButton(r, "instagram", { compact: true, onDone: () => { dlg.close(); onDone && onDone(); } })) : null;
  const save = button("Save schedule", (e) => busy(e.target, async () => {
    const when = input.value.replace("T", " ").slice(0, 16);
    if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(when)) throw new Error("pick a date and time");
    const res = await post(`/api/reels/${encodeURIComponent(r["Video ID"])}/schedule`, { when, auto: auto.checked }, { allow: [202, 409] });
    if (res._status === 409) throw new Error(res.error || "changed in the Sheet meanwhile; reopen the reel");
    toast(res.status === "pending" ? "The Sheet did not answer; queued for the next sync" : `${r["Video ID"]} ${auto.checked ? "will post" : "planned"} ${fmtWhen(when)} IST`, res.status === "pending" ? "error" : "ok");
    dlg.close();
    await loadReels(true);
    onDone && onDone();
  }), "primary");
  const dlg = modal(`Schedule ${r["Video ID"]}`, [
    h("p.small.muted", {}, `${b.name}: slots ${slots.join(", ")} IST, at most ${b.cap || slots.length} a day.`),
    h("label.field", {}, "When (IST)", input), chips,
    h("fieldset.choice", {}, h("legend.small.muted", {}, "At that time"),
      h("label.check", {}, auto, h("span", {}, h("b", {}, "Auto-publish"), " · status Ready, cron posts it", b.auto_publish === false ? h("span.pill.failed", {}, "auto-publish is OFF for this channel") : null)),
      h("label.check", {}, plan, h("span", {}, h("b", {}, "Just plan it"), " · status Hold, nothing is posted"))),
    pub,
  ], [button("Cancel", () => dlg.close()), save]);
  return dlg;
}

// ---------- archive with Undo ----------

export async function archiveReel(r, archive, onDone) {
  const vid = r["Video ID"];
  const res = await post(`/api/reels/${encodeURIComponent(vid)}/archive`, { archive }, { allow: [202, 409] });
  if (res._status === 409) { toast(res.error || "changed in the Sheet meanwhile", "error", 7000); return; }
  await loadReels(true);
  onDone && onDone();
  undoToast(archive ? `${vid} archived${res.drive ? ` · ${res.drive}` : ""}` : `${vid} restored${res.note ? ` · ${res.note}` : ""}`,
    () => archiveReel(r, !archive, onDone));
}

export function undoToast(msg, undo, ms = 8000) {
  const t = h("div.toast.ok", { role: "status" }, h("span", {}, msg), h("button.linkbtn", { type: "button", onclick: () => { t.remove(); undo(); } }, "Undo"));
  document.querySelector("#toasts").append(t);
  setTimeout(() => t.classList.add("out"), ms);
  setTimeout(() => t.remove(), ms + 400);
}

export async function holdReel(r, hold, onDone) {
  const res = await post(`/api/reels/${encodeURIComponent(r["Video ID"])}/hold`, { hold }, { allow: [202, 409] });
  if (res._status === 409) { toast(res.error || "changed in the Sheet meanwhile", "error", 7000); return; }
  await loadReels(true);
  onDone && onDone();
  undoToast(`${r["Video ID"]} ${hold ? "held" : "back to Ready"}`, () => holdReel(r, !hold, onDone));
}

