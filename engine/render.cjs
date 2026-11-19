// Frame-exact renderer: loads a style page, seeks every frame, pipes JPEG frames into ffmpeg (one file per scene),
// then joins the scene files with the concat demuxer. Usage: node render.cjs resolved.json outdir [workers]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs'), path = require('path');

(async () => {
  const [, , specPath, outDir, workersArg] = process.argv;
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  fs.mkdirSync(path.join(outDir, 'segs'), { recursive: true });
  const fps = spec.fps || 30, scale = spec.scale || 1.5;
  const total = Math.round(spec.duration * fps);
  const html = 'file://' + path.resolve(__dirname, 'styles', spec.style + '.html');
  const browser = await chromium.launch({ args: ['--font-render-hinting=none', '--disable-lcd-text'] });

  async function openPage() {
    const page = await browser.newPage({ viewport: { width: spec.W, height: spec.H }, deviceScaleFactor: scale });
    page.on('pageerror', e => { console.error('PAGE ERROR', e.message); process.exitCode = 2; });
    await page.goto(html);
    await page.evaluate(async () => {
      const faces = ['400 20px Anton', '800 20px Archivo', '700 20px Archivo', '500 20px "JetBrains Mono"', '700 20px "JetBrains Mono"',
        '400 20px "Instrument Serif"', '400 20px Inter', '600 20px Inter', '800 20px Inter', '700 20px "Space Grotesk"'];
      await Promise.all(faces.map(f => document.fonts.load(f).catch(() => null)));
      await document.fonts.ready;
    });
    const info = await page.evaluate(s => window.__init(s, window.STYLE), spec);
    return { page, info };
  }

  // scene segments in frames
  const segs = spec.scenes.map((sc, i) => {
    const a = i === 0 ? 0 : Math.round(sc.t0 * fps);
    const b = i === spec.scenes.length - 1 ? total : Math.round(spec.scenes[i + 1].t0 * fps);
    return { i, a, b };
  }).filter(s => s.b > s.a);

  const nW = Math.max(1, Math.min(+workersArg || 2, segs.length));
  const pages = [];
  for (let w = 0; w < nW; w++) pages.push(await openPage());
  fs.writeFileSync(path.join(outDir, 'events.json'), JSON.stringify(pages[0].info.events));

  // optional preview stills: spec.stills = [seconds...]
  for (const s of spec.stills || []) {
    await pages[0].page.evaluate(t => window.__seek(t), s);
    await pages[0].page.screenshot({ path: path.join(outDir, `still_${String(s).replace('.', '_')}.jpg`), type: 'jpeg', quality: 90 });
  }
  if (spec.stillsOnly) { await browser.close(); return; }

  // --only: re-render just these scenes and reuse the other scene files (timing must be unchanged)
  const todo = spec.onlyScenes ? segs.filter(s => spec.onlyScenes.includes(s.i)) : segs;
  let next = 0, done = 0; const t0 = Date.now();
  async function worker({ page }) {
    while (next < todo.length) {
      const s = todo[next++];
      const tmp = path.join(outDir, 'segs', `seg_${String(s.i).padStart(3, '0')}.tmp.mp4`);
      const fin = tmp.replace('.tmp.mp4', '.mp4');
      const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', String(spec.crf || 18), '-pix_fmt', 'yuv420p', '-r', String(fps), tmp],
        { stdio: ['pipe', 'inherit', 'inherit'] });
      const closed = new Promise(r => ff.on('close', r));
      for (let f = s.a; f < s.b; f++) {
        await page.evaluate(t => window.__seek(t), f / fps);
        const buf = await page.screenshot({ type: 'jpeg', quality: 92 });
        if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      }
      ff.stdin.end();
      const code = await closed;
      if (code !== 0) throw new Error('ffmpeg failed on scene ' + s.i);
      fs.renameSync(tmp, fin);
      done += s.b - s.a;
      process.stdout.write(`  scene ${s.i} done  (${done}/${total} frames, ${((Date.now() - t0) / 1000).toFixed(0)}s)\n`);
    }
  }
  await Promise.all(pages.map(worker));
  await browser.close();
  const list = segs.map(s => `file 'segs/seg_${String(s.i).padStart(3, '0')}.mp4'`).join('\n');
  fs.writeFileSync(path.join(outDir, 'concat.txt'), list);
  await new Promise((res, rej) => spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', path.join(outDir, 'concat.txt'), '-c', 'copy', path.join(outDir, 'video_silent.mp4')], { stdio: 'inherit' }).on('close', c => c === 0 ? res() : rej(new Error('concat failed'))));
})().catch(e => { console.error(e); process.exit(1); });
