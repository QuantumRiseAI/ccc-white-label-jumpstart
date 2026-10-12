// Every account number a console shows must have its name beside it.
//   node tests/audit_account_names.js [console.html ...]   (default: both consoles in consoles/)
// Renders every page (with an entry recoded and one approved, so the editable entries and
// the Export page are filled), reads the visible text, and lists each account number whose
// name does not follow within the same line. Exits 1 if any is missing.
let chromium; try { ({ chromium } = require('playwright')); }
catch (e) { ({ chromium } = require(process.env.PLAYWRIGHT || '/Users/anniebritton/.npm/_npx/520e866687cefe78/node_modules/playwright')); }
const path = require('path');
const B = path.resolve(__dirname, '..') + '/';
const files = process.argv.slice(2).length ? process.argv.slice(2) : [B + 'consoles/serif-gl-coding-review.html', B + 'consoles/serif-pl-flux.html'];
(async () => {
  const b = await chromium.launch(); let bad = 0;
  for (const f of files){
    const p = await b.newPage({viewport: {width: 1440, height: 900}});
    await p.goto('file://' + f); await p.waitForTimeout(300);
    const res = await p.evaluate(() => {
      const acct = DATA.acct, out = new Map();
      // fill the dynamic parts: approve every flag and open every recode
      $$('[data-item]').forEach(x => { const id = x.dataset.item; if (DATA.je[id]) S.dec[id] = {v: DATA.je[id].when === 'recode' ? 'recode' : 'approve', at: ''}; });
      refresh();
      const pages = $$('.page').map(p => p.id.slice(2));
      for (const pid of pages){
        $$('.page').forEach(p => p.hidden = p.id !== 'p-' + pid);
        $$('[data-pane]').forEach(x => x.hidden = false);
        $$('details').forEach(d => d.open = true);
        const pg = document.getElementById('p-' + pid);
        // inputs hold codes: read them as text with what follows
        pg.querySelectorAll('input[data-jef$="|account"]').forEach(inp => { const sm = inp.parentElement.querySelector('[data-jean]');
          const code = inp.value.trim(); if (code && !(sm && sm.textContent.trim())) out.set(pid + ' | entry editor: ' + code, 1); });
        const lines = pg.innerText.split('\n');
        lines.forEach((ln, i) => {
          const re = /\b([1-8]\d{6})\b/g; let m;
          while ((m = re.exec(ln))){
            const code = m[1], name = acct[code];
            const around = (ln.slice(m.index) + ' ' + (lines[i + 1] || '')).slice(0, 200).toLowerCase();
            if (/(Bill|Journal|Credit|Invoice|Payment|Check|Deposit)\s+$|[-A-Z]$/i.test(ln.slice(0, m.index).slice(-12)) && !/ - $/.test(ln.slice(0, m.index).slice(-3))) continue;
            if (!name && /^ \(no name in the exports\)/.test(ln.slice(m.index + 7))) continue;
            if (!name){ if (/\d{8,}/.test(ln.slice(Math.max(0, m.index - 1), m.index + 9))) continue; out.set(pid + ' | ' + code + ' (no name known) | ' + ln.trim().slice(0, 120), 1); continue; }
            if (!around.includes(name.toLowerCase().slice(0, 12))) out.set(pid + ' | ' + code + ' ' + name + ' | ' + ln.trim().slice(0, 120), 1);
          }
        });
      }
      return [...out.keys()];
    });
    console.log(path.basename(f) + ': ' + res.length + ' without a name');
    res.slice(0, 60).forEach(x => console.log('  ' + x)); bad += res.length;
    await p.close();
  }
  await b.close(); process.exit(bad ? 1 : 0);
})();
