// Board: kanban by Instagram status. Hold and unhold in one click.
import { h, post, state, loadReels, brandDot, button, busy, toast, fmtWhen, short, statusKind } from "../app.js";
import { openReel } from "./reel.js";

const COLS = [["ready", "Ready"], ["hold", "Hold"], ["published", "Published"], ["failed", "Failed / manual"]];

export async function render(root) {
  await loadReels(true);
  const brand = h("select", { onchange: () => draw() }, h("option", { value: "" }, "All brands"), state.brands.map((b) => h("option", { value: b.key, selected: state.channel === b.key }, b.name)));
  const body = h("div.board");
  root.append(h("header.page", {}, h("h1", {}, "Board"), brand, h("div.sub", {}, "By Instagram status. Rows in Publishing or other states are in the Library.")), body);
  const draw = () => {
    const reels = state.reels.reels.filter((r) => !brand.value || r.brand === brand.value);
    body.replaceChildren(...COLS.map(([k, label]) => {
      const list = reels.filter((r) => statusKind(r["Instagram Status"]) === k).sort((a, b) => (k === "published" ? -1 : 1) * a["Scheduled Time (IST)"].localeCompare(b["Scheduled Time (IST)"]));
      return h("section.col", {}, h("header", {}, label, h("span.count", {}, list.length)), list.map((r) => card(r, k, draw)));
    }));
  };
  draw();
}

function card(r, k, draw) {
  const act = k === "ready" || k === "hold" ? button(k === "ready" ? "Hold" : "Unhold", (e) => { e.stopPropagation(); busy(e.target, async () => {
    const res = await post(`/api/reels/${r["Video ID"]}/hold`, { hold: k === "ready" }, { allow: [202, 409] });
    if (res._status === 409) return toast(res.error || "The Sheet changed meanwhile; open the reel", "error");
    toast(`${r["Video ID"]}: ${k === "ready" ? "held" : "ready"}${res.status === "pending" ? " (queued)" : ""}`, res.status === "pending" ? "error" : "ok");
    await loadReels(true); draw();
  }); }, "sm") : null;
  return h("div.bcard", { onclick: () => openReel(r["Video ID"], draw) },
    h("img", { src: `/thumb/${r["Video ID"]}.jpg`, loading: "lazy", alt: "" }),
    h("div", {}, h("div.row", { style: { marginTop: 0 } }, brandDot(r.brand), h("b", {}, r["Video ID"])), h("div.t", {}, short(r["Category / Topic"], 70)),
      h("div.row", {}, h("span.small.muted", {}, fmtWhen(r["Scheduled Time (IST)"])), h("span.spacer"), act),
      k === "failed" ? h("div.small", { style: { color: "var(--bad)" } }, short(r["Instagram Status"], 90)) : null));
}
