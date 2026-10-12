// Tests for the 2.0.0 consoles: standalone state, the decision record, the run log,
// editable entries and the NetSuite CSV, then shared mode on a mocked Artifact db:
// two reviewers, attribution, a conflict, a read-only viewer, downloads, and a rerun
// bringing in the earlier run's decisions. Needs Playwright with Chromium.
//   node tests/test_console.js [folder holding the two aug2026 v2.0.0 consoles]   (or: make test)
// With no folder, it tests consoles/.
let chromium; try { ({ chromium } = require('playwright')); }
catch (e) { ({ chromium } = require(process.env.PLAYWRIGHT || '/Users/anniebritton/.npm/_npx/520e866687cefe78/node_modules/playwright')); }
const fs = require('fs'), path = require('path'), os = require('os');
const B = path.resolve(__dirname, '..') + '/';
const DIR = process.argv[2];
const FILES = DIR ? {gl: path.join(DIR, 'serif-gl-coding-review-aug2026-v2.0.0.html'), pl: path.join(DIR, 'serif-pl-flux-aug2026-v2.0.0.html')}
  : {gl: B + 'consoles/serif-gl-coding-review.html', pl: B + 'consoles/serif-pl-flux.html'};
let fails = 0;
const ok = (c, m) => { console.log((c ? '  PASS ' : '  FAIL ') + m); if (!c) fails++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));

// The mock runtime, injected before the page's scripts. db calls go to the node hub.
const MOCK = ({uid, name, canWrite, canEdit, withDb}) => {
  const hub = (...a) => window.__hub(...a);
  const subs = [];
  const docSnap = (path, b) => ({id: path.split('/').pop(), exists: !!b, data: () => b ? JSON.parse(JSON.stringify(b)) : undefined,
    metadata: {fromCache: false, hasPendingWrites: false}});
  async function deliver(s){
    if (s.t === 'doc'){ const b = await hub('get', s.path); s.next(docSnap(s.path, b)); return; }
    const rows = await hub('list', s.path), now = new Map(rows.map(r => [r.path, JSON.stringify(r.body)])), ch = [];
    rows.forEach(r => { const was = s.prev.get(r.path);
      if (was === undefined) ch.push({type: 'added', doc: docSnap(r.path, r.body)});
      else if (was !== JSON.stringify(r.body)) ch.push({type: 'modified', doc: docSnap(r.path, r.body)}); });
    s.prev.forEach((v, p) => { if (!now.has(p)) ch.push({type: 'removed', doc: docSnap(p, JSON.parse(v))}); });
    const first = !s.started; s.started = true; s.prev = now;
    if (!first && !ch.length) return;
    const docs = rows.map(r => docSnap(r.path, r.body));
    s.next({docs, size: docs.length, empty: !docs.length, docChanges: () => ch, metadata: {fromCache: false, hasPendingWrites: false}});
  }
  window.__dbChanged = path => { subs.forEach(s => {
    const parent = path.split('/').slice(0, -1).join('/');
    if ((s.t === 'doc' && s.path === path) || (s.t === 'col' && s.path === parent)) deliver(s); }); };
  const err = code => { const e = new Error(code); e.code = code; return e; };
  const db = {
    doc(path){ return {path, id: path.split('/').pop(),
      get: async () => docSnap(path, await hub('get', path)),
      set: async b => { const r = await hub('set', path, b, uid); if (r) throw err(r); },
      update: async b => { const r = await hub('update', path, b, uid); if (r) throw err(r); },
      delete: async () => { const r = await hub('del', path, null, uid); if (r) throw err(r); },
      onSnapshot(next){ const s = {t: 'doc', path, next}; subs.push(s); setTimeout(() => deliver(s), 5); return () => {}; }}; },
    collection(path){ return {path,
      get: async () => { const rows = await hub('list', path); const docs = rows.map(r => docSnap(r.path, r.body));
        return {docs, size: docs.length, empty: !docs.length, docChanges: () => [], metadata: {fromCache: false, hasPendingWrites: false}}; },
      onSnapshot(next){ const s = {t: 'col', path, next, prev: new Map()}; subs.push(s); setTimeout(() => deliver(s), 5); return () => {}; }}; },
  };
  const names = {u_A: 'Alice Reviewer', u_B: 'Bob Checker', u_C: 'Cara Viewer'};
  const user = {
    me: async () => ({id: uid, name, avatarUrl: '', color: '#000', email: null, isOwner: uid === 'u_A', canEdit}),
    id: async () => uid, canEdit: async () => canEdit, isOwner: async () => uid === 'u_A',
    can: async n => n === 'data.write' ? canWrite : false,
    profiles: async ids => Object.fromEntries([].concat(ids).map(i => [i, {id: i, name: names[i] || '', isMe: i === uid}])),
  };
  window.__saved = [];
  const downloads = {save: async ({filename, data}) => { window.__saved.push({filename, size: String(data).length}); window.__lastData = String(data); return {status: 'saved'}; }};
  window.claude = Object.freeze({use: async n => { await new Promise(r => setTimeout(r, 30));
    return n === 'db' ? (withDb ? db : null) : n === 'user' ? user : n === 'downloads' ? downloads : null; }});
};


(async () => {
  const b = await chromium.launch();
  const errs = [];
  const firstItem = (p, sel) => p.evaluate(s => document.querySelector(s).dataset.item, sel);

  // ---- standalone ----
  for (const k of ['gl', 'pl']){
    console.log('standalone ' + k);
    const ctx = await b.newContext({acceptDownloads: true}); const p = await ctx.newPage();
    p.on('pageerror', e => errs.push(k + ' standalone: ' + e.message));
    await p.goto('file://' + FILES[k]); await p.waitForTimeout(500);
    ok(await p.locator('#sharedbar').isHidden(), k + ': no shared banner');
    const sel = k === 'gl' ? '#p-prepaid [data-flag]' : '#p-adj [data-item]';
    const id = await firstItem(p, sel);
    ok(/^[A-Z]+-[0-9a-f]{8}/.test(id), k + ': item id is built from the item (' + id + ')');
    await p.evaluate(id => decide(id, 'approve', 'x'), id);
    await p.reload(); await p.waitForTimeout(400);
    ok(await p.evaluate(id => (S.dec[id] || {}).v === 'approve', id), k + ': decision survives a reload');
    // edit the entry: marks it Modified, needs a note, then exports as edited
    await p.evaluate(() => show(DATA.kind === 'coding' ? 'prepaid' : 'adj'));
    const inp = p.locator('[data-jef="' + id + '|0|department"]');
    await inp.fill('Finance');
    ok(await p.evaluate(id => S.dec[id].v === 'modify', id), k + ': an entry edit marks the item Modified');
    ok(await p.evaluate(id => !jeReady(id), id), k + ': a Modified entry waits for its note');
    await p.fill('[data-note="' + id + '"]', 'Department per budget owner');
    ok(await p.evaluate(id => jeReady(id), id), k + ': with a note the entry is ready');
    const [dl] = await Promise.all([p.waitForEvent('download', {timeout: 4000}).catch(() => null), p.evaluate(() => exportCSV())]);
    let csvText = ''; if (dl){ const f = await dl.path(); csvText = fs.readFileSync(f, 'utf8'); }
    ok(/Finance/.test(csvText) && /Department per budget owner/.test(csvText), k + ': the CSV carries the edit and the note');
    if (k === 'gl'){
      const r = await p.evaluate(() => document.querySelector('#p-clear [data-item]').dataset.item);
      await p.evaluate(() => show('clear'));
      await p.click('[data-item="' + r + '"] [data-v="confirm"]');
      ok(await p.locator('[data-item="' + r + '"] > .ib').isHidden(), 'gl: a confirmed vendor card folds to its name');
      await p.click('[data-item="' + r + '"] > .ih b');
      ok(await p.locator('[data-item="' + r + '"] > .ib').isVisible(), 'gl: clicking the name opens it');
      await p.click('[data-item="' + r + '"] > .ih b');
      ok(await p.locator('[data-item="' + r + '"] > .ib').isHidden(), 'gl: clicking again folds it');
      await p.click('[data-item="' + r + '"] > .ih b');
      await p.click('[data-item="' + r + '"] [data-v="confirm"]');
      ok(await p.locator('[data-item="' + r + '"] > .ib').isVisible() && !(await p.evaluate(r => !!S.dec[r], r)), 'gl: undoing the confirm leaves it open');
    }
    if (k === 'gl'){
      const txt = await p.evaluate(() => { const c = [...document.querySelectorAll('#p-dept [data-item^="D-"]')].find(i => /Coupa PO/.test(i.textContent) && /DraI/.test(i.textContent)); return c ? c.querySelector('.ih b').textContent + ' | ' + c.textContent : ''; });
      ok(/^New England BioLabs Inc \|/.test(txt) && /6501100/.test(txt) && /6410000/.test(txt), 'gl: an item on an account other than its usual one shows its supplier and both accounts (DraI)');
      ok(/under \$2,500/.test(await p.locator('#p-dept > .note, #p-dept p.note').first().innerText()), 'gl: item drift under the threshold is a count and a total');
    }
    if (k === 'pl'){
      // a variance row proposes an entry: the row's account, an offset to fill, the memo from the review; it joins the same CSV
      await p.evaluate(() => show('ava'));
      const btn = p.locator('#p-ava [data-propose]').first(); const pid = await btn.getAttribute('data-propose');
      await btn.click();
      ok(await p.locator('[data-jerow="' + pid + '"]').isVisible(), 'pl: Propose entry opens a Journal Entry on the variance row');
      ok(await p.evaluate(pid => !S.dec[pid] && /^P&L flux reclass, \d{7} .+, Aug 2026: \$[\d,]+ (un)?favorable MoM$/.test(jeOf(pid).memo) && jeOf(pid).memo.length < 200 && !jeLive(pid) && !jeReady(pid), pid), 'pl: the proposal is a suggestion with a short memo, nothing approved');
      ok(await p.evaluate(pid => $('[data-propose="' + pid + '"]').getAttribute('aria-expanded') === 'true' && jeOf(pid).date === '2026-08-31' && jeOf(pid).period === 'Aug 2026', pid), 'pl: Propose entry is expanded; dated the last day of the close month');
      ok(await p.locator('#p-ava [data-pane="mom"] tr[data-var="0"] [data-propose]').count() === 0, 'pl: no Propose entry on a row with no variance');
      // begun and not finished is open, with the reason on export; Reset is the way back
      await p.fill('[data-jef="' + pid + '|0|debit"]', '500');
      ok(await p.evaluate(pid => jeOpen('ava').length === 1 && /open of/.test($('[data-checklist]').textContent) && jeWhy(pid) === 'out of balance', pid), 'pl: a begun proposal counts as open');
      await p.evaluate(() => exportCSV());
      ok(/Left out: .*out of balance/.test(await p.evaluate(() => $('#tip').textContent)), 'pl: the export names why an entry was left out');
      await p.click('[data-jereset="' + pid + '"]');
      ok(await p.evaluate(pid => !S.dec[pid] && !S.je[pid] && !S.jh[pid] && !S.notes[pid] && !jeLive(pid) && jeOpen('ava').length === 0, pid), 'pl: Reset clears a proposal, nothing is held');
      await p.fill('[data-jef="' + pid + '|0|debit"]', '500');
      await p.fill('[data-jef="' + pid + '|1|account"]', '2206000');
      await p.fill('[data-jef="' + pid + '|0|debit"]', '500'); await p.fill('[data-jef="' + pid + '|1|credit"]', '500');
      await p.fill('[data-jef="' + pid + '|0|memo"]', 'Reclass test line');
      await p.selectOption('[data-jeh="' + pid + '|reversing"]', 'Y');
      ok(await p.evaluate(pid => { S.notes[pid] = 'Reviewer note'; return !jeReady(pid); }, pid), 'pl: reversing without a reversal date is held');
      await p.fill('[data-jeh="' + pid + '|reversal_date"]', '2026-08-01');
      ok(await p.evaluate(pid => jeWhy(pid) === 'Reversal Date is not a date after the Journal Date', pid), 'pl: a reversal date before the Journal Date is held');
      await p.fill('[data-jeh="' + pid + '|period"]', 'August');
      ok(await p.evaluate(pid => jeWhy(pid) === 'Posting Period is not Mon YYYY', pid), 'pl: a Posting Period that is not Mon YYYY is held');
      await p.fill('[data-jeh="' + pid + '|period"]', 'Aug 2026');
      await p.fill('[data-jeh="' + pid + '|reversal_date"]', '2026-09-01');
      // saved edits keep main's shape: lines in je, header fields in jh; a record from main (no jh, lines without a Line Memo) still loads
      ok(await p.evaluate(pid => Array.isArray(S.je[pid]) && !Array.isArray(S.jh[pid]) && recordOf().je[pid] === S.je[pid], pid), 'pl: S.je keeps the lines array; header edits are in their own store');
      ok(await p.evaluate(() => { const id = Object.keys(DATA.je).find(k => !DATA.je[k].proposal), lines = DATA.je[id].lines.map(l => ({account: l.account, department: l.department, debit: l.debit, credit: l.credit}));
        const rec = {kind: 'serif-decision-record', console_kind: 'flux', dec: {}, notes: {}, je: {[id]: lines}, ck: {}, sign: {}, log: {}}; planRecord(rec); const was = S.je[id]; S.je[id] = lines;
        const ok_ = jeOf(id).lines.every(l => l.memo === DATA.je[id].memo); if (was) S.je[id] = was; else delete S.je[id]; return ok_; }), 'pl: a record in main\'s format loads; Line Memo defaults to the entry memo');
      ok(await p.evaluate(pid => jeReady(pid), pid), 'pl: a balanced, noted proposal is ready');
      const [d2] = await Promise.all([p.waitForEvent('download', {timeout: 4000}).catch(() => null), p.evaluate(() => exportCSV())]);
      const rowsCsv = d2 ? fs.readFileSync(await d2.path(), 'utf8').split('\n') : [];
      ok(/^\ufeff?External ID,Subsidiary,Journal Date,Posting Period,Currency,Exchange Rate,Memo,Reversing Entry,Reversal Date,Account,Department,Debit,Credit,Line Memo$/.test(rowsCsv[0] || ''), 'pl: the CSV carries the NetSuite header and line fields');
      ok(rowsCsv.some(r => /"?Serif Biomedicines, Inc\.?"?,2026-08-31,Aug 2026,USD,1,.*,Y,2026-09-01,.*Reclass test line/.test(r)), 'pl: the proposed entry exports with subsidiary, posting period, reversal and line memo');
      ok(await p.locator('#p-ava [data-pane="mom"] th', {hasText: '3-mo avg'}).count() === 1, 'pl: MoM carries trailing averages');
      ok(await p.locator('#p-dept .ch', {hasText: 'Credits in Expense Accounts'}).count() === 1 && await p.locator('[data-note^="cr:"]').count() > 0, 'pl: credits in expense accounts listed');
      ok(await p.locator('[data-note="bonus:total"]').count() === 1, 'pl: bonus accrual check, in total');
      ok(await p.locator('#p-adj h3', {hasText: 'Billed Twice After a Gap'}).count() === 1, 'pl: billed twice after a gap');
      ok(await p.locator('#p-sox .ch', {hasText: 'Related Party: Flagship'}).count() === 1, 'pl: Flagship related-party schedule');
    }
    // the run log
    await p.evaluate(() => show('runlog'));
    ok(await p.locator('#p-runlog h3', {hasText: 'What each check found'}).count() === 1, k + ': run log shows each check');
    ok(await p.locator('#p-runlog td', {hasText: '2.0.0'}).count() >= 1, k + ': build record names 2.0.0');
    // the decision record: save, then load into a clean browser
    await p.evaluate(() => show('settings'));
    const [rd] = await Promise.all([p.waitForEvent('download', {timeout: 4000}).catch(() => null), p.click('[data-recsave]')]);
    const recPath = path.join(os.tmpdir(), 'serif-rec-' + k + '.json');
    if (rd) fs.copyFileSync(await rd.path(), recPath);
    const rec = rd ? JSON.parse(fs.readFileSync(recPath, 'utf8')) : {};
    ok(rec.kind === 'serif-decision-record' && rec.dec && rec.dec[id], k + ': record saved with the decision');
    await ctx.close();
    const c2 = await b.newContext(); const q = await c2.newPage();
    q.on('pageerror', e => errs.push(k + ' load: ' + e.message));
    await q.goto('file://' + FILES[k]); await q.waitForTimeout(400);
    await q.evaluate(() => show('settings'));
    await q.setInputFiles('#recfile', recPath); await q.waitForTimeout(300);
    ok(await q.locator('#ask').isVisible(), k + ': loading asks first, on the page');
    await q.click('[data-askok]'); await q.waitForTimeout(200);
    ok(await q.evaluate(id => (S.dec[id] || {}).v === 'modify' && (S.je[id] || [])[0].department === 'Finance', id), k + ': record loads the decision and the edit');
    await c2.close();
  }

  // ---- shared ----
  for (const k of ['gl', 'pl']){
    console.log('shared ' + k);
    const store = new Map(); const pages = [];
    const levels = {u_A: {write: true, admin: true}, u_B: {write: true}, u_C: {write: false}};
    const notify = p_ => pages.forEach(pg => pg.evaluate(pth => window.__dbChanged && window.__dbChanged(pth), p_).catch(() => {}));
    const hub = async (op, p_, body, uid) => {
      if (op === 'get') return store.has(p_) ? store.get(p_) : null;
      if (op === 'list') return Array.from(store.entries()).filter(([pp]) => pp.split('/').slice(0, -1).join('/') === p_).map(([pp, bb]) => ({path: pp, body: bb}));
      if (!(levels[uid] || {}).write || (p_.startsWith('signoff/') && !(levels[uid] || {}).admin)) return 'invalid_argument';
      if (op === 'set') store.set(p_, body);
      if (op === 'update') store.set(p_, Object.assign({}, store.get(p_), body));
      if (op === 'del') store.delete(p_);
      setTimeout(() => notify(p_), 10); return null;
    };
    const open = async (uid, name, canWrite, file) => {
      const ctx = await b.newContext({viewport: {width: 1440, height: 900}}); const p = await ctx.newPage();
      p.on('pageerror', e => errs.push(k + ' ' + uid + ': ' + e.message));
      await p.exposeFunction('__hub', hub);
      await p.addInitScript(MOCK, {uid, name, canWrite, canEdit: canWrite, withDb: true});
      await p.goto('file://' + (file || FILES[k])); pages.push(p); return p;
    };
    const A = await open('u_A', 'Alice Reviewer', true), Bp = await open('u_B', 'Bob Checker', true);
    await sleep(1200);
    ok(await A.evaluate(() => Shared.on()) && await Bp.evaluate(() => Shared.on()), 'both in shared mode');
    ok(/^Shared review/.test(await A.textContent('#sharedbar')), 'banner shown');
    const ids = await A.evaluate(() => $$('[data-item]').slice(0, 3).map(x => x.dataset.item));
    await A.evaluate(id => decide(id, 'approve', 'a'), ids[0]);
    await Bp.evaluate(id => decide(id, 'reject', 'b'), ids[1]);
    await sleep(1500);
    ok(await Bp.evaluate(id => (S.dec[id] || {}).v === 'approve', ids[0]), 'B sees A\'s decision');
    ok(await A.evaluate(id => (S.dec[id] || {}).v === 'reject', ids[1]), 'A sees B\'s decision');
    const stp = await A.evaluate(id => document.querySelector('[data-item="' + id + '"] .stp').textContent, ids[1]);
    ok(/Bob Checker/.test(stp), 'decision named by who made it: ' + stp);
    ok(!JSON.stringify(Array.from(store.values())).includes('Alice Reviewer'), 'no name written to the shared review');
    // conflict: both change the same item at once; one stands and the other is told
    await Promise.all([A.evaluate(id => decide(id, 'approve', 'c'), ids[2]), Bp.evaluate(id => decide(id, 'reject', 'c'), ids[2])]);
    await sleep(1800);
    const va = await A.evaluate(id => (S.dec[id] || {}).v, ids[2]), vb = await Bp.evaluate(id => (S.dec[id] || {}).v, ids[2]);
    ok(va === vb && !!va, 'conflict settles on one decision for both (' + va + ')');
    // sign-off: Editors only, per the publish rules
    const role = await A.evaluate(() => document.querySelector('[data-sname]').dataset.sname);
    await Bp.evaluate(r => { document.querySelector('[data-sname="' + r + '"]').value = 'Bob, Controller'; document.querySelector('[data-signbtn="' + r + '"]').click(); }, role);
    await sleep(1200);
    ok(await Bp.evaluate(r => !S.sign[r], role) && /Only Editors/.test(await Bp.textContent('#toast')), 'a Contributor cannot sign off');
    await A.evaluate(r => { document.querySelector('[data-sname="' + r + '"]').value = 'Alice, CFO'; document.querySelector('[data-signbtn="' + r + '"]').click(); }, role);
    await sleep(1200);
    ok(await Bp.evaluate(r => !!S.sign[r] && S.sign[r].by_uid === 'u_A', role), 'an Editor\'s sign-off reaches everyone');
    // read-only
    const C = await open('u_C', 'Cara Viewer', false); await sleep(1200);
    ok(/view it, not change it/.test(await C.textContent('#sharedbar')), 'viewer told the review is read-only');
    await C.evaluate(id => decide(id, 'reject', 'x'), ids[0]); await sleep(600);
    ok(await A.evaluate(id => S.dec[id].v === 'approve', ids[0]), 'a viewer cannot change a decision');
    // downloads go through the capability
    await A.evaluate(() => { show('settings'); saveRecord(); }); await sleep(300);
    ok((await A.evaluate(() => window.__saved.length)) === 1, 'decision record offered through downloads');
    // a rerun of the close brings in the earlier run's decisions
    const html = fs.readFileSync(FILES[k], 'utf8').replace(/"run": "([^"]+)"/, '"run": "rerun0000000002"');
    const rerun = path.join(os.tmpdir(), 'serif-rerun-' + k + '.html'); fs.writeFileSync(rerun, html);
    const R = await open('u_A', 'Alice Reviewer', true, rerun); await sleep(1400);
    ok(await R.evaluate(() => !document.querySelector('[data-carry]').hidden), 'rerun offers the earlier run\'s decisions');
    ok(await R.evaluate(id => !S.dec[id], ids[0]), 'rerun starts fresh');
    await R.evaluate(() => { show('settings'); carryRun(); }); await sleep(800);
    await R.click('[data-askok]'); await sleep(300);
    ok(await R.evaluate(id => (S.dec[id] || {}).v === 'approve', ids[0]), 'earlier decisions brought in');
    for (const p of pages) await p.context().close();
  }
  ok(errs.length === 0, 'no page errors' + (errs.length ? ': ' + errs.slice(0, 3).join(' | ') : ''));
  await b.close();
  console.log(fails ? fails + ' failed' : 'all passed');
  process.exit(fails ? 1 : 0);
})();
