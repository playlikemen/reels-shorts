// Small set of generic, original stroke icons (24x24) used by both styles. No brand logos on purpose:
// a channel should show product names as text, not redraw other companies' marks.
(function () {
  const P = {
    terminal: '<rect x="2.5" y="4" width="19" height="16" rx="2.5"/><path d="M7 9.5l3 2.5-3 2.5M12.5 15h4.5"/>',
    branch: '<circle cx="6" cy="5.5" r="2.2"/><circle cx="6" cy="18.5" r="2.2"/><circle cx="18" cy="8" r="2.2"/><path d="M6 7.7v8.6M18 10.2c0 4-6 3.3-11 6.4"/>',
    cloud: '<path d="M7 18.5h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.5 1.5A3.3 3.3 0 0 0 7 18.5z"/>',
    bolt: '<path d="M13 2.5L4.5 13.5H11l-1 8 8.5-11H12l1-8z"/>',
    code: '<path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5M13.5 4.5l-3 15"/>',
    chip: '<rect x="6" y="6" width="12" height="12" rx="1.5"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/>',
    globe: '<circle cx="12" cy="12" r="9.5"/><ellipse cx="12" cy="12" rx="4" ry="9.5"/><path d="M2.5 12h19"/>',
    check: '<path d="M4.5 12.5l5 5 10-11"/>',
    bookmark: '<path d="M6.5 3.5h11v17.5l-5.5-4-5.5 4z"/>',
    cursor: '<path d="M5 3.5l13.5 7-6 1.6-2.6 6.4z"/>',
    spark: '<path d="M12 2.5c.7 5.2 4.3 8.8 9.5 9.5-5.2.7-8.8 4.3-9.5 9.5-.7-5.2-4.3-8.8-9.5-9.5 5.2-.7 8.8-4.3 9.5-9.5z"/>',
    doc: '<path d="M6 2.5h8l4.5 4.5v14.5H6z"/><path d="M14 2.5V7h4.5M9 12h6.5M9 15.5h6.5"/>',
    users: '<circle cx="9" cy="8.5" r="3.3"/><path d="M2.8 19.5c.8-3.4 3.3-5.3 6.2-5.3s5.4 1.9 6.2 5.3"/><circle cx="17" cy="9.5" r="2.6"/><path d="M16.5 14.4c2.3.2 4 1.8 4.7 4.6"/>',
    shield: '<path d="M12 2.5l8 3v6c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10v-6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    router: '<rect x="3" y="12.5" width="18" height="7" rx="1.8"/><path d="M7 12.5L5.5 5M17 12.5L18.5 5M7 16h.01M10.5 16h.01"/>',
    layers: '<path d="M12 3l9.5 5-9.5 5-9.5-5z"/><path d="M2.5 12.5l9.5 5 9.5-5M2.5 16.5l9.5 5 9.5-5"/>',
    book: '<path d="M4 4.5h6.5a2.5 2.5 0 0 1 2.5 2.5v13a2 2 0 0 0-2-2H4z"/><path d="M20 4.5h-6.5A2.5 2.5 0 0 0 11 7v13a2 2 0 0 1 2-2h7z"/>',
    star: '<path d="M12 3l2.8 5.8 6.2.9-4.5 4.4 1.1 6.2L12 17.4l-5.6 2.9 1.1-6.2L3 9.7l6.2-.9z"/>',
    lock: '<rect x="4.5" y="10.5" width="15" height="10.5" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    gauge: '<path d="M3.5 17a8.5 8.5 0 1 1 17 0"/><path d="M12 17l4.5-6"/>',
    trend: '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    server: '<rect x="3.5" y="3.5" width="17" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="17" height="7" rx="1.5"/><path d="M7.5 7h.01M7.5 17h.01"/>',
    eye: '<path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5l5 5"/>',
    play: '<path d="M7 4.5v15l12-7.5z"/>',
    pr: '<circle cx="6" cy="5.5" r="2.2"/><circle cx="6" cy="18.5" r="2.2"/><circle cx="18" cy="18.5" r="2.2"/><path d="M6 7.7v8.6M18 16.3V9a3 3 0 0 0-3-3h-4M13 3.5L10.5 6l2.5 2.5"/>',
  };
  window.KV = window.KV || {};
  KV.icon = (name, o = {}) => {
    const s = o.stroke || 'currentColor', w = o.w || 1.9, f = o.fill || 'none', size = o.size || 48;
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="${f}" stroke="${s}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round">${P[name] || P.spark}</svg>`;
  };
  KV.iconNames = Object.keys(P);
})();
