// STYLE "clean" — minimal whiteboard explainer with word-by-word kinetic captions (recreates the look of video 2).
// Off-white canvas, dot-grid stage, captions that appear exactly as each word is spoken (grey -> ink),
// soft-shadow app tiles, dashed connector diagrams, check lists, orange accent shapes and a brand watermark.
(function () {
  const { h, esc, clamp, ease } = KV;
  const C = { accent: '#E2704C', ink: '#1B1B1B', muted: '#A2A2A2', white: '#FFFFFF' };
  KV.palette = C;   // spec.theme overrides these (see runtime.js __init)
  const mix = (a, b, p) => { const pa = a.match(/\w\w/g).map(x => parseInt(x, 16)), pb = b.match(/\w\w/g).map(x => parseInt(x, 16)); return `rgb(${pa.map((v, i) => Math.round(v + (pb[i] - v) * p)).join(',')})`; };
  const md = s => esc(s || '').replace(/\*(.+?)\*/g, '<em>$1</em>').replace(/\n/g, '<br>');

  function tile(it, size) {
    const t = h('div', 'tile ' + (it.tile || 'dark'));
    const s = it.size || size || 120; t.style.width = t.style.height = s + 'px'; t.style.borderRadius = Math.round(s * 0.23) + 'px';
    const stroke = (it.tile === 'light' || it.tile === 'none') ? (it.color || C.ink) : '#fff';
    if (it.icon) t.innerHTML = KV.icon(it.icon, { size: s * 0.55, stroke, w: 2, fill: it.fill ? stroke : 'none' });
    else t.innerHTML = `<span class="tl" style="font-size:${Math.round(s * (String(it.text).length > 4 ? 0.2 : 0.27))}px">${esc(it.text || '')}</span>`;
    return t;
  }
  function floatWrap(n, ctx, seed, amp = 5) {
    const w = h('div'); w.style.display = 'inline-block'; w.appendChild(n);
    ctx.custom(t => { w.style.transform = `translateY(${Math.sin(t * 1.4 + seed) * amp}px)`; });
    return w;
  }

  const V = {};
  V.icon = (e, ctx) => {
    const box = h('div'); box.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:14px';
    const t = tile(e, e.size || 170); box.appendChild(floatWrap(t, ctx, e.tin));
    ctx.anim(t, e.anim || 'pop', e.tin, 0.5, '', 'pop');
    if (e.fillTin != null) { // outline -> filled (e.g. bookmark saved)
      const filled = tile({ ...e, fill: true }, e.size || 170); filled.style.position = 'absolute';
      ctx.custom(tt => { const on = tt >= e.fillTin; t.innerHTML = (on ? filled : tile(e, e.size || 170)).innerHTML; t.style.transform += on && tt < e.fillTin + 0.25 ? ` scale(${1 + 0.15 * Math.sin((tt - e.fillTin) / 0.25 * Math.PI)})` : ''; });
      KV.sfx(e.fillTin, 'pop');
    }
    if (e.label) { const l = h('div', 'lbl', esc(e.label)); box.appendChild(l); ctx.anim(l, 'up', e.labelTin || e.tin + 0.2, 0.4); }
    return box;
  };
  V.tiles = (e, ctx) => {
    const r = h('div', 'row'); r.style.gap = (e.gap || 34) + 'px';
    if (e.wrap) { r.style.flexWrap = 'wrap'; r.style.maxWidth = (e.wrap) + 'px'; }
    e.items.forEach((it, i) => { const t = tile(it, e.size || 120); r.appendChild(floatWrap(t, ctx, i * 1.7, 4)); ctx.anim(t, it.anim || 'pop', it.tin != null ? it.tin : e.tin + i * 0.22, 0.45, '', 'pop'); });
    return r;
  };
  V.big = (e, ctx) => { const n = h('div', 'big', esc(e.text)); if (e.color) n.style.color = e.color === 'accent' ? C.accent : e.color; if (e.size) n.style.fontSize = e.size + 'px'; ctx.anim(n, e.anim || 'zoom', e.tin, 0.5, '', 'pop'); return n; };
  V.label = (e, ctx) => { const n = h('div', 'lbl', md(e.text)); if (e.size) n.style.fontSize = e.size + 'px'; ctx.anim(n, e.anim || 'blur', e.tin, 0.4); return n; };
  V.spacer = e => { const n = h('div'); n.style.height = (e.h || 20) + 'px'; return n; };
  V.checklist = (e, ctx) => {
    const n = h('div', 'check');
    e.items.forEach((it, i) => {
      const r = h('div', 'it', `<span style="color:${C.ink}">${KV.icon('spark', { size: e.size ? e.size * 0.9 : 34, fill: C.ink, stroke: C.ink, w: 1 })}</span><span>${md(it.text)}</span>`);
      if (e.size) r.style.fontSize = e.size + 'px';
      n.appendChild(r); ctx.anim(r, 'left', it.tin != null ? it.tin : e.tin + i * 0.5, 0.45, '', 'tick');
    });
    return n;
  };
  V.card = (e, ctx) => {
    const n = h('div', 'card');
    const cols = ['#3fb950', '#d29922', '#a371f7', '#2f81f7', '#f85149', '#db61a2'];
    n.innerHTML = `<div class="t">${esc(e.title || '')}</div>` + [1, 0.92, 0.78].map(w => `<div class="ln" style="width:${w * 100}%"></div>`).join('') +
      `<div class="chips">${cols.map((c, i) => `<span style="width:${46 + (i * 17) % 40}px;background:${c}"></span>`).join('')}</div>` +
      [0.7, 0.5].map(w => `<div class="ln" style="width:${w * 100}%"></div>`).join('') + `<div class="btn">${esc(e.button || 'Star · Fork · Install')}</div>`;
    const w = floatWrap(n, ctx, 2, 4);
    ctx.anim(n, e.anim || 'drop', e.tin, 0.55, `rotate(${e.rot || 0}deg)`, 'whoosh');
    return w;
  };
  V.ocard = (e, ctx) => {
    const n = h('div', 'ocard', `<div class="t">${esc(e.title)}</div><div class="s">${esc(e.sub || '')}</div><div class="ics">${(e.icons || []).map(ic => KV.icon(ic, { size: 64, stroke: '#2a160f', w: 1.6 })).join('')}</div>`);
    ctx.anim(n, e.anim || 'pop', e.tin, 0.5, '', 'pop');
    return floatWrap(n, ctx, 1, 4);
  };
  V.book = (e, ctx) => {
    const n = h('div', 'book', `<div class="spine"></div><div class="cover"><div class="tt">${md(e.title)}</div><div class="sb">${esc(e.sub || '')}</div><div style="position:absolute;left:30px;bottom:34px;color:#9a9a9a">${KV.icon(e.icon || 'book', { size: 120, w: 1.2, stroke: '#9a9a9a' })}</div></div>`);
    ctx.anim(n, 'right', e.tin, 0.6, '', 'whoosh');
    ctx.custom(t => { if (t > e.tin + 0.6) n.style.transform = `perspective(900px) rotateY(${-18 + Math.sin(t * 0.9) * 6}deg) rotateZ(${Math.sin(t * 0.7) * 1.5}deg)`; else n.style.transform += ' perspective(900px) rotateY(-18deg)'; });
    return n;
  };
  V.pages = (e, ctx) => {
    const n = h('div'); n.style.cssText = 'position:relative;width:420px;height:430px';
    for (let i = 0; i < 3; i++) {
      const p = h('div'); p.style.cssText = `position:absolute;left:${60 + i * 40}px;top:${10 + i * 6}px;width:280px;height:380px;background:#fff;border:8px solid #6b6b6b;border-radius:6px;box-shadow:0 20px 40px rgba(0,0,0,.2);padding:26px`;
      p.innerHTML = Array.from({ length: 11 }, (_, k) => `<div style="height:7px;border-radius:4px;margin:9px 0;width:${60 + ((k * 37 + i * 13) % 40)}%;background:${k % 5 === 0 ? C.accent : '#cfcfcf'}"></div>`).join('');
      n.appendChild(p);
      ctx.anim(p, 'drop', e.tin + i * 0.25, 0.55, `rotate(${-14 + i * 12}deg)`, i ? null : 'whoosh');
    }
    return n;
  };
  function box(el, root) { let x = 0, y = 0, e = el; while (e && e !== root) { x += e.offsetLeft; y += e.offsetTop; e = e.offsetParent; } return { left: x, top: y, width: el.offsetWidth, height: el.offsetHeight, right: x + el.offsetWidth, bottom: y + el.offsetHeight }; }
  function connectors(svg, from, tos, ctx, dashed) {
    const root = svg.parentNode; const sr = { left: 0, top: 0 };
    const fr = box(from, root);
    const fx = fr.left + fr.width / 2 - sr.left, fy = fr.bottom - sr.top;
    tos.forEach(({ node, tin }) => {
      const r = box(node, root); const tx = r.left + r.width / 2 - sr.left, ty = r.top - sr.top;
      const my = fy + (ty - fy) * 0.5;
      const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      p.setAttribute('d', dashed === 'side' ? `M${fr.right - sr.left} ${fr.top + fr.height / 2 - sr.top} L${r.left - sr.left} ${r.top + r.height / 2 - sr.top}` : `M${fx} ${fy} V${my} H${tx} V${ty}`);
      p.setAttribute('fill', 'none'); p.setAttribute('stroke', '#2a2a2a'); p.setAttribute('stroke-width', '3');
      svg.appendChild(p);
      const L = p.getTotalLength();
      ctx.custom(t => {
        const k = ease.out(clamp((t - tin + 0.25) / 0.45));
        if (dashed === true) { p.setAttribute('stroke-dasharray', '10 9'); p.style.opacity = k; p.style.clipPath = `inset(0 0 ${(1 - k) * 100}% 0)`; }
        else { p.style.strokeDasharray = L; p.style.strokeDashoffset = L * (1 - k); }
      });
    });
  }
  V.tree = (e, ctx) => {
    const n = h('div'); n.style.cssText = 'position:relative;display:flex;flex-direction:column;align-items:center;gap:' + (e.vgap || 80) + 'px';
    const root = e.root.icon || e.root.text ? tile(e.root, e.root.size || 130) : h('div');
    if (e.root.label) { root.style.position = 'relative'; }
    const rootBox = h('div'); rootBox.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:10px'; rootBox.appendChild(root);
    if (e.root.label) { const l = h('div', 'lbl', esc(e.root.label)); rootBox.appendChild(l); ctx.anim(l, 'up', e.tin + 0.15, 0.4); }
    const row = h('div', 'row'); row.style.gap = (e.gap || 46) + 'px';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('class', 'svgover');
    n.append(svg, rootBox, row);
    ctx.anim(root, 'pop', e.tin, 0.5, '', 'pop');
    const kids = e.items.map((it, i) => { const t = tile(it, e.size || 110); row.appendChild(t); const tin = it.tin != null ? it.tin : e.tin + 0.35 + i * 0.25; ctx.anim(t, 'pop', tin, 0.45, '', 'pop'); return { node: t, tin }; });
    ctx.after.push(() => connectors(svg, rootBox, kids, ctx, true));
    return n;
  };
  V.bridge = (e, ctx) => {
    const n = h('div'); n.style.cssText = 'position:relative;display:flex;align-items:center;gap:150px';
    const left = tile(e.from, e.from.size || 130); const col = h('div'); col.style.cssText = 'display:flex;flex-direction:column;gap:30px;align-items:center';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('class', 'svgover');
    n.append(svg, left, col); ctx.anim(left, 'pop', e.tin, 0.5, '', 'pop');
    const kids = e.items.map((it, i) => { const t = tile(it, e.size || 104); col.appendChild(t); const tin = it.tin != null ? it.tin : e.tin + 0.4 + i * 0.3; ctx.anim(t, 'pop', tin, 0.45, '', 'pop'); return { node: t, tin }; });
    ctx.after.push(() => connectors(svg, left, kids, ctx, 'side'));
    return n;
  };
  V.row = (e, ctx) => { const r = h('div', 'row'); if (e.gap != null) r.style.gap = e.gap + 'px'; e.children.forEach(c => r.appendChild(build(c, ctx))); return r; };

  function build(e, ctx) {
    if (e.tin == null) e.tin = ctx.cursor; ctx.cursor = Math.max(ctx.cursor, e.tin + 0.3);
    if (e.children) e.children.forEach(c => { if (c.tin == null) c.tin = e.tin; });
    const f = V[e.type]; if (!f) throw new Error('unknown clean element ' + e.type);
    const n = f(e, ctx);
    if (e.mt != null) n.style.marginTop = e.mt + 'px';
    if (e.abs) { n.style.position = 'absolute'; n.style.left = e.abs[0] + 'px'; n.style.top = e.abs[1] + 'px'; }
    if (e.out != null) ctx.exit(n, e.out);
    return n;
  }

  function splash(root, corner, ctx, t0, color) {
    const S = h('div', 'splash');
    const [v, hz] = [corner[0], corner[1]];
    S.style[v === 't' ? 'top' : 'bottom'] = '-180px'; S.style[hz === 'l' ? 'left' : 'right'] = '-180px';
    let g = '<svg width="360" height="360" viewBox="0 0 360 360">';
    [70, 112, 154].forEach((r, i) => { g += `<circle cx="180" cy="180" r="${r}" fill="none" stroke="${color}" stroke-width="${16 - i * 3}" stroke-linecap="round" stroke-dasharray="${r * 1.2} ${r * 0.5}"/>`; });
    g += `<circle cx="180" cy="180" r="34" fill="${color}"/></svg>`;
    S.innerHTML = g; root.appendChild(S);
    const circles = [...S.querySelectorAll('circle')];
    ctx.custom(t => {
      const pin = ease.back(clamp((t - t0) / 0.6)), pout = ease.inout(clamp((t - t0 - 1.7) / 0.5));
      const k = pin * (1 - pout);
      S.style.transform = `scale(${k}) rotate(${(t - t0) * 30}deg)`; S.style.opacity = k > 0.01 ? 1 : 0;
      circles.forEach((c, i) => { c.style.transformOrigin = '180px 180px'; c.style.transform = `rotate(${(t - t0) * (i % 2 ? -50 : 40)}deg)`; });
    });
    KV.sfx(t0, 'whoosh', 0.7);
  }

  const STYLE = {
    buildScene(sc, i, root, ctx, spec) {
      const land = spec.W > spec.H, W = spec.W, H = spec.H;
      ctx.after = []; ctx.cursor = sc.t0 + 0.2;
      const L = land ? { capTop: [20, 140], vis: [168, 330], capBot: [506, 132], dots: [130, 150, 1020, 380] }
        : { capTop: [96, 262], vis: [372, 430], capBot: [818, 230], dots: [40, 330, 640, 520] };
      const hasVis = sc.vis && sc.vis.length;
      if (hasVis && sc.dots !== false) { const d = h('div', 'dots'); const [x, y, w, hh] = L.dots; Object.assign(d.style, { left: x + 'px', top: y + 'px', width: w + 'px', height: hh + 'px' }); root.appendChild(d); ctx.anim(d, 'fade', sc.t0, 0.5); }
      const mkCap = (top, hh, just) => { const c = h('div', 'cap'); c.style.top = top + 'px'; c.style.height = hh + 'px'; c.style.justifyContent = just; root.appendChild(c); return c; };
      let capT, capB;
      if (hasVis) { capT = mkCap(L.capTop[0], L.capTop[1], 'flex-end'); capB = mkCap(L.capBot[0], L.capBot[1], 'flex-start'); }
      else { capT = capB = mkCap(0, H - (land ? 60 : 160), 'center'); }
      (sc.cap || []).forEach(seg => {
        const s = h('div', 'seg ' + (seg.size || 'm') + (seg.upper ? ' up' : '') + (seg.style === 'pill' ? ' pill' : ''));
        const target = seg.pos === 'bottom' ? capB : capT; target.appendChild(s);
        const final = seg.color === 'accent' ? C.accent : C.ink;
        (seg.ws || []).forEach((w, k) => {
          const sp = h('span', 'wd', esc(w.w) + (k < seg.ws.length - 1 ? ' ' : ''));
          s.appendChild(sp);
          ctx.custom(t => {
            const p = clamp((t - w.t) / 0.2);
            if (t < w.t) { sp.style.opacity = 0; return; }
            sp.style.opacity = R(p); sp.style.filter = `blur(${(1 - p) * 5}px)`; sp.style.transform = `translateY(${(1 - ease.out(p)) * 12}px)`;
            sp.style.color = mix('A2A2A2', final.slice(1), clamp((t - w.t - 0.1) / 0.35));
          });
        });
        if (seg.style === 'pill' && seg.ws && seg.ws.length) ctx.anim(s, 'pop', seg.ws[0].t - 0.05, 0.4, '', 'pop');
      });
      if (hasVis) {
        const vis = h('div', 'vis'); vis.style.top = L.vis[0] + 'px'; vis.style.height = L.vis[1] + 'px'; root.appendChild(vis);
        const inner = h('div'); inner.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:26px;transform-origin:50% 50%';
        vis.appendChild(inner);
        sc.vis.forEach(e => inner.appendChild(build(e, ctx)));
        root.style.display = 'block';
        if (inner.offsetHeight > L.vis[1]) inner.style.transform = `scale(${(L.vis[1] / inner.offsetHeight).toFixed(4)})`;
      }
      if (sc.splash) sc.splash.split(',').forEach(c => splash(root, c.trim(), ctx, sc.t0, spec.accent || C.accent));
      root.style.display = 'block';
      ctx.after.forEach(f => f());
    },
    buildGlobal(stage, spec) {
      if (!spec.brand) return;
      const w = h('div', 'wm', esc(spec.brand)); w.style.top = (spec.W > spec.H ? 668 : 1080) + 'px'; if (spec.W > spec.H) w.style.fontSize = '24px'; stage.appendChild(w);
    },
    visible(S, cur, t) {
      const dt = t - S[cur].sc.t0; const TR = 0.22;
      if (cur > 0 && dt < TR) { const p = clamp(dt / TR); return [[cur - 1, { z: 2, o: 1 - p, f: `blur(${p * 8}px)`, tf: `scale(${1 - p * 0.04})` }], [cur, { z: 1 }]]; }
      return [[cur, {}]];
    },
  };
  const R = x => x;
  window.STYLE = STYLE;
})();
