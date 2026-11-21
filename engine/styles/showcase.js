// STYLE "showcase": dark product-demo reel. Indigo glow, drifting bokeh, phones and tablets whose screens are
// built from small blocks, a table floor plan, QR, callout chips, a step checklist, an orbit diagram, end card + CTA.
// Captions are global: every spoken word appears as it is said (accent words in the brand colour), one short line
// at a time. Works with any voice language: for Hindi audio the spec's `show` text gives Roman Hinglish captions.
(function () {
  const { h, esc, clamp, ease } = KV;
  const C = { accent: '#8A99FF', accent2: '#465FFF', bg: '#060913', panel: '#101828', text: '#F2F4F8', muted: '#8B93A7', screen: '#F7F8F5', ok: '#3DDC97' };
  KV.palette = C;
  const mix = (a, b, p) => { const pa = a.slice(1).match(/\w\w/g).map(x => parseInt(x, 16)), pb = b.slice(1).match(/\w\w/g).map(x => parseInt(x, 16)); return `rgb(${pa.map((v, i) => Math.round(v + (pb[i] - v) * p)).join(',')})`; };
  const md = s => esc(s || '').replace(/\*(.+?)\*/g, '<em>$1</em>').replace(/\n/g, '<br>');

  // ---- small original icon set (24x24 strokes)
  const IP = {
    plate: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/>',
    fire: '<path d="M12 21c-4 0-6.5-2.7-6.5-6.2 0-3.6 3-5.6 3.6-9.3 2.4 1.5 3.4 3.6 3.4 5.4 1-.6 1.6-1.8 1.7-3 2.3 1.9 4.3 4.3 4.3 7.1C18.5 18.4 16 21 12 21z"/>',
    bell: '<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
    wifi: '<path d="M3 9a13 13 0 0 1 18 0M6 12.5a8.5 8.5 0 0 1 12 0M9 16a4 4 0 0 1 6 0"/><circle cx="12" cy="19" r="1"/>',
    cash: '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.6"/>',
    bank: '<path d="M3 9.5L12 4l9 5.5M5 10v7M9.5 10v7M14.5 10v7M19 10v7M3 20h18"/>',
    card: '<rect x="2.5" y="5.5" width="19" height="13" rx="2"/><path d="M2.5 10h19M6 15h4"/>',
    phone: '<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>',
    wallet: '<path d="M4 7.5h14.5a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7l11-3v3.5"/><circle cx="16.5" cy="13.5" r="1.2"/>',
    star: '<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.9L12 17l-5.2 2.7 1-5.9L3.5 9.7l5.9-.8z"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    pin: '<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.4"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    coffee: '<path d="M4.5 9h12v5a5 5 0 0 1-5 5h-2a5 5 0 0 1-5-5zM16.5 10.5h1.5a2.5 2.5 0 0 1 0 5h-1.5M8 3.5c0 1.5 1.5 1.5 1.5 3M12 3.5c0 1.5 1.5 1.5 1.5 3"/>',
    chat: '<path d="M4 18.5l1.3-3.6A7.5 7.5 0 1 1 8.6 18z"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    menu: '<path d="M5 6.5h14M5 12h14M5 17.5h9"/>',
    globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.6 2.6 14.4 0 17M12 3.5c-2.6 2.6-2.6 14.4 0 17"/>',
    gift: '<rect x="4" y="9" width="16" height="11" rx="1.5"/><path d="M3 9h18M12 9v11M12 9c-3-5-7-3-5 0M12 9c3-5 7-3 5 0"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    cal: '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    leaf: '<path d="M5 19c0-8 5-13 14-14-1 9-6 14-14 14zM5 19l7-7"/>',
    tag: '<path d="M3.5 12V4.5h7.5l9 9-7.5 7.5z"/><circle cx="8" cy="8.5" r="1.3"/>',
  };
  const icon = (n, o = {}) => (!IP[n] && KV.icon) ? KV.icon(n, { size: o.size || 20, stroke: o.stroke || 'currentColor', w: o.w || 2, fill: o.fill || 'none' }) : `<svg width="${o.size || 20}" height="${o.size || 20}" viewBox="0 0 24 24" fill="${o.fill || 'none'}" stroke="${o.stroke || 'currentColor'}" stroke-width="${o.w || 2}" stroke-linecap="round" stroke-linejoin="round">${IP[n] || (KV.iconPaths && KV.iconPaths[n]) || IP.plate}</svg>`;
  const FOOD = ['#E8B04B', '#D2693C', '#7FB069', '#C94F4F', '#F2C14E', '#9E6B4A', '#E07A5F'];

  // anim helper that respects a wrapper: entrance on `n`, extra transform on an inner node stays untouched
  function enter(ctx, n, kind, tin, dur = 0.3, sfx = null) { ctx.anim(n, kind || 'up', tin, Math.min(dur, SPEED), '', sfx); }
  let SPEED = 0.32;   // cap on every entrance: snappy, never sluggish
  function selWatch(ctx, node, tin) { if (tin == null) return; ctx.custom(t => node.classList.toggle('sel', t >= tin)); KV.sfx(tin, 'tick'); }

  // ---- screen blocks
  const B = {};
  B.head = b => { const n = h('div', 'b-head'); n.innerHTML = (b.badge ? `<span class="bd">${esc(b.badge)}</span>` : '') + (b.kick ? `<div class="k">${esc(b.kick)}</div>` : '') + `<div class="t">${md(b.t)}</div>` + (b.s ? `<div class="s">${esc(b.s)}</div>` : ''); return n; };
  B.search = (b, ctx) => {
    const n = h('div', 'b-search'); n.innerHTML = icon('search', { size: 15 }); const sp = h('span'); n.appendChild(sp);
    const full = b.t || ''; const t0 = b.typeTin != null ? b.typeTin : b.tin;
    if (b.type) ctx.custom(t => { const k = Math.round(clamp((t - t0) / (b.typeDur || 0.9)) * full.length); sp.textContent = full.slice(0, k) + (t > t0 && k < full.length ? '|' : ''); });
    else sp.textContent = full;
    if (!full) sp.textContent = b.ph || 'Search'; return n;
  };
  B.tabs = b => { const n = h('div', 'b-tabs'); (b.items || []).forEach((x, i) => n.appendChild(h('span', i === (b.on || 0) ? 'on' : '', esc(x)))); return n; };
  B.rows = (b, ctx) => {
    const n = h('div'); n.style.cssText = 'display:flex;flex-direction:column;gap:2px';
    b.items.forEach((it, i) => {
      const r = h('div', 'row');
      const col = it.c || FOOD[i % FOOD.length];
      r.innerHTML = `<div class="ic" style="background:${col}22;color:${col}">${icon(it.ic || 'plate', { size: 20 })}</div><div class="tx"><div class="tt">${esc(it.t)}</div>${it.s ? `<div class="ss">${esc(it.s)}</div>` : ''}</div>${it.v ? `<div class="vv">${esc(it.v)}</div>` : ''}${b.plus ? '<div class="pl">+</div>' : ''}`;
      n.appendChild(r);
      if (b.stagger) enter(ctx, r, 'up', b.tin + i * b.stagger, 0.35);
      if (b.hl === i) selWatch(ctx, r, b.selTin != null ? b.selTin : b.tin);
    });
    return n;
  };
  B.dish = b => { const col = b.c || FOOD[0]; const n = h('div', 'b-dish'); n.innerHTML = `<div class="pt" style="background:radial-gradient(circle at 40% 35%,#fff,${col}55 60%,${col})">${icon(b.ic || 'plate', { size: 60, stroke: '#fff', w: 1.6 })}</div><div class="t">${esc(b.t)}</div>${b.v ? `<div class="v">${esc(b.v)}</div>` : ''}${b.s ? `<div class="s">${esc(b.s)}</div>` : ''}`; return n; };
  B.kv = (b, ctx) => { const n = h('div', 'b-kv'); b.items.forEach(([k, v], i) => { const r = h('div', 'r', `<span>${esc(k)}</span><b>${esc(v)}</b>`); n.appendChild(r); if (b.stagger) enter(ctx, r, 'left', b.tin + i * b.stagger, 0.35); }); return n; };
  B.btn = b => { const n = h('div', 'b-btn', esc(b.t)); if (b.c) n.style.background = b.c; return n; };
  B.ring = (b, ctx) => {
    const n = h('div', 'b-ring'); const S = b.size || 150, R = S / 2 - 9, L = 2 * Math.PI * R;
    n.innerHTML = `<div style="position:relative;width:${S}px;height:${S}px"><svg width="${S}" height="${S}" style="position:absolute;inset:0;transform:rotate(-90deg)"><circle cx="${S / 2}" cy="${S / 2}" r="${R}" fill="none" stroke="rgba(127,127,127,.18)" stroke-width="9"/><circle class="arc" cx="${S / 2}" cy="${S / 2}" r="${R}" fill="none" stroke="${C.accent2}" stroke-width="9" stroke-linecap="round" stroke-dasharray="${L}" stroke-dashoffset="${L}"/></svg><div style="position:absolute;inset:0;display:grid;place-items:center;text-align:center"><div><div class="vv"></div><div class="lb">${esc(b.l || '')}</div></div></div></div>`;
    const arc = n.querySelector('.arc'), vv = n.querySelector('.vv');
    const [a0, a1] = b.count || [0, 0];
    ctx.custom(t => {
      const p = clamp((t - b.tin) / (b.dur || 3));
      arc.setAttribute('stroke-dashoffset', L * (1 - (b.p != null ? b.p * ease.out(clamp((t - b.tin) / 0.8)) : p)));
      if (b.count) { const s = Math.max(0, Math.round(a0 + (a1 - a0) * p)); vv.textContent = b.fmt === 'num' ? s : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; }
      else vv.textContent = b.v || '';
    });
    return n;
  };
  B.stars = (b, ctx) => {
    const n = h('div', 'b-stars'); const k = b.fill || 5;
    for (let i = 0; i < (b.n || 5); i++) {
      const s = h('span', '', icon('star', { size: b.size || 30, stroke: '#C9CDD6', w: 1.6 })); n.appendChild(s);
      const tt = (b.selTin != null ? b.selTin : b.tin + 0.4) + i * 0.16;
      if (i < k) { ctx.custom(t => { const on = t >= tt; s.innerHTML = icon('star', { size: b.size || 30, stroke: on ? '#F5B83D' : '#C9CDD6', fill: on ? '#F5B83D' : 'none', w: 1.6 }); s.style.transform = on && t < tt + 0.2 ? `scale(${1 + 0.3 * Math.sin((t - tt) / 0.2 * Math.PI)})` : ''; }); KV.sfx(tt, 'pop', 0.6); }
    }
    return n;
  };
  B.pay = (b, ctx) => {
    const n = h('div', 'b-pay'); const ics = ['cash', 'bank', 'card', 'phone', 'wallet'];
    b.items.forEach((x, i) => { const r = h('div', 'r', icon(ics[i % ics.length], { size: 18 }) + `<span>${esc(x)}</span>`); n.appendChild(r);
      const sel = Array.isArray(b.sel) ? b.sel.map(x => Array.isArray(x) ? x : [x.i, x.selTin]) : [[b.sel, b.selTin]];
      ctx.custom(t => { let cur = null; sel.forEach(([k, at]) => { if (at != null && t >= at) cur = k; }); r.classList.toggle('sel', cur === i); });
    });
    (Array.isArray(b.sel) ? b.sel : []).forEach(x => KV.sfx(Array.isArray(x) ? x[1] : x.selTin, 'tick'));
    return n;
  };
  B.total = b => h('div', 'b-total', `<span>${esc(b.t || 'Total')}</span><span>${esc(b.v)}</span>`);
  B.profile = (b, ctx) => {
    const n = h('div', 'b-profile');
    n.innerHTML = `<div class="top"><div class="av">${b.logo ? `<img src="${b.logo}" style="width:100%;height:100%;border-radius:50%">` : esc(b.ini || 'B')}</div><div class="st">${(b.stats || [['0', 'posts'], ['0', 'followers'], ['0', 'following']]).map(([v, l]) => `<div><b>${esc(v)}</b>${esc(l)}</div>`).join('')}</div></div><div class="nm">${esc(b.name || '')}</div>`;
    (b.bio || []).forEach((line, i) => { const r = h('div', 'bio', md(line)); n.appendChild(r); if (b.bioTin) enter(ctx, r, 'left', b.bioTin + i * 0.3, 0.35); if (b.hl === i) selWatch(ctx, r, b.selTin); });
    return n;
  };
  B.hl = (b, ctx) => { const n = h('div', 'b-hl'); b.items.forEach((x, i) => { const it = h('div', 'h', `<i>${icon(x.ic || 'star', { size: 20 })}</i><span>${esc(x.t)}</span>`); n.appendChild(it); if (b.stagger) enter(ctx, it, 'pop', b.tin + i * b.stagger, 0.4, 'pop'); }); return n; };
  B.grid = (b, ctx) => { const n = h('div', 'b-grid'); (b.items || []).forEach((x, i) => { const d = h('div', '', md(x.t || '')); d.style.background = x.c || FOOD[i % FOOD.length]; if (x.ic) d.innerHTML = icon(x.ic, { size: 26, stroke: '#fff', w: 1.6 }) + (x.t ? `<span style="font-size:9px">${esc(x.t)}</span>` : ''); n.appendChild(d); if (b.stagger) enter(ctx, d, 'pop', b.tin + i * b.stagger, 0.35, i ? null : 'pop'); }); return n; };
  B.chat = (b, ctx) => { const n = h('div', 'b-chat'); b.msgs.forEach((m, i) => { const d = h('div', 'm' + (m.me ? ' me' : ''), esc(m.t)); n.appendChild(d); enter(ctx, d, 'up', m.tin != null ? m.tin : b.tin + i * 0.6, 0.35, 'pop'); }); return n; };
  B.big = b => h('div', 'b-big', `<div class="t">${md(b.t)}</div>${b.s ? `<div class="s">${esc(b.s)}</div>` : ''}`);
  B.bell = (b, ctx) => { const n = h('div', 'b-bell', `<div class="c"><div style="text-align:center">${icon('bell', { size: 46, stroke: '#fff' })}<div>${esc(b.t || 'Call waiter')}</div></div></div>`); const c = n.firstChild; ctx.custom(t => { const k = b.selTin != null && t >= b.selTin ? Math.max(0, 1 - (t - b.selTin) / 0.3) : 0; c.style.transform = `scale(${1 + Math.sin(t * 3) * 0.025 - k * 0.12})`; }); if (b.selTin != null) KV.sfx(b.selTin, 'ding'); return n; };
  B.split = b => { const n = h('div', 'b-split'); b.items.forEach(x => n.appendChild(h('div', '', `${esc(x.l)}<b>${esc(x.v)}</b>`))); return n; };
  B.stats = (b, ctx) => { const n = h('div', 'b-stats'); b.items.forEach(x => { const d = h('div', '', `${esc(x.l)}<b>${esc(x.v)}</b>`); n.appendChild(d); if (x.to) { const bb = d.querySelector('b'); ctx.custom(t => { if (t >= x.toTin) bb.textContent = x.to; else bb.textContent = x.v; }); } }); return n; };
  B.cols = (b, ctx) => { const n = h('div', 'b-cols'); b.cols.forEach((c, ci) => { const col = h('div', 'col', `<div class="h">${esc(c.h)}</div>`); c.items.forEach((x, i) => { const tk = h('div', 'tk', `<span>${esc(x.t)}</span><b>${esc(x.v || '')}</b>`); col.appendChild(tk); if (b.stagger) enter(ctx, tk, 'up', b.tin + (ci * 2 + i) * b.stagger, 0.35); }); n.appendChild(col); }); return n; };
  B.note = b => h('div', 'b-note', md(b.t));
  B.map = b => h('div', 'b-map', `<div class="pin">${icon('pin', { size: 40, stroke: C.accent2, w: 2.2, fill: '#fff' })}</div>`);
  B.space = b => { const n = h('div'); n.style.height = (b.h || 10) + 'px'; return n; };
  B.qr = b => { const n = h('div'); n.style.cssText = 'display:grid;place-items:center;padding:6px'; n.innerHTML = qrSvg(b.size || 150, b.seed || 7); return n; };

  function screenPage(sc, ctx, dark) {
    const pg = h('div', 'page' + (sc.dark || dark ? ' dark' : ''));
    if (sc.bg) pg.style.background = sc.bg;
    (sc.blocks || []).forEach(b => {
      if (b.tin == null) b.tin = sc.tin;
      const f = B[b.k]; if (!f) throw new Error('unknown showcase block ' + b.k);
      const n = f(b, ctx);
      if (b.grow) n.style.marginTop = 'auto';
      pg.appendChild(n);
      if (b.at_set) enter(ctx, n, b.anim || 'up', b.tin, 0.4, b.sfx || null);
    });
    return pg;
  }
  function device(e, ctx, kind) {
    const isPhone = kind === 'phone', isBrowser = kind === 'browser';
    const w = e.w || (isPhone ? 320 : isBrowser ? 560 : 620), hh = isPhone ? Math.round(w * 2.04) : Math.round(w * (isBrowser ? 0.66 : 0.64));
    const d = h('div', kind); d.style.width = w + 'px'; d.style.height = hh + 'px';
    if (isBrowser) d.appendChild(h('div', 'bar', `<i></i><i></i><i></i><span>${esc(e.url || 'yourcafe.in')}</span><b>● LIVE</b>`));
    const scr = h('div', 'scr'); d.appendChild(scr);
    if (isPhone) { d.appendChild(h('div', 'isl')); }
    const screens = e.screens || [Object.assign({ tin: e.tin }, e.screen || {})];
    const pages = screens.map((s, i) => {
      if (s.tin == null) s.tin = i === 0 ? e.tin : e.tin + i;
      const pg = screenPage(s, ctx, (!isPhone && !isBrowser) || e.dark);
      if (isPhone) pg.appendChild(h('div', 'sb', `<span>9:41</span><span>●●● ▮</span>`));
      scr.appendChild(pg); return { pg, s };
    });
    ctx.custom(t => {
      let cur = 0; pages.forEach((p, i) => { if (t >= p.s.tin) cur = i; });
      pages.forEach((p, i) => {
        if (i === cur) { const k = i === 0 ? 1 : ease.out5(clamp((t - p.s.tin) / 0.24)); p.pg.style.opacity = 1; p.pg.style.transform = `translateX(${(1 - k) * 100}%)`; p.pg.style.zIndex = 2; p.pg.style.visibility = 'visible'; }
        else if (i === cur - 1 && t - pages[cur].s.tin < 0.24) { p.pg.style.visibility = 'visible'; p.pg.style.zIndex = 1; p.pg.style.transform = `translateX(${-ease.out5(clamp((t - pages[cur].s.tin) / 0.24)) * 30}%)`; }
        else p.pg.style.visibility = 'hidden';
      });
    });
    pages.slice(1).forEach(p => KV.sfx(p.s.tin, 'whoosh', 0.5));
    // 3D tilt + float on an inner wrapper so the entrance animation keeps its own transform
    const tilt = h('div'); tilt.appendChild(d);
    const [rx, ry, rz] = e.tilt || [0, 0, 0];
    ctx.custom(t => { const f = Math.sin(t * 1.2 + (e.seed || 0)) * (e.float == null ? 6 : e.float); tilt.style.transform = `perspective(1400px) translateY(${f}px) rotateX(${rx}deg) rotateY(${ry + Math.sin(t * 0.6) * 2}deg) rotateZ(${rz}deg)`; });
    const outer = h('div'); outer.appendChild(tilt);
    if (e.scale) { d.style.transformOrigin = '50% 0'; }
    enter(ctx, outer, e.anim || 'zoom', e.tin, 0.4, 'whoosh');
    return outer;
  }

  function qrSvg(size, seed) {
    const N = 25, c = size / N; let r = '';
    const finder = (x, y) => (x >= 0 && x < 7 && y >= 0 && y < 7);
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
      const inF = finder(x, y) || finder(x - (N - 7), y) || finder(x, y - (N - 7));
      let on;
      if (inF) { const lx = x >= N - 7 ? x - (N - 7) : x, ly = y >= N - 7 ? y - (N - 7) : y; on = lx === 0 || ly === 0 || lx === 6 || ly === 6 || (lx >= 2 && lx <= 4 && ly >= 2 && ly <= 4); }
      else if ((x < 8 && y < 8) || (x > N - 9 && y < 8) || (x < 8 && y > N - 9)) on = false;
      else on = KV.rand(seed * 1000 + y * N + x) > 0.52;
      if (on) r += `<rect x="${(x * c).toFixed(2)}" y="${(y * c).toFixed(2)}" width="${(c + 0.4).toFixed(2)}" height="${(c + 0.4).toFixed(2)}"/>`;
    }
    return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" fill="#101828">${r}</svg>`;
  }

  // ---- scene elements
  const V = {};
  V.phone = (e, ctx) => device(e, ctx, 'phone');
  V.tablet = (e, ctx) => device(e, ctx, 'tablet');
  V.qr = (e, ctx) => { const n = h('div', 'qr', qrSvg(e.size || 260, e.seed || 3)); enter(ctx, n, e.anim || 'pop', e.tin, 0.5, 'pop'); return n; };
  V.title = (e, ctx) => { const n = h('div', 'title', md(e.text)); if (e.size) n.style.fontSize = e.size + 'px'; enter(ctx, n, e.anim || 'blur', e.tin, 0.5); return n; };
  V.slam = (e, ctx) => {
    const n = h('div', 'title slam'); if (e.size) n.style.fontSize = e.size + 'px';
    const lines = (e.text || '').split('\n'); let k = 0;
    lines.forEach((ln, li) => {
      const row = h('div', 'sl'); n.appendChild(row);
      let on = false;
      ln.split(' ').filter(Boolean).forEach(tok => {
        const st = tok.startsWith('*'), en = tok.replace(/[.,!?:;]+$/, '').endsWith('*'); const acc = on || st; if (st && !en) on = true; if (en) on = false;
        const w = h('span', 'sw' + (acc ? ' acc' : ''), esc(tok.replace(/\*/g, ''))); row.appendChild(w);
        const tin = e.tin + (e.stagger || 0.11) * k++;
        ctx.custom(t => {
          const p = clamp((t - tin) / 0.22);
          w.style.opacity = p > 0 ? 1 : 0;
          w.style.transform = `scale(${2.3 - 1.3 * ease.back(p)}) translateY(${(1 - p) * -30}px)`;
          w.style.filter = `blur(${(1 - p) * 10}px)`;
          if (acc) w.style.setProperty('--hl', clamp((t - tin - 0.12) / 0.2));
        });
        if (k % 2) KV.sfx(tin, 'pop', 0.5);
      });
    });
    return n;
  };
  V.sub = (e, ctx) => { const n = h('div', 'sub', md(e.text)); enter(ctx, n, e.anim || 'up', e.tin, 0.45); return n; };
  V.logo = (e, ctx, spec) => {
    const n = h('div', 'logo', `<img src="${spec.logo}" width="${e.size || 170}" height="${e.size || 170}"><div class="n">CraftLayer <span>Studio</span></div>${e.sub ? `<div class="s">${esc(e.sub)}</div>` : ''}`);
    if (e.name) n.querySelector('.n').innerHTML = md(e.name);
    enter(ctx, n, e.anim || 'zoom', e.tin, 0.6, 'whoosh'); return n;
  };
  V.cta = (e, ctx) => {
    const n = h('div', 'cta', `<div class="in"><div class="av"></div><div class="tx"></div><div class="go">${icon('arrow', { size: 24, stroke: '#fff', w: 2.4 })}</div></div>${e.label ? `<div class="lb">${md(e.label).replace(/<em>/g, '<b>').replace(/<\/em>/g, '</b>')}</div>` : ''}`);
    const tx = n.querySelector('.tx'); const full = e.text || '';
    ctx.custom(t => { const k = Math.round(clamp((t - e.tin - 0.3) / 0.7) * full.length); tx.textContent = full.slice(0, k); });
    enter(ctx, n, 'up', e.tin, 0.5, 'pop'); return n;
  };
  V.chips = (e, ctx) => {
    const n = h('div'); n.style.cssText = 'position:absolute;inset:0;pointer-events:none';
    e.items.forEach((c, i) => {
      const d = h('div', 'chip' + (c.dark || e.dark ? ' dk' : ''), (c.ic ? icon(c.ic, { size: 18, stroke: c.dark || e.dark ? C.accent : C.accent2 }) : '<i></i>') + `<span>${md(c.t)}</span>`);
      d.style.left = c.x + 'px'; d.style.top = c.y + 'px'; n.appendChild(d);
      const tin = c.tin != null ? c.tin : e.tin + i * 0.35;
      enter(ctx, d, 'pop', tin, 0.45, 'pop');
      ctx.custom(t => { if (t > tin + 0.45) d.style.transform = `translateY(${Math.sin(t * 1.6 + i) * 4}px)`; });
    });
    return n;
  };
  V.avatars = (e, ctx) => { const n = h('div', 'avs'); e.items.forEach((a, i) => { const d = h('div', '', esc(a.t)); d.style.background = a.c || (i ? '#4F7DF3' : '#E5533D'); n.appendChild(d); enter(ctx, d, 'pop', e.tin + i * 0.25, 0.45, 'pop'); }); return n; };
  V.steps = (e, ctx) => {
    const n = h('div', 'steps', e.title ? `<div class="hd">${esc(e.title)}</div>` : '');
    e.items.forEach((it, i) => {
      const r = h('div', 'it', `<span class="no">${String(i + 1).padStart(2, '0')}</span><span class="tt">${esc(it.t)}</span><span class="ss">${esc(it.s || '')}</span><span class="ck"></span>`);
      n.appendChild(r); const ck = r.querySelector('.ck');
      const tin = it.tin != null ? it.tin : e.tin + i * (e.stagger || 0.45);
      enter(ctx, r, 'left', tin, 0.4);
      ctx.custom(t => { const on = t >= tin + 0.3; ck.style.background = on ? C.accent2 : 'none'; ck.style.borderColor = on ? C.accent2 : 'rgba(255,255,255,.18)'; ck.innerHTML = on ? icon('check', { size: 18, stroke: '#fff', w: 3 }) : ''; });
      KV.sfx(tin + 0.3, 'tick');
    });
    enter(ctx, n, 'up', e.tin - 0.2 < 0 ? e.tin : e.tin - 0.2, 0.45); return n;
  };
  V.orbit = (e, ctx, spec) => {
    const n = h('div', 'orbit'); const W = 560, H = 520, cx = W / 2, cy = H / 2, R = e.r || 205;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('width', W); svg.setAttribute('height', H); n.appendChild(svg);
    const cn = h('div', 'cn', `<img src="${spec.logo}">`); n.appendChild(cn); enter(ctx, cn, 'zoom', e.tin, 0.55, 'pop');
    e.items.forEach((it, i) => {
      const a = -Math.PI / 2 + i * 2 * Math.PI / e.items.length, x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
      const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      [['x1', cx], ['y1', cy], ['x2', x], ['y2', y], ['stroke', C.accent2], ['stroke-width', 3], ['stroke-dasharray', '8 8']].forEach(([k, v]) => ln.setAttribute(k, v));
      svg.appendChild(ln);
      const nd = h('div', 'nd', esc(it.t)); nd.style.left = x + 'px'; nd.style.top = y + 'px'; n.appendChild(nd);
      const tin = it.tin != null ? it.tin : e.tin + 0.4 + i * 0.4;
      enter(ctx, nd, 'pop', tin, 0.45, 'pop');
      ctx.custom(t => { ln.style.opacity = clamp((t - tin + 0.2) / 0.3); ln.setAttribute('stroke-dashoffset', -t * 30); });
    });
    return n;
  };
  V.floor = (e, ctx) => {
    const cols = e.cols || 3, rows = Math.ceil(e.tables.length / cols), W = e.w || 560, H = rows * 190 + 40;
    const wrap = h('div'); wrap.style.cssText = `width:${W}px;height:${H}px;perspective:1100px`;
    const f = h('div', 'floor'); f.style.cssText = `width:${W}px;height:${H}px;transform-style:preserve-3d`;
    wrap.appendChild(f); f.appendChild(h('div', 'pl'));
    const pos = {};
    e.tables.forEach((tb, i) => {
      const x = W * ((i % cols) + 0.5) / cols, y = 40 + 190 * Math.floor(i / cols) + 75; pos[tb.id] = [x, y];
      [[-62, -8], [36, -8], [-13, -66], [-13, 50]].forEach(([dx, dy]) => { const c = h('div', 'ch'); c.style.left = x + dx + 'px'; c.style.top = y + dy + 'px'; f.appendChild(c); });
      const t = h('div', 'tb', esc(tb.id)); t.style.left = x + 'px'; t.style.top = y + 'px'; f.appendChild(t);
      if (tb.s) { const st = h('div', 'st', esc(tb.s)); st.style.color = tb.c || C.ok; t.appendChild(st); if (e.statusTin) enter(ctx, st, 'fade', e.statusTin + i * 0.12, 0.3); }
      if (e.hl && e.hl.includes(tb.id)) ctx.custom(tt => { const on = tt >= (e.selTin != null ? e.selTin : e.tin); t.style.boxShadow = on ? `0 0 0 3px ${C.accent2},0 0 40px ${C.accent2},0 14px 24px rgba(0,0,0,.5)` : ''; t.style.color = on ? '#fff' : ''; });
      if (e.phones) { const m = h('div', 'mp'); m.style.left = x + 'px'; m.style.top = y + 'px'; f.appendChild(m); enter(ctx, m, 'drop', (e.phonesTin != null ? e.phonesTin : e.tin) + i * 0.14, 0.45, i ? null : 'pop'); }
    });
    (e.people || []).forEach((p, i) => { const [x, y] = pos[p.at]; const d = h('div', 'pp', esc(p.t)); d.style.background = p.c || (i ? '#4F7DF3' : '#E5533D'); d.style.left = x + (p.dx || (i ? 58 : -58)) + 'px'; d.style.top = y + (p.dy || 0) + 'px'; f.appendChild(d); enter(ctx, d, 'pop', (p.tin != null ? p.tin : e.tin) + i * 0.2, 0.45, 'pop'); });
    ctx.custom(t => { const k = e.camTin != null ? ease.inout(clamp((t - e.camTin) / 1.2)) : 0; f.style.transform = `rotateX(${(e.rx == null ? 52 : e.rx) - k * 20}deg) scale(${1 + k * (e.zoom || 0)})`; });
    enter(ctx, wrap, e.anim || 'fade', e.tin, 0.6);
    return wrap;
  };
  V.browser = (e, ctx) => device(Object.assign({ float: 4 }, e), ctx, 'browser');
  V.tile = (e, ctx) => {
    const n = h('div', 'tilex', `<div class="sq" style="${e.c ? `background:${e.c};color:#fff` : ''}">${icon(e.ic || 'globe', { size: (e.size || 150) * 0.5, w: 1.6 })}</div>${e.label ? `<div class="lb">${esc(e.label)}</div>` : ''}`);
    const sq = n.firstChild; sq.style.width = sq.style.height = (e.size || 150) + 'px';
    enter(ctx, n, e.anim || 'pop', e.tin, 0.5, 'pop'); return n;
  };
  V.net = (e, ctx) => {
    // a hand net: rim, handle, diamond mesh. dryTin: the ground under it cracks; fishTin: fish fill it
    const W = e.w || 420, H = Math.round(W * 1.05), n = h('div'); n.style.cssText = `position:relative;width:${W}px;height:${H}px`;
    const rx = W * 0.42, cx = W * 0.46, top = H * 0.2, tip = H * 0.92, ry = W * 0.08;
    let mesh = '';
    for (let k = -12; k <= 12; k++) { const x = cx + k * rx / 6; mesh += `<path d="M${x} ${top} L${cx + k * rx / 30} ${tip}"/>`; }
    for (let j = 1; j < 9; j++) { const y = top + (tip - top) * j / 9, r = rx * (1 - j / 9.5); mesh += `<ellipse cx="${cx}" cy="${y}" rx="${r}" ry="${ry * (1 - j / 10)}"/>`; }
    const fish = Array.from({ length: 9 }, (_, k) => { const fx = cx + (KV.rand(k + 3) - 0.5) * rx * 0.9 * (1 - k / 14), fy = top + 40 + k * (tip - top - 80) / 10; return `<g class="fish" data-k="${k}" transform="translate(${fx} ${fy})"><path d="M-22 0c10-12 30-12 40 0-10 12-30 12-40 0zM18 0l12-9v18z" fill="#E9EDF7" stroke="#9aa6c8" stroke-width="2"/></g>`; }).join('');
    n.innerHTML = `<div class="dry" style="position:absolute;left:${cx - rx * 1.25}px;top:${tip - 40}px;width:${rx * 2.5}px;height:90px;border-radius:50%;background:radial-gradient(closest-side,#d8c49a,#c8b07e 70%,transparent);opacity:0"></div>
      <svg width="${W}" height="${H}" style="position:absolute;inset:0;overflow:visible">
      <defs><clipPath id="nc${e.tin}"><path d="M${cx - rx} ${top} Q${cx - rx * 0.7} ${tip * 0.8} ${cx} ${tip} Q${cx + rx * 0.7} ${tip * 0.8} ${cx + rx} ${top} Z"/></clipPath></defs>
      <g class="fishes">${fish}</g>
      <g clip-path="url(#nc${e.tin})" fill="none" stroke="${e.color || C.accent2}" stroke-width="2.2" class="mesh">${mesh}</g>
      <path d="M${cx - rx} ${top} Q${cx - rx * 0.7} ${tip * 0.8} ${cx} ${tip} Q${cx + rx * 0.7} ${tip * 0.8} ${cx + rx} ${top}" fill="none" stroke="${e.color || C.accent2}" stroke-width="3"/>
      <ellipse cx="${cx}" cy="${top}" rx="${rx}" ry="${ry}" fill="none" stroke="${C.text}" stroke-width="7"/>
      <path d="M${cx + rx * 0.93} ${top - 10} L${W * 1.02} ${top - H * 0.24}" stroke="${C.text}" stroke-width="10" stroke-linecap="round"/>
      <path d="M${W * 0.96} ${top - H * 0.205} L${W * 1.05} ${top - H * 0.27}" stroke="${C.accent2}" stroke-width="14" stroke-linecap="round"/></svg>`;
    const dry = n.querySelector('.dry'), mesh2 = n.querySelector('.mesh'), fishes = [...n.querySelectorAll('.fish')];
    ctx.custom(t => {
      const d = e.dryTin != null ? clamp((t - e.dryTin) / 0.6) : 0;
      dry.style.opacity = d; mesh2.setAttribute('stroke', d > 0 ? mix(e.color || C.accent2, '#B59A62', d) : (e.color || C.accent2));
      fishes.forEach((f, k) => { const tt = e.fishTin != null ? clamp((t - e.fishTin - k * 0.12) / 0.4) : 0; f.style.opacity = tt; f.style.transform = `translateY(${(1 - tt) * -40}px)`; });
    });
    if (e.fishTin != null) KV.sfx(e.fishTin, 'pop');
    enter(ctx, n, e.anim || 'drop', e.tin, 0.6, 'whoosh'); return n;
  };
  V.water = (e, ctx, spec) => {
    // full-width water that rises to `level` (px from the top of the visual area)
    const n = h('div', 'water'); n.style.top = (e.level == null ? 420 : e.level) + 'px';
    n.innerHTML = '<div class="wv"></div>' + Array.from({ length: 14 }, (_, k) => `<i style="left:${(KV.rand(k + 7) * 100).toFixed(1)}%"></i>`).join('');
    const wv = n.firstChild, bubbles = [...n.querySelectorAll('i')];
    ctx.custom(t => {
      const p = ease.out(clamp((t - e.tin) / 0.9)); n.style.transform = `translateY(${(1 - p) * 900}px)`;
      wv.style.backgroundPositionX = (t * 60) + 'px';
      bubbles.forEach((b, k) => { const y = 600 - ((t * (30 + k * 4) + k * 90) % 600); b.style.top = y + 'px'; });
    });
    if (e.tin != null) KV.sfx(e.tin, 'whoosh');
    return n;
  };
  V.pipes = (e, ctx) => {
    // sources pouring into water: each a labelled tile on a pipe with falling drops
    const n = h('div'); n.style.cssText = `display:flex;gap:${e.gap || 40}px;align-items:flex-start`;
    e.items.forEach((it, i) => {
      const c = h('div', 'pipe', `<div class="k">${esc(it.k || '')}</div><div class="sq">${icon(it.ic || 'globe', { size: 46, w: 1.8 })}</div><div class="lb">${esc(it.t)}</div><div class="ln"></div>`);
      n.appendChild(c); const tin = it.tin != null ? it.tin : e.tin + i * 0.5; enter(ctx, c, 'drop', tin, 0.5, 'pop');
      const ln = c.querySelector('.ln'); ctx.custom(t => { ln.style.backgroundPositionY = (t * 160) + 'px'; ln.style.opacity = clamp((t - tin - 0.3) / 0.3); });
    });
    return n;
  };
  V.coins = (e, ctx) => {
    const n = h('div'); n.style.cssText = 'position:absolute;inset:0;pointer-events:none';
    for (let k = 0; k < (e.n || 9); k++) { const c = h('div', 'coin', '₹'); n.appendChild(c); const x = 200 + KV.rand(k + 5) * 320, d = 0.25 * k;
      ctx.custom(t => { const p = clamp((t - e.tin - d) / 3); c.style.opacity = p > 0 ? 1 - p * 0.7 : 0; c.style.transform = `translate(${x + Math.sin(t * 2 + k) * 14}px,${(e.y || 420) + p * 360}px) rotate(${t * 90 + k * 40}deg)`; }); }
    return n;
  };
  V.row = (e, ctx, spec) => { const r = h('div'); r.style.cssText = `display:flex;align-items:center;justify-content:center;gap:${e.gap == null ? 24 : e.gap}px`; e.children.forEach(c => r.appendChild(build(c, ctx, spec))); return r; };
  V.spacer = e => { const n = h('div'); n.style.height = (e.h || 20) + 'px'; return n; };

  function build(e, ctx, spec) {
    if (e.tin == null) e.tin = ctx.cursor; ctx.cursor = Math.max(ctx.cursor, e.tin + 0.3);
    if (e.children) e.children.forEach(c => { if (c.tin == null) c.tin = e.tin; });
    const f = V[e.type]; if (!f) throw new Error('unknown showcase element ' + e.type);
    const n = f(e, ctx, spec);
    if (e.mt != null) n.style.marginTop = e.mt + 'px';
    if (e.abs) { n.classList.add('abs'); n.style.left = e.abs[0] + 'px'; n.style.top = e.abs[1] + 'px'; }
    if (e.out != null) ctx.exit(n, e.out);
    return n;
  }

  // mark screen blocks that have their own cue so they animate in
  function prepBlocks(list) { (list || []).forEach(e => { (e.screens || (e.screen ? [e.screen] : [])).forEach(s => (s.blocks || []).forEach(b => { if (b.tin != null && b.anim !== 'none') b.at_set = true; })); if (e.children) prepBlocks(e.children); }); }

  // ---- problem / fix treatment: a coloured flash and tint, a big label, a stamp, a shake (bad) or a tap (good)
  function toneFx(sc, i, root, vis, vin, ctx, end) {
    const bad = sc.tone === 'bad', col = bad ? '#FF4D4D' : '#2EE59D', len = Math.max(0.6, end - sc.t0);
    const tint = h('div', 'tint'); tint.style.background = `radial-gradient(60% 45% at 50% 45%, ${col}33, transparent 70%)`; root.insertBefore(tint, vis);
    const flash = h('div', 'flash'); flash.style.background = bad ? `${col}` : `linear-gradient(115deg, transparent 30%, ${col}aa 50%, transparent 70%)`; root.appendChild(flash);
    const lab = h('div', 'tlabel ' + (bad ? 'bad' : 'good'), `<i>${bad ? '✕' : '✓'}</i><span>${esc(sc.label || (bad ? 'PROBLEM' : 'FIX'))}</span>`); root.appendChild(lab);
    const stamp = h('div', 'stamp ' + (bad ? 'bad' : 'good'), bad ? '✕' : '✓'); root.appendChild(stamp);
    const rays = []; if (!bad) for (let r = 0; r < 10; r++) { const ry = h('div', 'ray'); ry.style.transform = `rotate(${r * 36}deg)`; stamp.appendChild(ry); rays.push(ry); }
    const sAt = sc.t0 + len * (sc.stampAt || (bad ? 0.55 : 0.62));
    KV.sfx(sc.t0 + 0.02, bad ? 'stamp' : 'riser', bad ? 0.35 : 0.25); KV.sfx(sAt, bad ? 'stamp' : 'ding', bad ? 0.8 : 0.6);
    const btn = vin.querySelector('.b-btn'); const tap = btn ? h('div', 'tap') : null; if (tap) root.appendChild(tap);
    const tAt = sc.t0 + len * 0.78; if (tap) KV.sfx(tAt, 'tick', 0.9);
    ctx.custom(t => {
      const d = t - sc.t0;
      tint.style.opacity = clamp(d / 0.3) * (0.85 + 0.15 * Math.sin(t * 6));
      flash.style.opacity = bad ? Math.max(0, 0.32 * (1 - d / 0.22)) : Math.max(0, 1 - Math.abs(d - 0.25) / 0.25) * 0.7;
      if (!bad) flash.style.transform = `translateX(${(d / 0.5 - 0.5) * 140}%)`;
      const lp = ease.back(clamp(d / 0.3)), lo = clamp((len - d) / 0.2);
      lab.style.opacity = Math.min(clamp(d / 0.12), lo); lab.style.transform = `translateX(-50%) scale(${0.4 + 0.6 * lp}) rotate(${(bad ? -3 : 2) * (1 - lp)}deg)`;
      const sp = clamp((t - sAt) / 0.25);
      stamp.style.opacity = t < sAt ? 0 : Math.min(1, clamp((end - t) / 0.2) * 1);
      stamp.style.transform = `rotate(${bad ? -12 : 8}deg) scale(${t < sAt ? 3 : 3 - 2 * ease.out5(sp)})`;
      rays.forEach(ry => { const rp = clamp((t - sAt - 0.1) / 0.45); ry.style.opacity = rp > 0 && rp < 1 ? 1 - rp : 0; ry.style.height = (30 + rp * 80) + 'px'; });
      if (bad) { const sh = d < 0.42 ? (1 - d / 0.42) * 14 : (t > sAt && t < sAt + 0.2 ? (1 - (t - sAt) / 0.2) * 10 : 0);
        vis.style.transform = `translate(${Math.sin(t * 90) * sh}px,${Math.cos(t * 77) * sh * 0.6}px)`; }
      if (tap) {
        const r = btn.getBoundingClientRect(), rr = root.getBoundingClientRect(), sx = (r.left + r.width / 2 - rr.left) / (rr.width / SPEC.W), sy = (r.top + r.height / 2 - rr.top) / (rr.height / SPEC.H);
        const tp = (t - tAt);
        tap.style.left = sx + 'px'; tap.style.top = sy + 'px';
        tap.style.opacity = tp > -0.35 && tp < 0.5 ? (tp < 0 ? 1 + tp / 0.35 : 1 - tp / 0.5) : 0;
        tap.style.transform = `translate(-50%,-50%) scale(${tp < 0 ? 1.4 + tp : 0.6 + tp * 3})`;
        btn.style.transform = tp > 0 && tp < 0.16 ? 'scale(.93)' : '';
        if (tp > 0) btn.style.filter = 'brightness(1.15)';
      }
    });
  }

  let SPEC, CAP = [], KICK, scenesRef;
  const STYLE = {
    buildScene(sc, i, root, ctx, spec) {
      if (i === 0) {   // theme first: elements read C while they are built
        if (spec.bigScreens) document.body.classList.add('big');
        if (spec.light) { document.body.classList.add('light'); Object.assign(C, { text: '#101828', accent: '#3A50E0', accent2: '#465FFF', bg: '#F3F1EC' }); }
        Object.assign(C, (spec.light ? spec.lightTheme : spec.theme) || {});
      }
      ctx.cursor = sc.t0 + 0.15;
      const end = i + 1 < spec.scenes.length ? spec.scenes[i + 1].t0 : spec.duration;
      prepBlocks(sc.vis);
      const vis = h('div', 'vis'); if (sc.visTop != null) vis.style.top = sc.visTop + 'px'; if (sc.visH != null) vis.style.height = sc.visH + 'px';
      const vin = h('div', 'vin'); vis.appendChild(vin); root.appendChild(vis);
      (sc.vis || []).forEach(e => vin.appendChild(build(e, ctx, spec)));
      if (sc.tone) toneFx(sc, i, root, vis, vin, ctx, end);
      // slow camera push for the whole scene
      const [s0, s1] = sc.push || [1, 1.08];
      const kicks = (sc.words || []).filter(w => w.acc).map(w => w.t);
      const dir = i % 2 ? 1 : -1;
      ctx.custom(t => {
        const p = clamp((t - sc.t0) / Math.max(0.5, end - sc.t0));
        const inP = ease.out5(clamp((t - sc.t0) / 0.32));
        let kick = 0; kicks.forEach(kt => { const d = t - kt; if (d >= 0 && d < 0.26) kick = Math.max(kick, (1 - d / 0.26)); });
        const sc2 = (s0 + (s1 - s0) * ease.inout(p)) * (1.14 - 0.14 * inP) * (1 + 0.045 * ease.out(kick));
        vin.style.transform = `translate(${dir * (1 - inP) * 40}px,0) rotate(${dir * (1 - inP) * 2 + Math.sin(t * 0.8) * 0.4}deg) scale(${sc2})`;
      });
    },
    buildGlobal(stage, spec, scenes) {
      SPEC = spec; scenesRef = scenes;
      const bg = h('div'); bg.style.cssText = 'position:absolute;inset:0;z-index:0'; stage.prepend(bg);
      const glow = h('div', 'glow'); bg.appendChild(glow);
      const bok = [];
      for (let k = 0; k < 26; k++) { const b = h('div', 'bokeh'); const s = 3 + KV.rand(k + 1) * 9; b.style.width = b.style.height = s + 'px'; bg.appendChild(b); bok.push({ b, x: KV.rand(k + 11) * spec.W, y: KV.rand(k + 21) * spec.H, v: 6 + KV.rand(k + 31) * 16, o: 0.08 + KV.rand(k + 41) * 0.3 }); }
      bg.appendChild(h('div', 'vign'));
      stage.querySelectorAll('.scene').forEach(s => s.style.zIndex = 2);
      const hdr = h('div', 'hdr', `<div class="kick"></div><div class="brand">${spec.logo ? `<img src="${spec.logo}">` : ''}<span>${esc(spec.brand || 'CraftLayer')}</span></div>`); stage.appendChild(hdr);
      KICK = hdr.querySelector('.kick');
      stage.appendChild(h('div', 'handle', esc(spec.handle || '@craftlayer.studio')));   // watermark: always on
      this._prog = h('div', 'prog'); stage.appendChild(this._prog);
      if (spec.badge) stage.appendChild(h('div', 'badge', `<span>${esc(spec.badge)}</span>`));
      // captions: lines of <= capChars characters, broken after punctuation
      const maxC = spec.capChars || 16, top = spec.capTop || 975;
      spec.scenes.forEach((sc, si) => {
        const end = si + 1 < spec.scenes.length ? spec.scenes[si + 1].t0 : spec.duration;
        let line = [];
        const flush = () => { if (line.length) CAP.push({ ws: line, si, end }); line = []; };
        (sc.words || []).forEach(w => {
          const len = line.reduce((a, x) => a + x.w.length + 1, 0);
          if (line.length && len + w.w.length > maxC) flush();
          line.push(w);
          if (/[,.!?।…:;]$/.test(w.w) && len > 8) flush();
        });
        flush();
      });
      CAP.forEach((L, k) => {
        const nx = CAP[k + 1];
        L.t0 = L.ws[0].t - 0.05;
        L.t1 = nx && nx.si === L.si ? nx.ws[0].t - 0.05 : Math.min(L.end, L.ws[L.ws.length - 1].e + 1.0);
        const d = h('div', 'capline'); d.style.top = top + 'px'; stage.appendChild(d);
        L.spans = L.ws.map((w, j) => { const s = h('span', 'w', esc(w.w.replace(/[।]/g, '')) + (j < L.ws.length - 1 ? ' ' : '')); d.appendChild(s); return s; });
        L.node = d;
      });
      this._bok = bok; this._glow = glow;
    },
    global(t, cur) {
      const bok = this._bok || [];
      bok.forEach((p, k) => { const y = ((p.y - t * p.v) % SPEC.H + SPEC.H) % SPEC.H; p.b.style.transform = `translate(${p.x + Math.sin(t * 0.5 + k) * 12}px,${y}px)`; p.b.style.opacity = p.o * (0.6 + 0.4 * Math.sin(t * 1.3 + k)); });
      if (this._glow) this._glow.style.transform = `translate(${Math.sin(t * 0.3) * 40}px,${Math.cos(t * 0.25) * 30}px) scale(${1 + Math.sin(t * 0.7) * 0.05})`;
      if (this._prog) this._prog.style.transform = `scaleX(${clamp(t / SPEC.duration)})`;
      const sc = scenesRef[cur].sc; const ch = sc.chapter || '';
      if (KICK.textContent !== ch) KICK.textContent = ch;
      KICK.style.opacity = clamp((t - sc.t0) / 0.3);
      CAP.forEach(L => {
        const on = t >= L.t0 && t < L.t1; L.node.style.display = on ? 'block' : 'none'; if (!on) return;
        L.ws.forEach((w, j) => {
          const s = L.spans[j]; const p = clamp((t - w.t + 0.03) / 0.12);
          const nxt = j + 1 < L.ws.length ? L.ws[j + 1].t : L.t1; const live = t >= w.t - 0.03 && t < nxt;
          s.style.opacity = t < w.t - 0.03 ? 0 : 1;
          s.style.transform = `translateY(${(1 - ease.out(p)) * 14}px) scale(${(1.4 - 0.4 * ease.back(p)) * (live ? 1.06 : 1)})`;
          s.style.color = w.acc || live ? C.accent : C.text;
        });
      });
    },
    visible(S, cur, t) {
      const dt = t - S[cur].sc.t0, TR = 0.16;
      if (cur > 0 && dt < TR) {
        const p = ease.inout(clamp(dt / TR)), into = S[cur].sc.tone === 'good';
        return [[cur - 1, { z: 3, o: 1 - p, f: `blur(${p * 16}px)`, tf: into ? `scale(${1 + p * 0.6})` : `translateY(${-p * 18}%) scale(${1 - p * 0.08})` }], [cur, { z: 2 }]];
      }
      return [[cur, { z: 2 }]];
    },
  };
  window.STYLE = STYLE;
})();
