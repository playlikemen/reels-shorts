// reelkit.js: Ultra-high quality motion graphics & retention grammar for 9:16 vertical video
// Built from tiktok-video-skills (short-form-video, caption-animation, lower-thirds, countdown-video)

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
  },
  pop: x => {
    // Punchy spring pop from caption-animation skill
    const p = clamp(x);
    if (p <= 0) return 0;
    return 1 + Math.sin(p * Math.PI) * 0.22 * Math.exp(-p * 3.5);
  }
};

let GA = 1;
const setA = a => { ctx.globalAlpha = clamp(GA * a); };

function scene(t, a, b, fn, fin = .25, fout = .2) {
  if (t < a || t >= b) return;
  const alpha = Math.min(prog(t, a, fin), 1 - prog(t, b - fout, fout));
  const prev = GA; GA = prev * alpha; ctx.save(); fn(t - a, b - a); ctx.restore(); GA = prev; ctx.globalAlpha = 1;
}

// ==========================================
// 1. TYPOGRAPHY & TEXT HELPERS
// ==========================================

function txt(s, x, y, o = {}) {
  const { px = 64, fam = 'Inter', wt = 900, fill = '#fff', stroke = null, strokeW = 0, align = 'center', alpha = 1, ls = 0 } = o;
  ctx.font = `${wt} ${px}px "${fam}", -apple-system, sans-serif`;
  ctx.textAlign = align;
  ctx.textBaseline = 'alphabetic';
  ctx.letterSpacing = ls + 'px';
  setA(alpha);
  if (stroke && strokeW > 0) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = strokeW;
    ctx.lineJoin = 'round';
    ctx.miterLimit = 2;
    ctx.strokeText(s, x, y);
  }
  ctx.fillStyle = fill;
  ctx.fillText(s, x, y);
  ctx.letterSpacing = '0px';
}

function rise(s, x, y, p, o = {}) {
  if (p <= 0) return;
  const e = E.out(p);
  txt(s, x, y + (1 - e) * 48, { ...o, alpha: (o.alpha ?? 1) * e });
}

function rr(x, y, w, h, r, fill, stroke, lw = 3, alpha = 1) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  setA(alpha);
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.stroke(); }
}

function glow(color, blur = 28) {
  ctx.shadowColor = color;
  ctx.shadowBlur = blur;
}
function noGlow() {
  ctx.shadowColor = 'transparent';
  ctx.shadowBlur = 0;
}

// ==========================================
// 2. PATTERN INTERRUPTS & CAMERA PUNCH
// (from short-form-video skill)
// ==========================================

function applyZoomPunch(t, hitTimes = [], punchScale = 1.07) {
  let scale = 1.0;
  for (const hit of hitTimes) {
    if (t >= hit && t < hit + 0.35) {
      const dt = t - hit;
      const p = dt / 0.35;
      // Instant snap on frame 0, smooth decay back to 1.0
      scale = 1.0 + (punchScale - 1.0) * Math.exp(-p * 7);
      break;
    }
  }
  if (scale !== 1.0) {
    ctx.translate(W / 2, H * 0.45);
    ctx.scale(scale, scale);
    ctx.translate(-W / 2, -H * 0.45);
  }
}

// ==========================================
// 3. HORMOZI KINETIC CAPTIONS
// (from caption-animation skill)
// ==========================================

function drawKineticCaptions(t, captionData, o = {}) {
  if (!captionData || !captionData.pages) return;
  const {
    cy = 1380,
    fontFamily = 'Inter',
    fontSize = 58,
    activeColor = '#FFE45E', // Viral electric gold
    textColor = '#FFFFFF',
    strokeColor = '#000000',
    strokeWidth = 14,
    showCard = true
  } = o;

  // Find active page for current second
  const page = captionData.pages.find(p => t >= p.start && t <= p.end + 0.12);
  if (!page) return;

  const words = page.words;
  ctx.font = `900 ${fontSize}px "${fontFamily}", sans-serif`;

  // Measure word widths and total line width
  const spaceW = ctx.measureText(' ').width;
  const wordWidths = words.map(w => ctx.measureText(w.word).width);
  const totalW = wordWidths.reduce((a, b) => a + b, 0) + (words.length - 1) * spaceW;

  let curX = (W - totalW) / 2;

  // Optional subtle backdrop pill
  if (showCard) {
    const padX = 36, padY = 20;
    const cardH = fontSize + padY * 2;
    rr(curX - padX, cy - fontSize - padY + 12, totalW + padX * 2, cardH, 22, 'rgba(0, 0, 0, 0.65)', 'rgba(255, 255, 255, 0.12)', 2, 0.95);
  }

  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    const isPastOrActive = t >= w.start;
    const isActive = t >= w.start && t <= w.end;

    // Word spring bounce on entry
    const timeSinceEnter = t - w.start;
    let wordScale = 1.0;
    if (timeSinceEnter >= 0 && timeSinceEnter < 0.25) {
      wordScale = E.pop(timeSinceEnter / 0.25);
    }

    const wordFill = isActive ? activeColor : textColor;
    const wordStroke = strokeColor;
    const wordStrokeW = strokeWidth;

    ctx.save();
    const wordCenterX = curX + wordWidths[i] / 2;
    const wordCenterY = cy - fontSize * 0.35;
    ctx.translate(wordCenterX, wordCenterY);
    ctx.scale(wordScale, wordScale);
    ctx.translate(-wordCenterX, -wordCenterY);

    if (isActive) {
      glow(activeColor, 32);
    }

    // Heavy outline for 100% readability over any background
    ctx.font = `900 ${fontSize}px "${fontFamily}", sans-serif`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    ctx.lineJoin = 'round';
    ctx.miterLimit = 2;
    ctx.strokeStyle = wordStroke;
    ctx.lineWidth = wordStrokeW;
    ctx.strokeText(w.word, curX, cy);

    // Main text fill
    ctx.fillStyle = wordFill;
    ctx.fillText(w.word, curX, cy);

    ctx.restore();
    noGlow();

    curX += wordWidths[i] + spaceW;
  }
}

// ==========================================
// 4. ANIMATED LOWER-THIRDS & BRANDING
// (from lower-thirds skill)
// ==========================================

function lowerThird(t, o = {}) {
  const {
    brand = 'STACKSHADE',
    topic = 'SYSTEM DESIGN',
    handle = '@stackshade',
    enterAt = 0.5,
    exitAt = 5.0,
    accentColor = '#38bdf8'
  } = o;

  if (t < enterAt || t >= exitAt) return;
  const pIn = prog(t, enterAt, 0.4);
  const pOut = prog(t, exitAt - 0.35, 0.35);
  const alpha = E.out(pIn) * (1 - E.in(pOut));

  const y = 300;
  const h = 76;
  const w = 620;
  const x = (W - w) / 2;

  ctx.save();
  // Glassmorphic container
  card(x, y, w, h, {
    r: h / 2,
    bg: 'rgba(15, 23, 42, 0.88)',
    border: 'rgba(255, 255, 255, 0.15)',
    glowColor: accentColor,
    glowBlur: 20,
    alpha
  });

  // Left accent dot
  rr(x + 22, y + h / 2 - 8, 16, 16, 8, accentColor, null, 0, alpha);

  // Brand and topic
  txt(`${brand} // ${topic}`, x + 54, y + 46, {
    px: 26, fam: 'JetBrains Mono', wt: 700, fill: '#ffffff', align: 'left', alpha, ls: 1
  });

  // Handle pill on right
  const pillW = 190;
  rr(x + w - pillW - 14, y + 14, pillW, h - 28, (h - 28) / 2, 'rgba(255, 255, 255, 0.08)', null, 0, alpha);
  txt(handle, x + w - pillW / 2 - 14, y + 47, {
    px: 24, fam: 'Inter', wt: 700, fill: accentColor, align: 'center', alpha
  });
  ctx.restore();
}

// ==========================================
// 5. COUNTDOWN & NUMERIC COUNTERS
// (from countdown-video skill)
// ==========================================

function counterWidget(t, { startVal, endVal, fromT, durT, cx, cy, suffix = '', prefix = '', color = '#38bdf8', px = 72 }) {
  const p = prog(t, fromT, durT);
  const val = Math.round(lerp(startVal, endVal, E.out(p)));
  txt(`${prefix}${val.toLocaleString()}${suffix}`, cx, cy, {
    px, fam: 'Inter', wt: 900, fill: color, stroke: '#000', strokeW: 10
  });
}

// ==========================================
// 6. UI CARDS & DIAGRAMS
// ==========================================

function card(x, y, w, h, o = {}) {
  const { r = 24, bg = 'rgba(15, 23, 42, 0.85)', border = 'rgba(56, 189, 248, 0.25)', lw = 2, glowColor = null, glowBlur = 24, alpha = 1 } = o;
  if (glowColor) glow(glowColor, glowBlur);
  rr(x, y, w, h, r, bg, border, lw, alpha);
  noGlow();
}

function badge(s, cx, cy, o = {}) {
  const { px = 30, bg = 'rgba(56, 189, 248, 0.15)', border = '#38bdf8', fill = '#38bdf8', fam = 'JetBrains Mono', wt = 700, alpha = 1 } = o;
  const padX = 26, padY = 12;
  ctx.font = `${wt} ${px}px "${fam}"`;
  const tw = ctx.measureText(s).width;
  const bw = tw + padX * 2, bh = px + padY * 2;
  rr(cx - bw / 2, cy - bh / 2, bw, bh, bh / 2, bg, border, 2, alpha);
  txt(s, cx, cy + px * 0.35, { px, fam, wt, fill, align: 'center', alpha });
}

function techGrid(t, o = {}) {
  const { size = 80, color = 'rgba(255, 255, 255, 0.03)', accent = 'rgba(56, 189, 248, 0.06)' } = o;
  ctx.save();
  ctx.lineWidth = 1;
  ctx.strokeStyle = color;
  for (let x = 0; x < W; x += size) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  for (let y = 0; y < H; y += size) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }
  const beamY = ((t * 220) % (H + 400)) - 200;
  const grad = ctx.createLinearGradient(0, beamY - 120, 0, beamY + 120);
  grad.addColorStop(0, 'rgba(56, 189, 248, 0)');
  grad.addColorStop(0.5, accent);
  grad.addColorStop(1, 'rgba(56, 189, 248, 0)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, beamY - 120, W, 240);
  ctx.restore();
}

function grid(t, size = 80, color = 'rgba(255, 255, 255, 0.03)', accent = 'rgba(56, 189, 248, 0.06)') {
  techGrid(t, { size, color, accent });
}

function bar(label, valText, pct, x, y, w, h, o = {}) {
  const { p = 1, fill = '#38bdf8', bg = 'rgba(255,255,255,0.06)', alpha = 1 } = o;
  txt(label, x, y - 14, { px: 30, fam: 'JetBrains Mono', wt: 600, fill: '#94a3b8', align: 'left', alpha });
  txt(valText, x + w, y - 14, { px: 32, fam: 'JetBrains Mono', wt: 700, fill, align: 'right', alpha });
  rr(x, y, w, h, h / 2, bg, null, 0, alpha);
  const fillW = Math.max(h, w * clamp(pct) * E.out(clamp(p)));
  rr(x, y, fillW, h, h / 2, fill, null, 0, alpha);
}

// Background electronic synth track generator
function buildScore(ac, { bpm = 126, dur, root = 45, chords = [0, 3, 5, 2], minor = true, kickFrom = 0.2, level = 0.8, hits = [] }) {
  const beat = 60 / bpm, f = m => 440 * Math.pow(2, (m - 69) / 12);
  const master = ac.createGain(); master.connect(ac.destination);
  master.gain.setValueAtTime(0, 0); master.gain.linearRampToValueAtTime(.6 * level, .4);
  master.gain.setValueAtTime(.6 * level, dur - 1.0); master.gain.linearRampToValueAtTime(0, dur);
  const r = (seed => () => ((seed = Math.imul(seed ^ (seed >>> 15), 2246822507) + 0x9e3779b9 | 0), ((seed ^ (seed >>> 13)) >>> 0) / 4294967296))(11);
  const noise = ac.createBuffer(1, ac.sampleRate, ac.sampleRate), nd = noise.getChannelData(0);
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
      osc('sawtooth', f(ch - 12), te, .22, .18, 450);
      osc('triangle', f(ch + 12 + tri[(i * 2 + e) % 4]), te, .28, .12);
    }
  }

  // Synthesize Sound Effects inside Web Audio
  if (hits && Array.isArray(hits)) {
    for (const hit of hits) {
      const ht = hit.t || 0;
      if (hit.type === 'clack') {
        const o = ac.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(2400, ht);
        const g = ac.createGain(); g.gain.setValueAtTime(0.2, ht); g.gain.exponentialRampToValueAtTime(0.001, ht + 0.03);
        o.connect(g); g.connect(master); o.start(ht); o.stop(ht + 0.035);
      } else if (hit.type === 'enter') {
        const o = ac.createOscillator(); o.type = 'triangle'; o.frequency.setValueAtTime(1100, ht);
        const g = ac.createGain(); g.gain.setValueAtTime(0.35, ht); g.gain.exponentialRampToValueAtTime(0.001, ht + 0.12);
        o.connect(g); g.connect(master); o.start(ht); o.stop(ht + 0.13);
      } else if (hit.type === 'whoosh') {
        const o = ac.createOscillator(); o.type = 'sine';
        o.frequency.setValueAtTime(140, ht); o.frequency.exponentialRampToValueAtTime(45, ht + 0.28);
        const g = ac.createGain(); g.gain.setValueAtTime(0.45, ht); g.gain.exponentialRampToValueAtTime(0.001, ht + 0.32);
        o.connect(g); g.connect(master); o.start(ht); o.stop(ht + 0.33);
      }
    }
  }
}

// ==========================================
// 4. ADVANCED TERMINAL & MOTION PRIMITIVES
// ==========================================

function punchCamera(t, punchTimestamps = [0.8, 3.5, 7.0], duration = 0.45, maxZoom = 1.07) {
  let zoom = 1.0;
  for (const pt of punchTimestamps) {
    if (t >= pt && t < pt + duration) {
      const p = (t - pt) / duration;
      // Spring pop profile
      const scaleBoost = (maxZoom - 1.0) * Math.sin(p * Math.PI) * Math.exp(-p * 2.5);
      zoom += Math.max(0, scaleBoost);
    }
  }
  if (zoom !== 1.0) {
    ctx.translate(W / 2, H * 0.46);
    ctx.scale(zoom, zoom);
    ctx.translate(-W / 2, -H * 0.46);
  }
  return zoom;
}

function drawTerminalCard(x, y, w, h, { title = 'bash — 1080×1920', bg = '#0b1120', border = '#1e293b', glowColor = 'rgba(56, 189, 248, 0.15)', alpha = 1 } = {}) {
  ctx.save();
  setA(alpha);
  glow(glowColor, 36);
  rr(x, y, w, h, 24, bg, border, 3, alpha);
  noGlow();

  // Window Top Titlebar
  rr(x, y, w, 68, [24, 24, 0, 0], 'rgba(255,255,255,0.03)', null, 0, alpha);
  ctx.beginPath();
  ctx.moveTo(x, y + 68);
  ctx.lineTo(x + w, y + 68);
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Traffic light window buttons
  const dotR = 8;
  const dotY = y + 34;
  rr(x + 36, dotY - dotR, dotR * 2, dotR * 2, dotR, '#ef4444', null, 0, alpha); // Red
  rr(x + 64, dotY - dotR, dotR * 2, dotR * 2, dotR, '#f59e0b', null, 0, alpha); // Yellow
  rr(x + 92, dotY - dotR, dotR * 2, dotR * 2, dotR, '#10b981', null, 0, alpha); // Green

  // Title Text
  txt(title, x + w / 2, y + 42, { px: 22, fam: 'JetBrains Mono', wt: 600, fill: '#64748b', align: 'center', alpha });
  ctx.restore();
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
