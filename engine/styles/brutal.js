// STYLE "brutal" — neo-brutalist chapter explainer (recreates the look of video 1).
// Chapter tag + series label header, flat colour backgrounds that rotate per chapter, condensed display type,
// paper cards with hard offset shadows, highlighter labels, and a giant outlined chapter word at the bottom.
(function () {
  const { h, esc, clamp, ease, rand } = KV;
  const C = { purple: '#4B00F3', mint: '#4CFFD1', pink: '#EE248A', black: '#0A0A0A', ink: '#0A0A0A', paper: '#F1F0EC', white: '#F7F7F2', yellow: '#FFD23F', orange: '#FF7A3D' };
  const col = c => C[c] || c || C.mint;
  const onDark = c => ['black', 'ink', 'purple', '#0A0A0A', '#4B00F3'].includes(c);
  const THEMES = {
    purple: { bg: C.purple, fg: C.white, head: C.white, accent: C.mint, accent2: C.mint, hlBg: C.mint, hlFg: C.ink, chapBg: C.mint, chapFg: C.ink, shadow: C.mint, grid: 'rgba(255,255,255,.06)', rule: 'rgba(255,255,255,.8)', stroke: 'rgba(255,255,255,.38)' },
    mint: { bg: C.mint, fg: C.ink, head: C.purple, accent: C.ink, accent2: C.purple, hlBg: C.ink, hlFg: C.mint, chapBg: C.ink, chapFg: C.mint, shadow: C.purple, grid: 'rgba(10,10,10,.07)', rule: C.ink, stroke: 'rgba(10,10,10,.38)' },
    pink: { bg: C.pink, fg: C.ink, head: C.ink, accent: C.white, accent2: C.white, hlBg: C.ink, hlFg: C.mint, chapBg: C.ink, chapFg: C.pink, shadow: C.ink, grid: 'rgba(10,10,10,.08)', rule: C.ink, stroke: 'rgba(10,10,10,.4)' },
    black: { bg: C.black, fg: C.white, head: C.white, accent: C.mint, accent2: C.mint, hlBg: C.pink, hlFg: C.ink, chapBg: C.mint, chapFg: C.ink, shadow: C.pink, grid: 'rgba(255,255,255,.07)', rule: 'rgba(255,255,255,.75)', stroke: 'rgba(255,255,255,.3)' },
    paper: { bg: C.paper, fg: C.ink, head: C.purple, accent: C.pink, accent2: C.purple, hlBg: C.mint, hlFg: C.ink, chapBg: C.purple, chapFg: C.white, shadow: C.purple, grid: 'rgba(10,10,10,.07)', rule: C.ink, stroke: 'rgba(10,10,10,.35)' },
  };
  // [[accent]]  {{highlight box}}  \n = line break
  const md = s => esc(s || '').replace(/\[\[(.+?)\]\]/g, '<span class="acc">$1</span>').replace(/\{\{(.+?)\}\}/g, '<span class="hl">$1</span>').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
  const TEXT_TYPES = new Set(['kicker', 'note', 'headline', 'tag', 'tags', 'stat', 'stamp', 'serif', 'label', 'bigmono', 'quote', 'spacer']);

  function words(s) { // headline -> spans per word, markup preserved
    const out = []; const re = /\[\[(.+?)\]\]|\{\{(.+?)\}\}|(\n)|([^\s\[\{]+)/g; let m;
    while ((m = re.exec(s || ''))) {
      if (m[3]) { out.push('<br>'); continue; }
      const txt = m[1] || m[2] || m[4]; const cls = m[1] ? 'acc' : m[2] ? 'hl' : '';
      out.push(`<span class="w ${cls}">${esc(txt)}</span>`);
    }
    return out.join(' ');
  }

  const B = {};
  const base = e => (e.rot ? `rotate(${e.rot}deg)` : '') + (e.scale ? ` scale(${e.scale})` : '');

  B.kicker = (e, ctx) => { const n = h('div', 'kicker', md(e.text)); ctx.anim(n, e.anim || 'up', e.tin, 0.4, base(e)); return n; };
  B.note = (e, ctx) => { const n = h('div', 'note', md(e.text)); ctx.anim(n, e.anim || 'up', e.tin, 0.4, base(e)); return n; };
  B.quote = (e, ctx) => { const n = h('div', 'quote', '&ldquo;'); ctx.anim(n, 'pop', e.tin, 0.4); return n; };
  B.spacer = (e) => { const n = h('div'); n.style.height = (e.h || 20) + 'px'; return n; };

  B.headline = (e, ctx) => {
    const n = h('div', 'headline', words(e.text));
    if (e.size) n.style.fontSize = e.size + 'px';
    if (e.color) n.style.color = col(e.color);
    n.dataset.fit = 1;
    const ws = [...n.querySelectorAll('.w')];
    const st = e.stagger == null ? 0.09 : e.stagger;
    ws.forEach((w, i) => ctx.anim(w, e.anim || 'slam', e.tin + i * st, 0.42));
    KV.sfx(e.tin, 'pop', 0.7);
    return n;
  };

  function tagNode(it) {
    const n = h('div', 'tag', md(it.text));
    n.style.background = col(it.color || 'mint');
    n.style.color = onDark(it.color) ? C.white : C.ink;
    if (it.size) n.style.fontSize = it.size + 'px';
    return n;
  }
  B.tag = (e, ctx) => { const n = tagNode(e); ctx.anim(n, e.anim || 'wipe', e.tin, 0.4, base(e), 'pop'); return n; };
  B.tags = (e, ctx) => {
    const wrap = h('div', 'col'); wrap.style.gap = (e.gap || 8) + 'px';
    if (e.quote) wrap.appendChild(B.quote({ tin: e.tin }, ctx));
    (e.items || []).forEach((it, i) => {
      const n = tagNode(it); if (it.ml) n.style.marginLeft = it.ml + 'px';
      ctx.anim(n, it.anim || e.anim || 'wipe', it.tin != null ? it.tin : e.tin + i * 0.3, 0.4, it.rot ? `rotate(${it.rot}deg)` : '', 'pop');
      wrap.appendChild(n);
    });
    return wrap;
  };

  B.serif = (e, ctx) => { const n = h('div', 'serif', esc(e.text)); ctx.anim(n, e.anim || 'drop', e.tin, 0.55, `rotate(${e.rot == null ? -3 : e.rot}deg)`, 'pop'); return n; };
  B.label = (e, ctx) => { const n = h('div', 'label ' + (e.variant || ''), md(e.text)); ctx.anim(n, e.anim || 'pop', e.tin, 0.35, `rotate(${e.rot == null ? -2 : e.rot}deg)`, 'tick'); return n; };

  B.bigmono = (e, ctx) => {
    const n = h('div', 'bigmono' + (e.ink ? ' ink' : ''), esc(e.text));
    if (e.size) n.style.fontSize = e.size + 'px';
    if (e.color) n.style.color = col(e.color);
    const to = String(e.text), from = String(e.from || '');
    const GL = '0123456789$#%@&*?';
    ctx.anim(n, e.anim || 'up', e.tin, 0.35);
    if (from) {
      const dur = e.morph || 0.8;
      ctx.custom(t => {
        const p = (t - e.tin) / dur;
        if (p <= 0) { n.textContent = from; return; }
        if (p >= 1) { n.textContent = to; return; }
        const L = Math.max(from.length, to.length); let s = '';
        const f = Math.floor(t * 30);
        for (let i = 0; i < L; i++) {
          const settle = (i + 1) / L;
          if (p > settle * 0.9 + 0.1) s += to[i] || '';
          else if (p < 0.15) s += from[i] || '';
          else s += (to[i] === '.' || to[i] === '$' || to[i] === ' ') ? to[i] : GL[Math.floor(rand(f * 31 + i) * GL.length)];
        }
        n.textContent = s;
      });
      KV.sfx(e.tin, 'tick'); KV.sfx(e.tin + 0.25, 'tick'); KV.sfx(e.tin + dur, 'pop');
    }
    return n;
  };

  B.stat = (e, ctx) => {
    const n = h('div', 'stat', md(e.text));
    if (e.size) n.style.fontSize = e.size + 'px';
    if (e.color) n.style.color = col(e.color);
    ctx.anim(n, e.anim || 'slam', e.tin, 0.45, base(e), 'stamp');
    if (e.count) {
      const c = e.count, d = c.decimals || 0;
      ctx.custom(t => {
        const p = ease.out(clamp((t - e.tin) / (c.dur || 0.9)));
        const v = c.from + (c.to - c.from) * p;
        n.innerHTML = esc((c.prefix || '') + v.toFixed(d) + (c.suffix || ''));
      });
    }
    return n;
  };

  B.stamp = (e, ctx) => {
    const w = h('div', 'stampw');
    const n = h('div', 'stamp', md(e.text));
    n.style.background = col(e.color || 'white');
    if (onDark(e.color)) n.style.color = C.white;
    if (e.size) n.style.fontSize = e.size + 'px';
    w.appendChild(n);
    if (e.burst) {
      const b = h('div', 'burst');
      let rays = ''; for (let i = 0; i < 10; i++) { const a = i * 36; rays += `<line x1="35" y1="35" x2="${35 + 31 * Math.cos(a * Math.PI / 180)}" y2="${35 + 31 * Math.sin(a * Math.PI / 180)}"/>`; }
      b.innerHTML = `<svg width="70" height="70" stroke="${col(e.burst === true ? 'pink' : e.burst)}" stroke-width="5" stroke-linecap="round">${rays}</svg>`;
      w.appendChild(b); ctx.anim(b, 'zoom', e.tin + 0.25, 0.4, '');
      ctx.custom(t => { if (t > e.tin) b.firstChild.style.transform = `rotate(${(t - e.tin) * 40}deg)`; });
    }
    ctx.anim(w, e.anim || 'stamp', e.tin, 0.4, `rotate(${e.rot == null ? -4 : e.rot}deg)`, 'stamp');
    return w;
  };

  B.bars = (e, ctx) => {
    const wrap = h('div', 'bars');
    const H = Math.min(e.h || 360, KV.land ? 250 : 9999), BW = Math.min(e.bw || 120, KV.land ? 110 : 9999), max = e.max || Math.max(...e.items.map(i => i.value));
    if (e.gap) wrap.style.gap = e.gap + 'px';
    e.items.forEach((it, i) => {
      const tin = it.tin != null ? it.tin : e.tin + 0.15 + i * 0.35;
      const b = h('div', 'bar'); b.style.width = BW + 'px';
      const val = h('div', 'val' + (it.big ? ' big' : ''), esc(it.text != null ? it.text : it.value));
      if (it.valColor) val.style.color = col(it.valColor);
      const f = h('div', 'fill' + (it.ghost ? ' ghost' : ''));
      f.style.height = Math.max(8, it.value / max * H) + 'px'; f.style.background = col(it.color || 'mint');
      const lab = h('div', 'lab', esc(it.label || ''));
      b.append(val, f, lab); wrap.appendChild(b);
      ctx.custom(t => {
        const p = ease.out(clamp((t - tin) / 0.8));
        f.style.transform = `scaleY(${p})`; f.style.visibility = t < tin ? 'hidden' : 'visible';
        val.style.opacity = clamp((t - tin - 0.45) / 0.25);
        val.style.transform = `translateY(${(1 - p) * (Math.max(8, it.value / max * H))}px)`;
        lab.style.opacity = clamp((t - e.tin) / 0.3);
      });
      KV.sfx(tin, 'pop', 0.8);
    });
    ctx.anim(wrap, 'fade', e.tin, 0.3);
    wrap.style.minHeight = (H + 50) + 'px';
    return wrap;
  };

  B.table = (e, ctx) => {
    const n = h('div', 'card table');
    if (e.w) n.style.width = Math.min(e.w, KV.land ? 540 : 9999) + 'px';
    e.rows.forEach((r, i) => {
      const tr = h('div', 'tr');
      const k = h('div', 'k', md(r.k));
      const right = h('div'); right.style.textAlign = 'right';
      const v = h('span', 'v', esc(r.v)); right.appendChild(v);
      if (r.sub) right.appendChild(h('div', 'sub', esc(r.sub)));
      tr.append(k, right); n.appendChild(tr);
      const tin = r.tin != null ? r.tin : e.tin + 0.25 + i * 0.35;
      ctx.anim(tr, 'left', tin, 0.4, '', 'pop');
      if (r.vAt != null) ctx.anim(v, 'wipe', r.vAt, 0.35);
    });
    ctx.anim(n, e.anim || 'pop', e.tin, 0.45, base(e));
    return n;
  };

  B.timeline = (e, ctx) => {
    const n = h('div', 'tl'); const line = h('div', 'line'); n.appendChild(line);
    ctx.custom(t => { line.style.transform = `scaleY(${ease.out(clamp((t - e.tin) / 1.0))})`; });
    e.items.forEach((it, i) => {
      const tin = it.tin != null ? it.tin : e.tin + 0.2 + i * 0.4;
      const d = h('div', 'it');
      d.innerHTML = `<div class="dot"></div><div class="date">${esc(it.date || '')}</div><div class="ttl">${md(it.title)}</div>`;
      if (it.chips) {
        const cw = h('div', 'chips');
        it.chips.forEach((c, j) => {
          const cc = typeof c === 'string' ? { text: c } : c;
          const ch = h('div', 'chip ' + (cc.color || ''), md(cc.text)); cw.appendChild(ch);
          ctx.anim(ch, 'pop', cc.tin != null ? cc.tin : tin + 0.3 + j * 0.18, 0.3, '', 'tick');
        });
        d.appendChild(cw);
      }
      n.appendChild(d); ctx.anim(d, 'left', tin, 0.4, '', 'pop');
    });
    ctx.anim(n, 'fade', e.tin, 0.2);
    return n;
  };

  B.tree = (e, ctx) => {
    const n = h('div', 'tree');
    const root = h('div', 'root', (e.icon !== false ? `<span style="color:${C.mint}">${KV.icon(e.icon || 'spark', { size: 40, stroke: C.mint, fill: C.mint })}</span>` : '') + md(e.root));
    const stem = h('div', 'stem');
    n.append(root, stem);
    ctx.anim(root, 'left', e.tin, 0.4, '', 'pop');
    ctx.custom(t => { stem.style.transform = `scaleY(${ease.out(clamp((t - e.tin - 0.2) / 0.6))})`; });
    e.items.forEach((it, i) => {
      const tin = it.tin != null ? it.tin : e.tin + 0.4 + i * 0.4;
      const j = h('div', 'job');
      j.style.background = col(it.color || 'mint');
      const dark = onDark(it.color);
      if (dark) j.style.color = C.white;
      j.innerHTML = `<div class="ic">${KV.icon(it.icon || 'spark', { size: 34, stroke: dark ? C.white : C.ink })}</div><div><small>${esc(it.small || '')}</small><span>${md(it.text)}</span></div>`;
      n.appendChild(j); ctx.anim(j, 'left', tin, 0.4, '', 'pop');
    });
    return n;
  };

  B.grid = (e, ctx) => {
    const n = h('div', 'g2');
    if (e.cols) n.style.gridTemplateColumns = `repeat(${e.cols},1fr)`;
    const slots = e.slots || e.items.length;
    for (let i = 0; i < slots; i++) {
      const it = e.items[i];
      const cell = h('div', 'cell'); const slot = h('div', 'slot'); slot.style.height = (e.ch || 150) + 'px'; cell.style.height = (e.ch || 150) + 'px';
      cell.appendChild(slot); n.appendChild(cell);
      ctx.anim(slot, 'fade', e.tin, 0.3);
      if (!it) continue;
      const c = h('div', 'card');
      c.style.boxShadow = `8px 8px 0 ${col(it.shadow || ['mint', 'pink', 'purple', 'black'][i % 4])}`;
      c.innerHTML = `<div class="glyph">${KV.icon(it.icon || 'cloud', { size: 52, stroke: col(it.iconColor || 'purple'), w: 2.2 })}</div><b>${md(it.title)}</b>`;
      cell.appendChild(c);
      ctx.anim(c, 'pop', it.tin != null ? it.tin : e.tin + 0.2 + i * 0.3, 0.4, `rotate(${it.rot || (i % 2 ? 1.5 : -1.5)}deg)`, 'pop');
    }
    return n;
  };

  B.segmented = (e, ctx) => {
    const n = h('div', 'seg');
    e.items.forEach(o => n.appendChild(h('div', 'o', esc(o))));
    const sel = h('div', 'sel'); n.appendChild(sel);
    const under = e.note ? h('div', 'under', esc(e.note)) : null;
    if (under) n.appendChild(under);
    const W = 120 + 2;
    const a = e.active || 0, b = e.moveTo == null ? a : e.moveTo, mt = e.moveTin != null ? e.moveTin : e.tin + 1.5;
    ctx.anim(n, 'pop', e.tin, 0.45, '', 'pop');
    if (under) { under.style.left = (a * W) + 'px'; ctx.anim(under, 'up', e.tin + 0.5, 0.3); }
    if (b !== a) KV.sfx(mt, 'tick');
    ctx.custom(t => {
      const p = ease.back(clamp((t - mt) / 0.45));
      sel.style.left = ((a + (b - a) * p) * W - 3) + 'px';
      sel.style.opacity = t < e.tin + 0.3 ? 0 : 1;
    });
    return n;
  };

  B.vs = (e, ctx) => {
    const n = h('div', 'vs');
    const mk = (s, sh) => { const c = h('div', 'card'); c.style.boxShadow = `8px 8px 0 ${col(sh)}`; c.innerHTML = `<small>${md(s.small)}</small><div>${esc(s.value)}</div>`; return c; };
    const L = mk(e.left, e.left.shadow || 'mint'), S = h('div', 'sym', esc(e.sym || '=')), Rr = mk(e.right, e.right.shadow || 'pink');
    n.append(L, S, Rr);
    ctx.anim(L, 'drop', e.tin, 0.5, 'rotate(-2deg)', 'pop');
    ctx.anim(S, 'pop', e.tin + 0.3, 0.3);
    ctx.anim(Rr, 'drop', e.right.tin != null ? e.right.tin : e.tin + 0.45, 0.5, 'rotate(2deg)', 'pop');
    return n;
  };

  B.type = (e, ctx) => {
    const n = h('div', 'typebox'); const txt = String(e.text); const cps = e.cps || 24;
    ctx.anim(n, 'wipe', e.tin, 0.25);
    for (let i = 0; i < txt.length; i += 2) KV.sfx(e.tin + 0.2 + i / cps, 'tick', 0.5);
    ctx.custom(t => {
      const k = Math.floor(clamp((t - e.tin - 0.2) * cps, 0, txt.length));
      const cur = (Math.floor(t * 2.5) % 2 === 0 || k < txt.length) ? '▌' : ' ';
      n.textContent = (e.prefix || '') + txt.slice(0, k) + cur;
    });
    return n;
  };

  B.chart = (e, ctx) => {
    const W = e.w || 540, H = e.h || 300, pad = 42;
    const n = h('div', 'card chart'); n.style.width = (W + 36) + 'px';
    const xs = e.series.flatMap(s => s.pts.map(p => p[0])), ys = e.series.flatMap(s => s.pts.map(p => p[1]));
    const x0 = e.xmin != null ? e.xmin : Math.min(...xs), x1 = e.xmax != null ? e.xmax : Math.max(...xs);
    const y0 = e.ymin != null ? e.ymin : 0, y1 = e.ymax != null ? e.ymax : Math.max(...ys) * 1.1;
    const X = x => pad + (x - x0) / (x1 - x0 || 1) * (W - pad - 14), Y = y => H - 26 - (y - y0) / (y1 - y0 || 1) * (H - 46);
    let g = `<svg width="${W}" height="${H}" font-family="Archivo" font-weight="700" font-size="14">`;
    (e.yticks || []).forEach(v => { g += `<line x1="${pad}" x2="${W - 10}" y1="${Y(v)}" y2="${Y(v)}" stroke="#0A0A0A" stroke-opacity=".12"/><text x="${pad - 8}" y="${Y(v) + 5}" text-anchor="end" fill="#0A0A0A" fill-opacity=".6">${v}${e.yunit || ''}</text>`; });
    g += `<line x1="${pad}" y1="${H - 26}" x2="${W - 10}" y2="${H - 26}" stroke="#0A0A0A" stroke-width="2"/><line x1="${pad}" y1="10" x2="${pad}" y2="${H - 26}" stroke="#0A0A0A" stroke-width="2"/>`;
    (e.xlabels || []).forEach(([x, l]) => { g += `<text x="${X(x)}" y="${H - 6}" text-anchor="middle" fill="#0A0A0A" fill-opacity=".7">${esc(l)}</text>`; });
    e.series.forEach((s, si) => {
      const d = s.pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join(' ');
      g += `<path class="s${si}" d="${d}" fill="none" stroke="${col(s.color)}" stroke-width="4" stroke-linejoin="round"/>`;
      s.pts.forEach((p, i) => { g += `<circle class="s${si}p${i}" cx="${X(p[0])}" cy="${Y(p[1])}" r="7" fill="${col(s.color)}" stroke="#0A0A0A" stroke-width="2"/>`; if (p[2]) g += `<text class="s${si}p${i}" x="${X(p[0])}" y="${Y(p[1]) - 14}" text-anchor="middle" fill="#0A0A0A">${esc(p[2])}</text>`; });
    });
    g += '</svg>';
    n.innerHTML = g;
    if (e.legend) {
      const lg = h('div'); lg.style.cssText = 'position:absolute;left:70px;top:16px;display:flex;flex-direction:column;gap:6px';
      e.series.forEach(s => { const l = h('div', 'label', `<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:${col(s.color)};border:2px solid #0A0A0A;margin-right:8px;vertical-align:-2px"></span>${esc(s.name)}`); l.style.boxShadow = 'none'; lg.appendChild(l); });
      n.style.position = 'relative'; n.appendChild(lg);
    }
    ctx.anim(n, e.anim || 'pop', e.tin, 0.45, `rotate(${e.rot == null ? -1.5 : e.rot}deg)`, 'pop');
    e.series.forEach((s, si) => {
      const tin = s.tin != null ? s.tin : e.tin + 0.4 + si * 0.5;
      ctx.custom(t => {
        const path = n.querySelector('.s' + si); if (!path) return;
        const L = path.getTotalLength(); const p = ease.inout(clamp((t - tin) / (e.draw || 1.2)));
        path.style.strokeDasharray = L; path.style.strokeDashoffset = L * (1 - p);
        s.pts.forEach((pt, i) => n.querySelectorAll(`.s${si}p${i}`).forEach(c => { c.style.opacity = p >= i / Math.max(1, s.pts.length - 1) - 0.001 ? 1 : 0; }));
      });
    });
    return n;
  };

  const TILE = {
    sunset: 'linear-gradient(165deg,#d8642c,#8a2412 55%,#2a0a07)',
    ember: 'radial-gradient(circle at 30% 70%,#ff7a2b,#8c1c0e 42%,#160504 78%)',
    spheres: 'radial-gradient(circle at 22% 62%,#d23a2a 0 13%,transparent 14%),radial-gradient(circle at 52% 58%,#b92b25 0 15%,transparent 16%),radial-gradient(circle at 82% 64%,#d23a2a 0 11%,transparent 12%),linear-gradient(#0a0a0a 55%,#c9407a)',
    yellow: 'linear-gradient(135deg,#ffe066,#f2b705)',
    violet: 'linear-gradient(140deg,#8a4dff,#2a0c8c)',
    mint: 'linear-gradient(140deg,#7dffe0,#0aa883)',
    grain: 'repeating-linear-gradient(100deg,#e2763a 0 6px,#a63c18 6px 11px,#f3a05b 11px 14px)',
    paper: 'repeating-linear-gradient(0deg,#f1f0ec 0 22px,#f9a8cf 22px 25px)',
  };
  B.collage = (e, ctx) => {
    const n = h('div'); n.style.cssText = `position:relative;width:${e.w || 640}px;height:${e.h || 220}px`;
    (e.tiles || []).forEach((ti, i) => {
      const d = h('div', 'tile'); d.style.cssText += `position:absolute;left:${ti.x}px;top:${ti.y}px;width:${ti.w || 150}px;height:${ti.h || 150}px;background:${TILE[ti.kind] || TILE.sunset};box-shadow:7px 7px 0 ${col(ti.shadow || ['mint', 'pink', 'white'][i % 3])}`;
      n.appendChild(d); ctx.anim(d, ti.anim || 'drop', ti.tin != null ? ti.tin : e.tin + i * 0.18, 0.5, `rotate(${ti.rot || 0}deg)`, i === 0 ? 'pop' : null);
      ctx.custom(t => { if (t > (ti.tin || e.tin) + 0.5) d.style.transform = `rotate(${(ti.rot || 0) + Math.sin(t * 1.3 + i) * 0.8}deg) translateY(${Math.sin(t * 1.1 + i * 2) * 3}px)`; });
    });
    return n;
  };

  B.squiggle = (e, ctx) => {
    const n = h('div'); const cs = e.colors || ['pink', 'mint', 'pink'];
    let s = `<svg width="${e.w || 300}" height="120">`;
    cs.forEach((c, i) => { const x = 40 + i * 100; s += `<path d="M${x} 10 C ${x + 25} 30, ${x - 25} 50, ${x} 70 S ${x + 20} 100, ${x + 4} 112" fill="none" stroke="${col(c)}" stroke-width="7" stroke-linecap="round"/>`; });
    n.innerHTML = s + '</svg>';
    ctx.anim(n, 'fade', e.tin, 0.2);
    ctx.custom(t => n.querySelectorAll('path').forEach((p, i) => { const L = p.getTotalLength(); const k = clamp((t - e.tin - i * 0.12) / 0.5); p.style.strokeDasharray = L; p.style.strokeDashoffset = L * (1 - ease.out(k)); p.style.transform = `translateY(${Math.sin(t * 4 + i) * 4}px)`; }));
    return n;
  };

  B.badge = (e, ctx) => { const n = h('div', 'badge', esc(e.text || '?')); if (e.color) n.style.background = col(e.color); ctx.anim(n, 'pop', e.tin, 0.4, '', 'pop'); return n; };

  B.magnifier = (e, ctx) => {
    const n = h('div'); n.style.cssText = 'position:absolute;pointer-events:none';
    n.innerHTML = `<svg width="200" height="200"><circle cx="80" cy="80" r="58" fill="rgba(255,255,255,.12)" stroke="#0A0A0A" stroke-width="10"/><circle cx="80" cy="80" r="58" fill="none" stroke="${C.white}" stroke-width="4"/><line x1="124" y1="124" x2="180" y2="180" stroke="#0A0A0A" stroke-width="20" stroke-linecap="round"/><line x1="124" y1="124" x2="180" y2="180" stroke="${C.white}" stroke-width="10" stroke-linecap="round"/></svg>`;
    ctx.anim(n, 'right', e.tin, 0.6, '', 'whoosh');
    ctx.custom(t => { if (t > e.tin + 0.6) n.style.transform = `translate(${Math.sin((t - e.tin) * 1.6) * 14}px,${Math.cos((t - e.tin) * 1.3) * 8}px)`; });
    return n;
  };

  B.icon = (e, ctx) => {
    const n = h('div', 'card'); n.style.cssText += `width:${e.size || 120}px;height:${e.size || 120}px;display:grid;place-items:center;background:${col(e.bg || 'paper')}`;
    n.innerHTML = KV.icon(e.name, { size: (e.size || 120) * 0.55, stroke: col(e.color || 'purple'), w: 2.2 });
    ctx.anim(n, e.anim || 'pop', e.tin, 0.4, base(e), 'pop');
    return n;
  };

  B.row = (e, ctx) => { const n = h('div', 'row'); if (e.gap != null) n.style.gap = e.gap + 'px'; if (e.align) n.style.alignItems = e.align; (e.children || []).forEach(c => n.appendChild(build(c, ctx))); return n; };
  B.col = (e, ctx) => { const n = h('div', 'col'); if (e.gap != null) n.style.gap = e.gap + 'px'; (e.children || []).forEach(c => n.appendChild(build(c, ctx))); return n; };

  function build(e, ctx) {
    if (e.tin == null) e.tin = ctx.cursor; ctx.cursor = Math.max(ctx.cursor, e.tin + 0.3);
    if (e.children) e.children.forEach(c => { if (c.tin == null) c.tin = e.tin; });
    const f = B[e.type]; if (!f) throw new Error('unknown element type ' + e.type);
    const n = f(e, ctx);
    if (e.mt != null) n.style.marginTop = e.mt + 'px';
    if (e.ml != null) n.style.marginLeft = e.ml + 'px';
    if (e.w && !['table', 'chart', 'collage', 'squiggle'].includes(e.type)) n.style.width = e.w + 'px';
    if (e.self) n.style.alignSelf = e.self;
    if (e.abs && !KV.land) { n.style.position = 'absolute'; n.style.left = e.abs[0] + 'px'; n.style.top = e.abs[1] + 'px'; n.style.zIndex = e.z || 5; }
    if (e.out != null) ctx.exit(n, e.out);
    return n;
  }

  function fit(root, maxW) {
    root.querySelectorAll('[data-fit]').forEach(n => {
      let fs = parseFloat(getComputedStyle(n).fontSize);
      n.style.whiteSpace = 'nowrap';
      let guard = 0; while (n.scrollWidth > maxW && fs > 40 && guard++ < 60) { fs -= 4; n.style.fontSize = fs + 'px'; }
      n.style.whiteSpace = 'normal';
    });
  }

  const STYLE = {
    buildScene(sc, i, root, ctx, spec) {
      const land = spec.W > spec.H; KV.land = land;
      const th = THEMES[sc.bg || 'purple'] || THEMES.purple;
      Object.entries(th).forEach(([k, v]) => root.style.setProperty('--' + k, v));
      root.style.setProperty('--bg', th.bg);
      if (sc.grid !== false) root.appendChild(h('div', 'gridbg'));
      const prev = spec.scenes[i - 1];
      const chapter = sc.chapter || (prev && prev.chapter) || '';
      const changed = !prev || (prev.chapter || '') !== chapter;
      sc._changed = changed;
      const M = land ? 48 : 40;
      const hdr = h('div', 'hdr'); hdr.style.left = M + 'px'; hdr.style.right = M + 'px'; hdr.style.top = (land ? 36 : 124) + 'px';
      const chap = h('div', 'chap', esc(chapter)); const ser = h('div', 'series', esc(sc.series || spec.series || ''));
      hdr.append(chap, ser); root.appendChild(hdr);
      const r1 = h('div', 'rule'); r1.style.left = M + 'px'; r1.style.right = M + 'px'; r1.style.top = (land ? 82 : 170) + 'px'; root.appendChild(r1);
      const r2 = h('div', 'rule'); r2.style.left = M + 'px'; r2.style.right = M + 'px'; r2.style.top = (land ? 560 : 990) + 'px'; root.appendChild(r2);
      const word = sc.word || chapter.replace(/^\s*\d+\s*/, '');
      const ol = h('div', 'outline', esc(word)); ol.style.left = (M - 6) + 'px'; ol.style.top = (land ? 578 : 1022) + 'px'; root.appendChild(ol);
      const t0 = sc.t0;
      const animHdr = changed && i > 0;   // first frame of the video is the hook: chrome is already there
      const hT = animHdr ? 0 : -1;   // static chrome is visible from the scene's first frame
      ctx.anim(chap, animHdr ? 'wipe' : 'none', t0 + 0.12 + hT, 0.35);
      ctx.anim(ser, animHdr ? 'fade' : 'none', t0 + 0.2 + hT, 0.35);
      ctx.custom(t => { const p = animHdr ? ease.out(clamp((t - t0 - 0.05) / 0.5)) : 1; r1.style.transform = r2.style.transform = `scaleX(${p})`; });
      ctx.anim(ol, animHdr ? 'up' : 'none', t0 + 0.18 + hT, 0.6);
      if (changed && i > 0) KV.sfx(t0 - 0.12, 'whoosh', 0.9);
      // content
      ctx.cursor = t0 + 0.3;
      const content = h('div', 'content');
      content.style.left = M + 'px'; content.style.right = M + 'px'; content.style.top = (land ? 112 : 206) + 'px'; content.style.height = (land ? 430 : 770) + 'px';
      if (sc.justify) content.style.justifyContent = sc.justify;
      root.appendChild(content);
      let colL = content, colR = content;
      if (land) {
        content.style.flexDirection = 'row'; content.style.gap = '48px'; content.style.alignItems = 'stretch';
        colL = h('div', 'col'); colL.style.flex = '1 1 52%'; colR = h('div', 'col'); colR.style.flex = '1 1 48%'; colR.style.justifyContent = 'center';
        if (sc.justify) colL.style.justifyContent = sc.justify;
        content.append(colL, colR);
      }
      (sc.els || []).forEach(e => {
        const n = build(e, ctx);
        const texty = TEXT_TYPES.has(e.type) || ((e.type === 'row' || e.type === 'col') && (e.children || []).every(c => TEXT_TYPES.has(c.type)));
        const target = !land ? content : (e.col === 2 ? colR : e.col === 1 ? colL : (texty ? colL : colR));
        target.appendChild(n);
      });
      root.style.display = 'block';
      fit(root, land ? 560 : 640);
      const boxH = land ? 430 : 770;
      const shrink = (el, origin) => { const need = el.scrollHeight; if (need > boxH + 2) { const k = boxH / need; el.style.transformOrigin = origin; el.style.transform = `scale(${k.toFixed(4)})`; } };
      if (land) { colL.style.height = colR.style.height = 'auto'; content.style.alignItems = 'flex-start'; [colL, colR].forEach(c => { if (c.offsetHeight > boxH + 2) { const k = boxH / c.offsetHeight; c.style.transformOrigin = 'top left'; c.style.transform = `scale(${k.toFixed(4)})`; } }); }
      else shrink(content, 'top left');
      { let fs = parseFloat(getComputedStyle(ol).fontSize); const maxW = spec.W - 2 * M + 30; let g = 0; while (ol.scrollWidth > maxW && fs > 120 && g++ < 60) { fs -= 6; ol.style.fontSize = fs + 'px'; } }
    },
    visible(S, cur, t) {
      const sc = S[cur].sc; const dt = t - sc.t0; const TR = 0.34;
      if (cur > 0 && dt < TR) {
        const p = ease.inout(clamp(dt / TR));
        const kind = sc.trans || (sc._changed ? 'slide' : 'cut');
        if (kind === 'slide') return [[cur - 1, { z: 1, tf: `translateX(${-p * 18}%)` }], [cur, { z: 2, tf: `translateX(${(1 - p) * 100}%)` }]];
        if (kind === 'up') return [[cur - 1, { z: 1 }], [cur, { z: 2, tf: `translateY(${(1 - p) * 100}%)` }]];
        if (kind === 'iris') return [[cur - 1, { z: 1 }], [cur, { z: 2, clip: `circle(${p * 120}% at 50% 50%)` }]];
      }
      return [[cur, {}]];
    },
  };
  window.STYLE = STYLE;
})();
