// The P&L Flux with the GL Coding Review's decision record: the record is made in the built GL
// console (approve three recodes, reject one), the flux is built with it, and the MoM table
// carries the corrections, flags on the adjusted figure and notes the open findings.
// Run after `make build PERIOD=aug2026`:   node tests/test_flux_coding.js   (or: make test)
let chromium; try { ({ chromium } = require('playwright')); }
catch (e) { ({ chromium } = require(process.env.PLAYWRIGHT || '/Users/anniebritton/.npm/_npx/520e866687cefe78/node_modules/playwright')); }
const fs = require('fs'), path = require('path'), os = require('os'), cp = require('child_process');
const B = path.resolve(__dirname, '..') + '/', O = B + 'out/aug2026/', D = B + 'out/dist/pl-flux/';
let fails = 0;
const ok = (c, m) => { console.log((c ? '  PASS ' : '  FAIL ') + m); if (!c) fails++; };
const num = s => Number(String(s).replace(/[^0-9.\-]/g, '')) * (/\(/.test(s) ? -1 : 1);

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'serif-fluxcoding-'));
  const b = await chromium.launch(), ctx = await b.newContext({acceptDownloads: true}), p = await ctx.newPage();
  await p.goto('file://' + O + 'gl-coding-review/serif-gl-coding-review-aug2026-v2.0.0.html');
  // the reclasses out of 6607000 Facility Repairs (two) and 6501100 Synthesis Costs (one)
  const memo = id => p.evaluate(id => DATA.je[id].memo, id);
  const find = (from) => p.evaluate(from => Object.keys(DATA.je).filter(id => document.querySelector('[data-item="' + id + '"][data-flag]') && new RegExp('from ' + from + ' to 6410000').test(DATA.je[id].memo))
    .sort((a, c) => DATA.je[c].lines[0].debit - DATA.je[a].lines[0].debit), from);
  const fac = await find('6607000'), syn = await find('6501100');
  const approve = [fac[0], fac[1], syn[0]], reject = syn[1];
  await p.evaluate(() => show('dept'));
  for (const id of approve) await p.click('[data-item="' + id + '"] [data-v="approve"]');
  await p.click('[data-item="' + reject + '"] [data-v="reject"]');
  await p.evaluate(() => show('settings'));
  const [d] = await Promise.all([p.waitForEvent('download'), p.click('[data-recsave]')]);
  const rec = path.join(tmp, 'coding-record.json'); await d.saveAs(rec);
  ok(JSON.parse(fs.readFileSync(rec, 'utf8')).console_kind === 'coding', 'coding decision record saved from the GL console');

  const GL = fs.readdirSync(B + 'inputs/aug2026').filter(f => /^netsuite_gl_detail_.*\.xls$/.test(f)).map(f => B + 'inputs/aug2026/' + f);
  const IS = fs.readdirSync(B + 'inputs/aug2026').filter(f => /^netsuite_income_statement_by_month_.*\.xls$/.test(f)).map(f => B + 'inputs/aug2026/' + f);
  const build = extra => { const out = path.join(tmp, extra.length ? 'with' : 'without');
    const r = cp.spawnSync('python3', ['build_pages.py', '--only', 'flux', '--flux-run', O + 'pl-flux/run.json', '--gl', ...GL, '--income-statement', IS[0], '--out', out, ...extra], {cwd: D, encoding: 'utf8'});
    return {out: path.join(out, 'serif-pl-flux-aug2026-v2.0.0.html'), r}; };
  const w = build(['--coding-run', O + 'gl-coding-review/run.json', '--coding-record', rec]);
  ok(w.r.status === 0 && /3 booked Journal Entries/.test(w.r.stdout), 'flux builds with the coding run and record: ' + (w.r.stdout.split('\n')[0] || w.r.stderr.slice(-200)));
  const wo = build([]);
  ok(wo.r.status === 0 && !/Corrections/.test(fs.readFileSync(wo.out, 'utf8').split('<script')[0]), 'without the inputs the MoM table has no corrections');

  const q = await b.newPage();
  await q.goto('file://' + w.out); await q.evaluate(() => show('ava'));
  const row = a => q.evaluate(a => { const t = [...document.querySelectorAll('#p-ava [data-pane="mom"] tr[data-var]')].find(x => x.querySelector('.code').textContent === a);
    return t && {v: Number(t.dataset.var), cls: t.className, cells: [...t.cells].map(c => c.innerText.replace(/\s+/g, ' ').trim()), note: (t.querySelector('.cm .note') || {}).innerText || ''}; }, a);
  const f = await row('6607000'), s = await row('6501100');
  // cells: account, actual, prior, reported $ var, corrections, adjusted $ var, adjusted % var, 3-mo, 6-mo, commentary
  ok(f.cells.length === 10 && num(f.cells[3]) < 0 && num(f.cells[4]) < 0, 'Facility Repairs: reported rise and a correction out of the account');
  ok(Math.abs(num(f.cells[3]) - num(f.cells[4]) - num(f.cells[5])) < 1.5, 'Facility Repairs: adjusted move is the reported move less the correction');
  ok(Math.abs(f.v - num(f.cells[5])) < 1.5, 'Facility Repairs: the flag runs on the adjusted figure');
  ok(Math.abs(s.v - num(s.cells[5])) < 1.5 && num(s.cells[4]) < 0 && num(s.cells[5]) > 0, 'Synthesis Costs: adjusted move is a fall, flagged on the adjusted figure');
  ok(/Open coding findings, not applied/.test(s.note), 'open findings are noted on the affected row');
  ok(await q.locator('#p-runlog td', {hasText: 'GL Coding Review run'}).count() === 1, 'run log names the coding run and record');
  // a row the record leaves alone is as it was
  const other = await q.evaluate(() => { const t = [...document.querySelectorAll('#p-ava [data-pane="mom"] tr[data-var]')].find(x => x.cells[4].innerText.trim() === '');
    const c = t.cells[3].innerText.trim(); return [Number(t.dataset.var), Number(c.replace(/[^0-9.]/g, '')) * (c[0] === '(' ? -1 : 1)]; });
  ok(Math.abs(other[0] - other[1]) < 1.5, 'a row with no correction is unchanged');
  // the same page with no record: no extra columns
  const z = await b.newPage(); await z.goto('file://' + wo.out); await z.evaluate(() => show('ava'));
  ok(await z.locator('#p-ava [data-pane="mom"] th').count() === 8, 'without the record the MoM table keeps its eight columns');
  await b.close();
  console.log(fails ? fails + ' failed' : 'all passed');
  process.exit(fails ? 1 : 0);
})();
