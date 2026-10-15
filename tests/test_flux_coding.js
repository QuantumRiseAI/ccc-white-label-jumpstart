// The P&L Flux with the GL Coding Review's decision record: the record is made in the built GL
// console (approve three recodes, reject one, modify one with no note, approve a Journal Entry
// Claude drafted, mark one Edited in NetSuite), the flux is built with it, and the MoM table
// carries the corrections, flags on the adjusted figure, and notes the open and held findings.
// Run after `make build PERIOD=aug2026`:   node tests/test_flux_coding.js   (or: make test)
let chromium; try { ({ chromium } = require('playwright')); }
catch (e) { ({ chromium } = require(process.env.PLAYWRIGHT || '/Users/anniebritton/.npm/_npx/520e866687cefe78/node_modules/playwright')); }
const fs = require('fs'), path = require('path'), os = require('os'), cp = require('child_process');
const B = path.resolve(__dirname, '..') + '/', O = B + 'out/aug2026/', D = B + 'out/dist/pl-flux/', DG = B + 'out/dist/gl-coding-review/';
let fails = 0;
const ok = (c, m) => { console.log((c ? '  PASS ' : '  FAIL ') + m); if (!c) fails++; };
const num = s => Number(String(s).replace(/[^0-9.\-]/g, '')) * (/\(/.test(s) ? -1 : 1);

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'serif-fluxcoding-'));
  const b = await chromium.launch();
  try {
    const GL = fs.readdirSync(B + 'inputs/aug2026').filter(f => /^netsuite_gl_detail_.*\.xls$/.test(f)).map(f => B + 'inputs/aug2026/' + f);
    const IS = fs.readdirSync(B + 'inputs/aug2026').filter(f => /^netsuite_income_statement_by_month_.*\.xls$/.test(f)).map(f => B + 'inputs/aug2026/' + f);
    // A coding console built with a drafted Journal Entry: 1,000 from 6607000 to 6410000
    const drafts = path.join(tmp, 'coding-drafts.json');
    fs.writeFileSync(drafts, JSON.stringify({entries: [{date: '2026-08-31', memo: 'Test reclass', reason: 'Test', lines: [
      {account: '6410000', department: 'Platform', vendor: 'Test', debit: 1000, credit: 0}, {account: '6607000', department: 'Platform', vendor: 'Test', debit: 0, credit: 1000}]}]}));
    const glOut = path.join(tmp, 'gl');
    const g = cp.spawnSync('python3', ['build_pages.py', '--only', 'coding', '--coding-run', O + 'gl-coding-review/run.json', '--gl', ...GL, '--out', glOut, '--drafts', drafts], {cwd: DG, encoding: 'utf8'});
    ok(g.status === 0, 'coding console builds with a drafted Journal Entry');
    const ctx = await b.newContext({acceptDownloads: true}), p = await ctx.newPage();
    await p.goto('file://' + path.join(glOut, 'serif-gl-coding-review-aug2026-v2.0.0.html'));
    const find = from => p.evaluate(from => Object.keys(DATA.je).filter(id => document.querySelector('[data-item="' + id + '"][data-flag]') && new RegExp('from ' + from + ' to 6410000').test(DATA.je[id].memo))
      .sort((a, c) => DATA.je[c].lines[0].debit - DATA.je[a].lines[0].debit), from);
    const fac = await find('6607000'), syn = await find('6501100');
    const draftId = await p.evaluate(() => Object.keys(DATA.je).find(id => /^DRAFT-\d{2}$/.test(refOf(id)) && DATA.je[id].memo === refOf(id) + " | Test reclass | Aug'26"));
    ok(!!draftId, 'the drafted entry is a card in the coding console, its Memo led by its reference ID');
    const approve = [fac[0], fac[1], syn[0], draftId], reject = syn[1], heldId = syn[2];
    await p.evaluate(() => show('dept'));
    await p.click('#p-dept [data-foldall="0"]');   // the page opens folded; Expand all opens every card
    for (const id of approve) await p.click('[data-item="' + id + '"] [data-v="approve"]');
    await p.click('[data-item="' + reject + '"] [data-v="reject"]');
    await p.click('[data-item="' + heldId + '"] [data-v="modify"]');          // no note: not decided
    const nsId = await p.evaluate(() => Object.keys(DATA.je).find(id => document.querySelector('[data-item="' + id + '"][data-flag]') && /from 6607000 to 6810000/.test(DATA.je[id].memo)));   // fixed on the bill in NetSuite
    await p.click('[data-item="' + nsId + '"] [data-v="netsuite"]');
    const nsAmt = await p.evaluate(id => DATA.je[id].lines.filter(l => l.account === '6607000').reduce((a, l) => a + l.credit - l.debit, 0), nsId);
    await p.evaluate(() => show('settings'));
    const [d] = await Promise.all([p.waitForEvent('download'), p.click('[data-recsave]')]);
    const rec = path.join(tmp, 'coding-record.json'); await d.saveAs(rec);
    const recJ = JSON.parse(fs.readFileSync(rec, 'utf8'));
    ok(recJ.console_kind === 'coding' && recJ.dec[heldId].v === 'modify', 'coding decision record saved from the GL console');
    ok(recJ.dec[nsId].v === 'netsuite' && nsAmt > 0, 'an item edited in NetSuite is in the record');

    let n = 0;
    const build = (extra, name, fluxRun) => { const out = path.join(tmp, name || 'b' + (n++));
      const r = cp.spawnSync('python3', ['build_pages.py', '--only', 'flux', '--flux-run', fluxRun || O + 'pl-flux/run.json', '--gl', ...GL, '--income-statement', IS[0], '--out', out, ...extra], {cwd: D, encoding: 'utf8'});
      return {out: path.join(out, 'serif-pl-flux-aug2026-v2.0.0.html'), r}; };
    const CODING = ['--coding-run', O + 'gl-coding-review/run.json'];
    const w = build([...CODING, '--coding-record', rec, '--coding-drafts', drafts]);
    ok(w.r.status === 0 && /4 booked Journal Entries/.test(w.r.stdout), 'flux builds with the coding run, record and drafts: ' + (w.r.stdout.split('\n')[0] || w.r.stderr.slice(-200)));
    const wd = build([...CODING, '--coding-record', rec]);
    ok(/3 booked Journal Entries/.test(wd.r.stdout) && /pass --coding-drafts/.test(wd.r.stdout), 'without the coding drafts the drafted entry is listed as not applied');
    ok(/1 decision held, not applied/.test(w.r.stdout), 'a modify with no note is held and listed');
    const wo = build([]);
    ok(wo.r.status === 0 && !/Corrections/.test(fs.readFileSync(wo.out, 'utf8').split('<script')[0]), 'without the inputs the MoM table has no corrections');

    const open = async f => { const q = await b.newPage(); await q.goto('file://' + f); await q.evaluate(() => show('ava')); return q; };
    const row = (q, a) => q.evaluate(a => { const t = [...document.querySelectorAll('#p-ava [data-pane="mom"] tr[data-var]')].find(x => x.querySelector('.code').textContent === a);
      return t && {v: Number(t.dataset.var), cells: [...t.cells].map(c => c.innerText.replace(/\s+/g, ' ').trim()), note: (t.querySelector('.cm .note') || t.querySelector('.draft.auto .dt') || {}).textContent || '', cm: (t.querySelector('.cm') || t.querySelector('.draft.auto .dt')).textContent}; }, a);   // the line's summary, an Auto Draft
    const q = await open(w.out), f = await row(q, '6607000'), s = await row(q, '6501100');
    // cells: account, actual, prior, reported $ var, corrections, adjusted $ var, adjusted % var, 3-mo, 6-mo, commentary
    ok(f.cells.length === 10 && num(f.cells[3]) < 0 && num(f.cells[4]) > 0, 'Facility Repairs: reported rise, and a correction signed like $ Var (favorable)');
    ok(Math.abs(num(f.cells[3]) + num(f.cells[4]) - num(f.cells[5])) < 1.5, 'Facility Repairs: adjusted move is the reported move plus the correction');
    ok(Math.abs(f.v - num(f.cells[5])) < 1.5, 'Facility Repairs: the flag runs on the adjusted figure');
    ok(/Largest vendors \(before coding corrections\)/.test(f.cm), 'Largest vendors says it is before corrections');
    // edited in NetSuite: applied like an approved recode on the coding run's own GL export, and said so
    ok(/4 booked Journal Entries and 1 item edited in NetSuite/.test(w.r.stdout) && /1 item edited in NetSuite, applied/.test(w.r.stdout), 'the item edited in NetSuite is applied, counted apart from the booked entries');
    ok(/by coding corrections \(\$[\d,]+ booked, \$[\d,]+ edited in NetSuite\)/.test(f.cm) && /Edited in NetSuite:\s*1/.test(await q.locator('#p-ava [data-pane="mom"] .sumline').innerText()), 'the row and the summary name the correction edited in NetSuite');
    const later = JSON.parse(fs.readFileSync(O + 'pl-flux/run.json', 'utf8'));
    later.manifest.inputs.forEach(i => { if ((i.roles || []).includes('netsuite_gl')) i.sha256 = '0'.repeat(64); });
    const laterP = path.join(tmp, 'flux-later-gl.json'); fs.writeFileSync(laterP, JSON.stringify(later));
    const wl = build([...CODING, '--coding-record', rec, '--coding-drafts', drafts], null, laterP);
    const fl = await row(await open(wl.out), '6607000');
    ok(/1 item edited in NetSuite, not applied: this flux reads a GL export other than the coding run's/.test(wl.r.stdout) && Math.abs(num(f.cells[4]) - num(fl.cells[4]) - nsAmt) < 1.5,
       'on another GL export, which may already hold the edit, the item edited in NetSuite is not applied');
    ok(Math.abs(s.v - num(s.cells[5])) < 1.5 && num(s.cells[5]) > 0, 'Synthesis Costs: adjusted move is a fall, flagged on the adjusted figure');
    ok(/Open coding findings, not applied/.test(s.note), 'open findings are noted on the affected row');
    const heldVendor = await p.evaluate(id => document.querySelector('[data-item="' + id + '"] .ih b').textContent, heldId);
    ok(s.note.includes(heldVendor) || (await row(q, '6410000')).note.includes(heldVendor), 'the modify with no note shows as open on its row');
    ok(await q.locator('#p-runlog td', {hasText: 'GL Coding Review run'}).count() === 1 && await q.locator('#p-runlog td', {hasText: 'held, not applied'}).count() === 1, 'run log names the coding run and the held decision');
    const other = await q.evaluate(() => { const t = [...document.querySelectorAll('#p-ava [data-pane="mom"] tr[data-var]')].find(x => x.cells[4].innerText.trim() === '');
      return [Number(t.dataset.var), num(t.cells[3].innerText), num(t.cells[5].innerText), t.cells[6].innerText.trim()]; function num(c){ c = c.trim(); return Number(c.replace(/[^0-9.]/g, '')) * (c[0] === '(' ? -1 : 1); } });
    ok(Math.abs(other[0] - other[1]) < 1.5 && Math.abs(other[0] - other[2]) < 1.5 && other[3] !== '', 'a row with no correction shows its move as adjusted');
    // the drafted entry moves 6607000 by 1,000 more than without the drafts
    const fd = await row(await open(wd.out), '6607000');
    ok(Math.abs(num(f.cells[4]) - num(fd.cells[4]) - 1000) < 1.5, 'the drafted Journal Entry is applied when the coding drafts are given');

    // decisions not in this run, and a record from another run
    const odd = JSON.parse(JSON.stringify(recJ)); odd.run_id = 'otherrun000000'; odd.dec['R-00000000'] = {v: 'approve'};
    const oddP = path.join(tmp, 'odd.json'); fs.writeFileSync(oddP, JSON.stringify(odd));
    const o = build([...CODING, '--coding-record', oddP, '--coding-drafts', drafts]);
    ok(/1 decision not in this run/.test(o.r.stdout) && /saved against coding run otherrun000000/.test(o.r.stdout), 'decisions not in the run, and a record from another run, are reported');
    ok(await (await open(o.out)).locator('#p-runlog td', {hasText: 'not in this run'}).count() === 1, 'the run log says so');
    // a correction on an account with no flux row
    const lost = JSON.parse(JSON.stringify(recJ)); lost.je[fac[0]] = [{account: '6999999', department: 'Platform', debit: 500, credit: 0}, {account: '6607000', department: 'Platform', debit: 0, credit: 500}];
    const lostP = path.join(tmp, 'lost.json'); fs.writeFileSync(lostP, JSON.stringify(lost));
    const l = build([...CODING, '--coding-record', lostP]);
    ok(/No flux row for 6999999/.test(l.r.stdout) && await (await open(l.out)).locator('#p-runlog td', {hasText: 'No flux row for 6999999'}).count() === 1, 'a correction with no flux row shows in the run log');
    // header rules from the console: a reversal date not after the Journal Date holds the entry; a later one books it
    const hdr = d => { const r = JSON.parse(JSON.stringify(recJ)); r.jh = {[fac[0]]: {reversing: 'Y', reversal_date: d}}; const f = path.join(tmp, 'h' + d + '.json'); fs.writeFileSync(f, JSON.stringify(r)); return build([...CODING, '--coding-record', f, '--coding-drafts', drafts]); };
    const h1 = hdr('2026-08-01'), h2 = hdr('2026-09-01');
    ok(/3 booked Journal Entries/.test(h1.r.stdout) && /Reversal Date is not a date after the Journal Date/.test(h1.r.stdout), 'a reversal date before the Journal Date holds the entry');
    ok(/4 booked Journal Entries/.test(h2.r.stdout), 'a reversal date after the Journal Date books it');
    // bad records fail with a message
    const bad = JSON.parse(JSON.stringify(recJ)); bad.je[fac[0]] = [{account: '6607000', debit: '5,000', credit: 0}];
    const badP = path.join(tmp, 'bad.json'); fs.writeFileSync(badP, JSON.stringify(bad));
    const r1 = build([...CODING, '--coding-record', badP]);
    ok(r1.r.status !== 0 && /not a number/.test(r1.r.stderr) && !/Traceback/.test(r1.r.stderr), 'a string amount fails with a message');
    const r2 = build(['--coding-record', rec]);
    ok(r2.r.status !== 0 && !/Traceback/.test(r2.r.stderr), 'a record without the coding run fails with a message');
    // the same page with no record: no extra columns
    ok(await (await open(wo.out)).locator('#p-ava [data-pane="mom"] > .tw > table > thead th').count() === 8, 'without the record the MoM table keeps its eight columns');
  } finally {
    await b.close();
    fs.rmSync(tmp, {recursive: true, force: true});
  }
  console.log(fails ? fails + ' failed' : 'all passed');
  process.exit(fails ? 1 : 0);
})();
