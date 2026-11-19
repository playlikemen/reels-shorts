// Deterministic timeline runtime shared by every style.
// The page never animates on its own: the renderer calls window.__seek(t) for every frame,
// and every visual property is a pure function of t. That makes renders frame-exact and repeatable.
(function () {
  const R = (window.KV = {});
  R.clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  R.ease = {
    lin: p => p,
    out: p => 1 - Math.pow(1 - p, 3),
    out5: p => 1 - Math.pow(1 - p, 5),
    inout: p => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    back: p => { const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); },
    expo: p => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p)),
    elastic: p => (p <= 0 ? 0 : p >= 1 ? 1 : Math.pow(2, -9 * p) * Math.sin((p * 10 - 0.75) * (2 * Math.PI) / 3.2) + 1),
  };
  R.h = (tag, cls, html) => { const n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; };
  R.esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  // deterministic pseudo random
  R.rand = (seed) => { let x = Math.sin(seed * 12.9898) * 43758.5453; return x - Math.floor(x); };

  // ---- entrance animations: return {transform, opacity, filter, clip} for progress p (0..1, eased inside)
  const A = {
    none: p => ({}),
    fade: p => ({ o: R.ease.out(p) }),
    up: p => { const e = R.ease.out(p); return { o: R.clamp(p * 2.5), tf: `translateY(${(1 - e) * 46}px)` }; },
    down: p => { const e = R.ease.out(p); return { o: R.clamp(p * 2.5), tf: `translateY(${-(1 - e) * 46}px)` }; },
    left: p => { const e = R.ease.out5(p); return { o: R.clamp(p * 3), tf: `translateX(${-(1 - e) * 90}px)` }; },
    right: p => { const e = R.ease.out5(p); return { o: R.clamp(p * 3), tf: `translateX(${(1 - e) * 90}px)` }; },
    pop: p => { const e = R.ease.back(p); return { o: R.clamp(p * 4), tf: `scale(${0.55 + 0.45 * e})` }; },
    slam: p => { const e = R.ease.expo(p); return { o: R.clamp(p * 5), tf: `scale(${1.7 - 0.7 * e})` }; },
    stamp: p => { const e = R.ease.back(p); return { o: R.clamp(p * 5), tf: `scale(${2.2 - 1.2 * e}) rotate(${(1 - e) * -14}deg)` }; },
    wipe: p => { const e = R.ease.out5(p); return { clip: `inset(-20% ${(1 - e) * 100}% -20% -2%)` }; },
    wipeup: p => { const e = R.ease.out5(p); return { clip: `inset(${(1 - e) * 100}% -2% -2% -2%)` }; },
    drop: p => { const e = R.ease.back(p); return { o: R.clamp(p * 4), tf: `translateY(${-(1 - e) * 160}px) rotate(${(1 - e) * 10}deg)` }; },
    blur: p => { const e = R.ease.out(p); return { o: e, tf: `translateY(${(1 - e) * 10}px)`, f: `blur(${(1 - e) * 10}px)` }; },
    zoom: p => { const e = R.ease.out5(p); return { o: R.clamp(p * 3), tf: `scale(${0.2 + 0.8 * e})` }; },
  };
  R.anims = A;

  // ---- registry built per render
  let SPEC = null, SCENES = [];
  R.events = [];
  R.sfx = (t, kind, g) => { if (t != null && isFinite(t)) R.events.push({ t: +t.toFixed(3), sfx: kind, g: g || 1 }); };

  // Context passed to style builders for one scene
  R.makeCtx = (scene) => {
    const ups = [];
    const ctx = {
      scene, ups,
      // register an entrance animation on a node
      anim(node, kind, tin, dur = 0.45, base = '', sfx = null) {
        node.style.willChange = 'transform,opacity';
        const fn = A[kind] || A.pop;
        if (sfx) R.sfx(tin, sfx);
        ups.push(t => {
          const p = R.clamp((t - tin) / dur);
          if (t < tin) { node.style.visibility = 'hidden'; return; }
          node.style.visibility = 'visible';
          const s = fn(p);
          node.style.opacity = s.o == null ? 1 : s.o;
          node.style.transform = (base || '') + ' ' + (s.tf || '');
          node.style.filter = s.f || 'none';
          node.style.clipPath = s.clip || 'none';
        });
      },
      // exit (fade/blur out) on a node
      exit(node, tout, dur = 0.25) {
        ups.push(t => { if (t >= tout) { const p = R.clamp((t - tout) / dur); node.style.opacity = Math.min(+node.style.opacity || 1, 1 - p); } });
      },
      custom(fn) { ups.push(fn); },
    };
    return ctx;
  };

  window.__init = (spec, style) => {
    SPEC = spec;
    // spec.theme = {colourName: "#hex"} recolours a style per brand: it overrides the style's palette and CSS variables.
    if (spec.theme) {
      const before = Object.assign({}, R.palette || {});
      Object.assign(R.palette || {}, spec.theme);
      // background tables were built from the old palette: swap the old hex for the new one
      for (const tbl of Object.values(R.themeTables || {}))
        for (const k of Object.keys(tbl))
          for (const [name, hex] of Object.entries(spec.theme)) if (before[name] && tbl[k] === before[name]) { tbl[k] = hex; break; }
      for (const [k, v] of Object.entries(spec.theme)) document.documentElement.style.setProperty('--' + k, v);
    }
    const stage = document.getElementById('stage');
    stage.style.width = spec.W + 'px'; stage.style.height = spec.H + 'px';
    document.body.classList.add(spec.W > spec.H ? 'land' : 'port');
    SCENES = spec.scenes.map((sc, i) => {
      const root = R.h('div', 'scene');
      stage.appendChild(root);
      const ctx = R.makeCtx(sc);
      style.buildScene(sc, i, root, ctx, spec);
      return { sc, root, ups: ctx.ups };
    });
    if (style.buildGlobal) style.buildGlobal(stage, spec, SCENES);
    R.style = style;
    return { events: R.events, duration: spec.duration };
  };

  window.__seek = (t) => {
    let cur = 0;
    for (let i = 0; i < SCENES.length; i++) if (t >= SCENES[i].sc.t0) cur = i;
    const vis = R.style.visible ? R.style.visible(SCENES, cur, t) : [[cur, {}]];
    const on = new Set(vis.map(v => v[0]));
    SCENES.forEach((S, i) => { S.root.style.display = on.has(i) ? 'block' : 'none'; });
    for (const [i, st] of vis) {
      const S = SCENES[i];
      S.root.style.transform = st.tf || 'none';
      S.root.style.zIndex = st.z || 1;
      S.root.style.opacity = st.o == null ? 1 : st.o;
      S.root.style.filter = st.f || 'none';
      S.root.style.clipPath = st.clip || 'none';
      for (const u of S.ups) u(t);
    }
    if (R.style.global) R.style.global(t, cur);
  };
})();
