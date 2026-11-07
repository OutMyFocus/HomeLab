// node render.js jobs.json   (jobs: [[scene, out.png], ...]; serve this dir on :8765)
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2]));
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const pg = await b.newPage();
  pg.on('pageerror', e => console.log('ERR', e.message));
  for (const [sc, out] of jobs) {
    fs.writeFileSync(__dirname + '/w/scene.json', JSON.stringify(sc));
    await pg.setViewportSize({ width: sc.w || 1600, height: sc.h || 1200 });
    await pg.goto('http://127.0.0.1:8765/view.html');
    await pg.waitForFunction('window.DONE === true', null, { timeout: 300000 });
    await pg.locator('canvas').screenshot({ path: out });
    console.log('wrote', out);
  }
  await b.close();
})();
