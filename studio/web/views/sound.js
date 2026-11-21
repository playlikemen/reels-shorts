// Sound: preview engine SFX packs, make a new cue with earshot from words, choose sfx_pack per brand.
import { h, api, post, button, busy, toast, followJob } from "../app.js";

let audio = null;
const play = (url) => { if (audio) audio.pause(); audio = new Audio(url); audio.play().catch((e) => toast(e.message, "error")); };

export async function render(root) {
  const d = await api("/api/sound");
  const packs = d.packs.map((p) => p.pack);
  root.append(h("header.page", {}, h("h1", {}, "Sound"), h("div.sub", {}, "Packs live in engine/sfx_bank/<pack>/<kind>_N.wav. A brand style uses one with \"sfx_pack\" in brand.json; re-render to hear it in a reel.")),
    ...d.packs.map((p) => h("div.panel", {}, h("h2", {}, `Pack: ${p.pack}`), h("p.small.muted", {}, `${p.files.length} files · ${p.kinds.join(", ")}`),
      h("div.sfx", {}, p.files.map((f) => button(`▶ ${f.replace(".wav", "")}`, () => play(`/sound/${p.pack}/${f}`), "sm"))))),
    d.packs.length ? null : h("div.panel", {}, h("p.muted", {}, "No packs in engine/sfx_bank yet.")),
    makePanel(d, packs),
    h("div.panel", {}, h("h2", {}, "Pack per brand style"),
      h("div.list", {}, d.brands.flatMap((b) => Object.entries(b.styles).map(([style, cur]) => {
        const sel = h("select", {}, h("option", { value: "" }, "engine default"), packs.map((p) => h("option", { value: p, selected: p === cur }, p)));
        const save = button("Save", (e) => busy(e.target, async () => { await post("/api/sound/brand", { brand: b.key, style, pack: sel.value }); toast(`${b.name} ${style}: ${sel.value || "default"}`, "ok"); }), "sm");
        return h("div", {}, h("b", {}, b.name), h("span.muted", {}, style), h("span.spacer"), sel, save);
      })))));
}

function makePanel(d, packs) {
  if (!d.earshot) return h("div.panel", {}, h("h2", {}, "Make a cue with earshot"), h("p.muted", {}, "earshot is not installed on this host."));
  const words = h("input", { placeholder: "a soft airy whoosh, short", style: { flex: "1" } });
  const pre = h("pre.log", { style: { maxHeight: "160px" } });
  const result = h("div.row");
  const go = button("Make", (e) => busy(e.target, async () => {
    const r = await post("/api/sound/make", { words: words.value });
    pre.textContent = ""; result.replaceChildren();
    await new Promise((res) => followJob(r.job, pre, (s) => {
      if (s.status === "done") {
        const pack = h("select", {}, packs.map((p) => h("option", { value: p }, p)));
        const name = h("input", { placeholder: "whoosh_2.wav", size: 14 });
        result.replaceChildren(button("▶ Play", () => play(r.url), "sm"), h("span", {}, "Replace in"), pack, name,
          button("Use this", (x) => busy(x.target, async () => { await post("/api/sound/use", { token: r.token, pack: pack.value, name: name.value.trim() }); toast("Replaced (old file kept in studio-sound/replaced)", "ok"); }), "sm primary"));
      } else toast(`earshot: ${s.status}`, "error");
      res();
    }));
  }), "primary");
  return h("div.panel", {}, h("h2", {}, "Make a cue with earshot"), h("div.row", {}, words, go), pre, result);
}
