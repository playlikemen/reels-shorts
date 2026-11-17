// reelkit.js: shared helpers for 1080x1920 vertical canvas reels (Instagram Reels & YouTube Shorts)
const W = 1080, H = 1920, FPS = 30;
const cv = document.querySelector('canvas'), ctx = cv.getContext('2d');
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
const prog = (t, start, dur) => clamp((t - start) / dur);

const E = {
  out: x => 1 - Math.pow(1 - x, 3),
  in: x => x * x * x,
  inOut: x => (x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  back: x => { const c = 1.70158; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); },
  elastic: x => {
    if (x === 0 || x === 1) return x;
    return Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1;
  }
};

let GA = 1;
const setA = a => { ctx.globalAlpha = clamp(GA * a); };

function scene(t, a, b, fn, fin = .25, fout = .2) {
  if (t < a || t >= b) return;
  const alpha = Math.min(prog(t, a, fin), 1 - prog(t, b - fout, fout));
  const prev = GA; GA = prev * alpha; ctx.save(); fn(t - a, b - a); ctx.restore(); GA = prev; ctx.globalAlpha = 1;
}

function txt(s, x, y, o = {}) {
  const { px = 64, fam = 'Inter', wt = 700, fill = '#fff', align = 'center', alpha = 1, ls = 0 } = o;
  ctx.font = `${wt} ${px}px "${fam}", -apple-system, sans-serif`;
  ctx.textAlign = align;
  ctx.textBaseline = 'alphabetic';
  ctx.letterSpacing = ls + 'px';
  ctx.fillStyle = fill;
  setA(alpha);
  ctx.fillText(s, x, y);
  ctx.letterSpacing = '0px';
}

function rise(s, x, y, p, o = {}) {
  if (p <= 0) return;
  const e = E.out(p);
  txt(s, x, y + (1 - e) * 46, { ...o, alpha: (o.alpha ?? 1) * e });
}

function measure(s, px, fam = 'Inter', wt = 700) {
  ctx.font = `${wt} ${px}px "${fam}", sans-serif`;
  return ctx.measureText(s).width;
}

function wrap(s, maxW, px, fam = 'Inter', wt = 700) {
  ctx.font = `${wt} ${px}px "${fam}", sans-serif`;
  const lines = []; let cur = '';
  for (const w of s.split(' ')) {
    const next = cur ? cur + ' ' + w : w;
    if (ctx.measureText(next).width > maxW && cur) {
      lines.push(cur); cur = w;
    } else cur = next;
  }
  if (cur) lines.push(cur);
  return lines;
}

function rr(x, y, w, h, r, fill, stroke, lw = 3, alpha = 1) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  setA(alpha);
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.stroke(); }
}

function glow(color, blur = 24) {
  ctx.shadowColor = color;
  ctx.shadowBlur = blur;
}
function noGlow() {
  ctx.shadowColor = 'transparent';
  ctx.shadowBlur = 0;
}

function card(x, y, w, h, o = {}) {
  const { r = 24, bg = 'rgba(18, 24, 38, 0.85)', border = 'rgba(56, 189, 248, 0.25)', lw = 2, glowColor = null, glowBlur = 20, alpha = 1 } = o;
  if (glowColor) glow(glowColor, glowBlur);
  rr(x, y, w, h, r, bg, border, lw, alpha);
  noGlow();
}

function badge(s, cx, cy, o = {}) {
  const { px = 32, bg = 'rgba(56, 189, 248, 0.15)', border = '#38bdf8', fill = '#38bdf8', fam = 'JetBrains Mono', wt = 700, alpha = 1 } = o;
  const padX = 28, padY = 14;
  ctx.font = `${wt} ${px}px "${fam}"`;
  const tw = ctx.measureText(s).width;
  const bw = tw + padX * 2, bh = px + padY * 2;
  rr(cx - bw / 2, cy - bh / 2, bw, bh, bh / 2, bg, border, 2, alpha);
  txt(s, cx, cy + px * 0.35, { px, fam, wt, fill, align: 'center', alpha });
}

function techGrid(t, o = {}) {
  const { size = 80, color = 'rgba(255, 255, 255, 0.03)', accent = 'rgba(56, 189, 248, 0.05)' } = o;
  ctx.save();
  ctx.lineWidth = 1;
  ctx.strokeStyle = color;
  for (let x = 0; x < W; x += size) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  for (let y = 0; y < H; y += size) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }
  // Subtle moving scanning beam
  const beamY = ((t * 180) % (H + 400)) - 200;
  const grad = ctx.createLinearGradient(0, beamY - 100, 0, beamY + 100);
  grad.addColorStop(0, 'rgba(56, 189, 248, 0)');
  grad.addColorStop(0.5, accent);
  grad.addColorStop(1, 'rgba(56, 189, 248, 0)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, beamY - 100, W, 200);
  ctx.restore();
}

function bar(label, valText, pct, x, y, w, h, o = {}) {
  const { p = 1, fill = '#38bdf8', bg = 'rgba(255,255,255,0.06)', alpha = 1 } = o;
  txt(label, x, y - 14, { px: 32, fam: 'JetBrains Mono', wt: 600, fill: '#94a3b8', align: 'left', alpha });
  txt(valText, x + w, y - 14, { px: 34, fam: 'JetBrains Mono', wt: 700, fill, align: 'right', alpha });
  rr(x, y, w, h, h / 2, bg, null, 0, alpha);
  const fillW = Math.max(h, w * clamp(pct) * E.out(clamp(p)));
  rr(x, y, fillW, h, h / 2, fill, null, 0, alpha);
}

function check(cx, cy, size, p, color = '#10b981', lw = 9) {
  if (p <= 0) return;
  const pts = [[-.5, 0], [-.12, .36], [.5, -.34]].map(([a, b]) => [cx + a * size, cy + b * size]);
  ctx.beginPath(); ctx.moveTo(...pts[0]);
  const p1 = clamp(p / .4), p2 = clamp((p - .4) / .6);
  ctx.lineTo(lerp(pts[0][0], pts[1][0], p1), lerp(pts[0][1], pts[1][1], p1));
  if (p2 > 0) ctx.lineTo(lerp(pts[1][0], pts[2][0], p2), lerp(pts[1][1], pts[2][1], p2));
  ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; setA(1); ctx.stroke();
}

function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = Math.imul(s ^ (s >>> 15), 2246822507) + 0x9e3779b9 | 0), ((s ^ (s >>> 13)) >>> 0) / 4294967296);
}

// Code-made electronic synth soundtrack: kick, hat, sub bass, tech synth arp
function buildScore(ac, { bpm = 124, dur, root = 45, chords = [0, 0, 5, 3], minor = true, kickFrom = 0, level = 1, hits = [] }) {
  const beat = 60 / bpm, f = m => 440 * Math.pow(2, (m - 69) / 12);
  const master = ac.createGain(); master.connect(ac.destination);
  master.gain.setValueAtTime(0, 0); master.gain.linearRampToValueAtTime(.8 * level, .5);
  master.gain.setValueAtTime(.8 * level, dur - 1.3); master.gain.linearRampToValueAtTime(0, dur);
  const r = rng(11), noise = ac.createBuffer(1, ac.sampleRate, ac.sampleRate), nd = noise.getChannelData(0);
  for (let i = 0; i < nd.length; i++) nd[i] = r() * 2 - 1;
  const env = (t, peak, decay) => {
    const g = ac.createGain(); g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(peak, t + .006);
    g.gain.exponentialRampToValueAtTime(.0008, t + decay);
    g.connect(master); return g;
  };
  const osc = (type, freq, t, decay, peak, lp) => {
    const o = ac.createOscillator(); o.type = type; o.frequency.setValueAtTime(freq, t); let node = o;
    if (lp) { const fl = ac.createBiquadFilter(); fl.type = 'lowpass'; fl.frequency.value = lp; o.connect(fl); node = fl; }
    node.connect(env(t, peak, decay)); o.start(t); o.stop(t + decay + .05); return o;
  };
  const tri = minor ? [0, 3, 7, 12] : [0, 4, 7, 12], beats = Math.floor(dur / beat);
  for (let i = 0; i < beats; i++) {
    const t = i * beat, ch = root + chords[Math.floor(i / 4) % chords.length];
    if (t >= kickFrom) {
      const k = osc('sine', 160, t, .22, .95); k.frequency.exponentialRampToValueAtTime(42, t + .12);
      const h = ac.createBufferSource(); h.buffer = noise; const hp = ac.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 8000;
      h.connect(hp); hp.connect(env(t + beat / 2, .12, .05)); h.start(t + beat / 2); h.stop(t + beat / 2 + .1);
    }
    for (let e = 0; e < 2; e++) {
      const te = t + e * beat / 2;
      osc('sawtooth', f(ch - 12), te, .22, .22, 450);
      osc('triangle', f(ch + 12 + tri[(i * 2 + e) % 4]), te, .28, .14);
    }
  }
  for (const t of hits) {
    const n = ac.createBufferSource(); n.buffer = noise; const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.setValueAtTime(2600, t); lp.frequency.exponentialRampToValueAtTime(180, t + .5);
    n.connect(lp); lp.connect(env(t, .32, .55)); n.start(t); n.stop(t + .6);
    const s = osc('sine', 95, t, .5, .55); s.frequency.exponentialRampToValueAtTime(36, t + .4);
  }
}

function startReel(frames, draw) {
  window.FRAMES = frames; window.FPS = FPS;
  window.draw = fr => {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    GA = 1;
    ctx.clearRect(0, 0, W, H);
    draw(fr / FPS);
  };
  if (!location.search.includes('render')) {
    const t0 = performance.now();
    const loop = () => {
      window.draw(Math.floor(((performance.now() - t0) / 1000 * FPS) % frames));
      requestAnimationFrame(loop);
    };
    loop();
  } else {
    window.draw(0);
  }
}
