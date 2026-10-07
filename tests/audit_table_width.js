// No table scrolls sideways on a normal screen.
//   node tests/audit_table_width.js [width]   (default 1440)
// Opens every page of both consoles at that width and lists each table wider than its card.
let chromium; try { ({ chromium } = require('playwright')); }
catch (e) { ({ chromium } = require(process.env.PLAYWRIGHT || '/Users/anniebritton/.npm/_npx/520e866687cefe78/node_modules/playwright')); }
const path = require('path');
const B = path.resolve(__dirname, '..') + '/';
const W = Number(process.argv[2]) || 1440;
(async () => {
  const b = await chromium.launch(); let bad = 0;
  for (const f of ['consoles/serif-gl-coding-review.html', 'consoles/serif-pl-flux.html']){
    const p = await b.newPage({viewport: {width: W, height: 900}});
    await p.goto('file://' + B + f); await p.waitForTimeout(300);
    const res = await p.evaluate(() => {
      $$('[data-item]').forEach(x => { const id = x.dataset.item; if (DATA.je[id]) S.dec[id] = {v: DATA.je[id].when === 'recode' ? 'recode' : 'approve', at: ''}; }); refresh();
      const out = [];
      $$('.page').forEach(pg => { $$('.page').forEach(p => p.hidden = p !== pg); $$('[data-pane]').forEach(x => x.hidden = false); $$('details').forEach(d => d.open = true);
        pg.querySelectorAll('.tw').forEach(tw => { if (tw.offsetParent && tw.scrollWidth > tw.clientWidth + 1){
          const h = (tw.closest('.card') || tw.parentElement).querySelector('.ch, h3, .l');
          out.push(pg.id.slice(2) + ' | ' + (h ? h.textContent.trim().slice(0, 60) : '') + ' | ' + tw.scrollWidth + ' > ' + tw.clientWidth); } }); });
      return [...new Set(out)];
    });
    console.log(f.split('/').pop() + ' at ' + W + 'px: ' + res.length + ' tables scroll'); res.forEach(x => console.log('  ' + x)); bad += res.length;
    await p.close();
  }
  await b.close(); process.exit(bad ? 1 : 0);
})();
