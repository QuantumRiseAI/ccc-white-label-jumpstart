// Tests for the 2.0.0 consoles: standalone state, the decision record, the run log,
// editable entries and the NetSuite CSV, an item edited in NetSuite (out of the CSV, in the
// record and the work paper), then shared mode on a mocked Artifact db:
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
    let ns = null;
    if (k === 'gl'){
      // Edited in NetSuite: the fix was made on the bill itself. Decided, out of the CSV, in the record and the work paper
      ns = await p.evaluate(() => { const n = $$('#p-dept [data-flag]').map(x => x.dataset.item).find(i => DATA.je[i] && DATA.docs[i] && $('[data-item="' + i + '"] [data-v="netsuite"]'));
        if (!refOf(n)) DATA.ref = Object.assign({}, DATA.ref, {[n]: 'TEST-01'});
        return {id: n, doc: DATA.docs[n], ref: refOf(n), ext: DATA.je[n].id}; });
      ok(!!ns.id && !!ns.doc, 'gl: a Dept & Entity flag offers Edited in NetSuite and knows its document (' + ns.doc + ')');
      ok(await p.evaluate(() => !$$('[data-item^="DR-"] [data-v="netsuite"]').length && $$('#p-clear [data-v="netsuite"]').length > 0 && $$('#p-prepaid [data-v="netsuite"]').length > 0),
         'gl: Edited in NetSuite is offered beside each fix to a transaction, not on an entry Claude drafted');
      await p.evaluate(() => show('dept'));
      await p.click('[data-item="' + ns.id + '"] [data-v="netsuite"]');
      ok(await p.evaluate(n => S.dec[n].v === 'netsuite' && decided(n) && !jeLive(n) && /Edited in NetSuite/.test($('[data-item="' + n + '"] .stp').textContent)
         && !$('[data-note="' + n + '"]').hidden, ns.id), 'gl: Edited in NetSuite counts as decided, no note required, the note offered');
      await p.fill('[data-jef="' + ns.id + '|0|department"]', 'Finance');
      ok(await p.evaluate(n => S.dec[n].v === 'netsuite', ns.id), 'gl: editing its entry records what changed and keeps it Edited in NetSuite');
      const [d3] = await Promise.all([p.waitForEvent('download', {timeout: 4000}).catch(() => null), p.evaluate(() => exportCSV())]);
      const csv3 = d3 ? fs.readFileSync(await d3.path(), 'utf8') : '';
      ok(!!csv3 && csv3.includes(await p.evaluate(id => DATA.je[id].id, id)) && !csv3.includes(ns.ext), 'gl: an item edited in NetSuite is absent from the CSV; the reclass is in it');
      ok(/1 item edited in NetSuite, not in the import/.test(await p.evaluate(() => $('#tip').textContent)), 'gl: the export says what was edited in NetSuite and left out');
      await p.evaluate(() => show('export'));
      ok(/Edited in NetSuite: 1/.test(await p.textContent('[data-fixsum]')) && (await p.textContent('[data-nsrows]')).includes(ns.doc) && (await p.textContent('[data-nsrows]')).includes(ns.ref),
         'gl: Export counts the paths and lists the item edited in NetSuite with its document and reference ID');
      const [wp] = await Promise.all([p.waitForEvent('download', {timeout: 4000}).catch(() => null), p.click('[data-wpsave]')]);
      const wpText = wp ? fs.readFileSync(await wp.path(), 'utf8') : '';
      const wpRow = (wpText.split('<tr>').find(r => r.includes('>' + ns.ref + '<')) || '');
      ok(/Edited in NetSuite/.test(wpRow) && wpRow.includes(ns.doc.replace(/&/g, '&amp;')) && /Finance/.test(wpRow) && !wpText.split('Reclasses in the NetSuite import')[1].includes(ns.ext),
         'gl: the work paper carries it with its path, document, reference ID and change, and not among the reclasses');
      ok(/Reclass, in the import/.test(wpText) && wpText.split('Reclasses in the NetSuite import')[1].includes(await p.evaluate(id => DATA.je[id].id, id)), 'gl: the work paper lists the reclass in the import');
    }
    if (k === 'gl'){
      const [ref, ext] = await p.evaluate(id => [refOf(id), DATA.je[id].id], id), rows = csvText.split('\n').filter(r => r.startsWith(ext + ','));
      ok(/^PREPAID-\d{2}$/.test(ref) && rows.length > 1 && rows.every(r => r.includes(',' + ref + ' | ') || r.includes(',"' + ref + ' | ')), 'gl: the CSV Memo starts with the finding\'s reference ID (' + ref + ')');
      // SERIF-144: Project and Program on each line and on both sides of each entry; balance sheet lines Non-Specific
      ok(/^﻿?External ID,.*,Account,Department,Project,Program,Debit,Credit,Line Memo\r?$/.test(csvText.split('\n')[0]) && rows.every(r => r.includes(',00 Non-Specific,00 Non-Specific,')),
         'gl: the CSV carries each line\'s Project and Program beside its department');
      ok(await p.evaluate(() => { const ids = Object.keys(DATA.je).filter(i => /^(C|P|CB|PB|D)-/.test(i));
        return ids.length > 10 && ids.every(i => { const m = {};
          DATA.je[i].lines.forEach(l => { const d = l.project + '|' + l.program; m[d] = (m[d] || 0) + (Number(l.debit) || 0) - (Number(l.credit) || 0); });
          return DATA.je[i].lines.every(l => l.project || l.program) && Object.values(m).every(v => Math.abs(v) < 0.005); })
          && ids.some(i => DATA.je[i].lines.some(l => l.project === 'Internal CMC')); }),
         'gl: both sides of each entry from a ledger line carry that line\'s Project and Program');
      ok(await p.evaluate(() => { const c = Object.keys(DATA.je).filter(i => /^(C|P)-/.test(i));
        return c.length > 0 && c.every(i => DATA.je[i].lines.every(l => /^[123]/.test(l.account) ? l.department === 'Non-Specific' && Number(l.debit) > 0 : !!l.department && l.department !== 'Non-Specific')); }),
         'gl: on CapEx and Prepaid flags the new balance sheet line is Non-Specific; the expense line keeps its department');
      ok(await p.evaluate(() => { const b = Object.keys(DATA.je).filter(i => /^(PB|CB)-/.test(i)), seen = [];
        const ok_ = b.length > 0 && b.every(i => { const x = $('[data-item="' + i + '"]'), kv = {};
          x.querySelectorAll('.kv > div').forEach(d => { kv[d.querySelector('.l').textContent] = d.querySelector('.x').textContent; });
          const cr = DATA.je[i].lines.filter(l => Number(l.credit));
          seen.push(cr[0].department);
          return cr.length === 1 && /^1/.test(cr[0].account) && kv['Current coding'].startsWith(cr[0].account) && cr[0].department === kv['Department']
            && Math.abs(Number(cr[0].credit) - Number(x.dataset.amt)) < 0.005; });
        return ok_ && seen.some(d => d !== 'Non-Specific'); }),
         'gl: a bill booked to prepaid or fixed assets is reversed on its own account and department, netting the original');
      ok(await p.evaluate(() => { const i = Object.keys(DATA.je).find(i => i.startsWith('C-') && /^1/.test(DATA.je[i].lines[0].account)), l = DATA.je[i].lines[0];
        return !!DATA.je[i].lines[1].department && DATA.je[i].lines[1].department !== 'Non-Specific' && $('[data-item="' + i + '"] .kv').textContent.includes(DATA.acct[l.account] + ' / Non-Specific'); }),
         'gl: a CapEx card recommends the asset account with Non-Specific, not the expense\'s department');
      ok(await p.evaluate(() => /Project \/ Program/.test($('#p-capex details.lines thead').textContent) && /00 Non-Specific/.test($('#p-capex details.lines tbody').textContent)
         && $$('[data-jef$="|project"]').length === $$('[data-jef$="|department"]').length && $$('[data-jef$="|program"]').length === $$('[data-jef$="|department"]').length),
         'gl: a card\'s lines show Project and Program, and every entry line can edit them');
      const rc = await p.evaluate(() => $$('#p-clear [data-item]').pop().dataset.item);
      await p.evaluate(rc => { decide(rc, 'recode', 'x'); show('clear'); }, rc);
      ok(await p.evaluate(rc => jeWhy(rc) === 'unchanged', rc), 'gl: a recode with nothing changed is unchanged');
      await p.fill('[data-jef="' + rc + '|0|project"]', 'Internal CMC');
      ok(await p.evaluate(rc => jeWhy(rc) === 'missing note' && jeOf(rc).lines[0].project === 'Internal CMC' && jeOf(rc).lines[1].project === DATA.je[rc].lines[1].project, rc),
         'gl: moving a line to another Project is a change, the other side keeps its Project');
      ok(await p.evaluate(rc => { const was = S.je[rc]; S.je[rc] = DATA.je[rc].lines.map(l => ({account: l.account, department: l.department, debit: l.debit, credit: l.credit}));
        const back = jeOf(rc).lines.every((l, n) => l.project === DATA.je[rc].lines[n].project && l.program === DATA.je[rc].lines[n].program);
        S.je[rc] = was; delete S.je[rc]; delete S.dec[rc]; save(); refresh(); return back; }, rc), 'gl: lines saved before Project and Program were carried take the run\'s');
    }
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
      ok(await p.evaluate(() => { const back = Object.values(DATA.je).filter(j => j.lines.some(l => / \| Original date \d{4}-\d{2}-\d{2}$/.test(l.memo || '')));
        return back.length > 0 && back.every(j => j.date === '2026-08-31' && j.period === 'Aug 2026'); }), 'gl: entries are dated in the close month and the Line Memo keeps the original date');
      // reference IDs: one per card, by screen, numbered largest first; each entry's Memo starts with its card's
      const refs = await p.evaluate(() => [...document.querySelectorAll('[data-item]')].map(x => ({id: x.dataset.item, amt: Math.abs(Number(x.dataset.amt)),
        shown: (x.querySelector(':scope > .ih > .ref') || {}).textContent || '', ref: refOf(x.dataset.item)})));
      ok(refs.length > 0 && refs.length === await p.evaluate(() => Object.keys(DATA.ref).length) && refs.every(r => r.shown && r.shown === r.ref), 'gl: every card shows its reference ID in its header (' + refs.length + ')');
      ok(refs.every(r => /^(CAPEX|FA|PREPAID|PPD|DEPT|DRAFT|CLEAR|NEW)-\d{2,}$/.test(r.ref)) && new Set(refs.map(r => r.ref)).size === refs.length, 'gl: reference IDs are PREFIX-NN and unique');
      ok(['CAPEX', 'PREPAID', 'DEPT'].every(s => refs.some(r => r.ref === s + '-01')) && refs.some(r => r.ref.startsWith('PREPAID-') && r.id.startsWith('P-')) && refs.some(r => r.ref.startsWith('DEPT-') && r.id.startsWith('D-')), 'gl: CapEx, Prepaid and Dept & Entity cards are numbered by screen');
      ok(Object.values(refs.reduce((m, r) => { const [s, n] = r.ref.split('-'); (m[s] = m[s] || [])[Number(n) - 1] = r; return m; }, {}))
        .every(xs => Array.from(xs).every((r, i) => r && (!i || xs[i - 1].amt >= r.amt))), 'gl: within a screen, numbered from 01 with no gaps, largest amount first');
      ok(await p.evaluate(() => Object.keys(DATA.je).every(id => refOf(id) && DATA.je[id].memo.startsWith(refOf(id) + ' | ') && / \| Aug'26$/.test(DATA.je[id].memo)
        && DATA.je[id].memo.length <= 999 && DATA.je[id].lines.every(l => l.memo.startsWith(refOf(id) + ' | ') && l.memo.length <= 999))), 'gl: each entry\'s Memo and Line Memo is REF | description | Aug\'26, within NetSuite\'s 999 characters');
      ok(await p.evaluate(() => { const m = $('#p-dept [data-jeh$="|memo"]'), id = m.dataset.jeh.split('|')[0];
        return /^DEPT-\d{2}$/.test(refOf(id)) && m.value === DATA.je[id].memo && m.value.startsWith(refOf(id) + ' | '); }), 'gl: the entry editor\'s Memo carries the reference ID');
      // a rebuild of the same run numbers every card the same; a drafted entry adds a DRAFT ID and moves none
      const DG = B + 'out/dist/gl-coding-review/', run = B + 'out/aug2026/gl-coding-review/run.json';
      if (fs.existsSync(DG + 'build_pages.py') && fs.existsSync(run) && fs.existsSync(B + 'inputs/aug2026')){
        const cp = require('child_process'), tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'serif-refs-'));
        const GL = fs.readdirSync(B + 'inputs/aug2026').filter(f => /^netsuite_gl_detail_.*\.xls$/.test(f)).map(f => B + 'inputs/aug2026/' + f);
        const drafts = path.join(tmp, 'drafts.json');
        fs.writeFileSync(drafts, JSON.stringify({entries: [{memo: "Test reclass | Aug'26", reason: 'Test', lines: [
          {account: '6410000', department: 'Platform', vendor: 'Test', debit: 1000}, {account: '6607000', department: 'Platform', vendor: 'Test', credit: 1000}]}]}));
        const refsOf = (name, extra) => { const out = path.join(tmp, name);
          const r = cp.spawnSync('python3', ['build_pages.py', '--only', 'coding', '--coding-run', run, '--gl', ...GL, '--out', out, ...extra], {cwd: DG, encoding: 'utf8'});
          if (r.status) return null; const h = fs.readFileSync(path.join(out, fs.readdirSync(out).find(f => /^serif-gl-coding-review-.*\.html$/.test(f))), 'utf8');
          return JSON.parse(h.match(/window\.DATA=(.*?);<\/script>/s)[1]).ref; };
        const mine = await p.evaluate(() => DATA.ref), again = refsOf('again', []), withDraft = refsOf('draft', ['--drafts', drafts]);
        ok(again && JSON.stringify(again) === JSON.stringify(mine), 'gl: a rebuild of the same data gives the same reference IDs');
        ok(withDraft && Object.keys(mine).every(i => withDraft[i] === mine[i]) && Object.keys(withDraft).filter(i => !(i in mine)).map(i => withDraft[i]).join() === 'DRAFT-01',
          'gl: a drafted entry is DRAFT-01 and moves no other reference ID');
      } else console.log('  SKIP gl: reference IDs across builds (needs out/dist, out/aug2026 and inputs/aug2026: run tools/build.sh first)');
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
      ok(await p.evaluate(pid => jeOf(pid).lines[1].department === 'Non-Specific' && $('[data-jef="' + pid + '|1|department"]').value === 'Non-Specific', pid),
         'pl: a line moved to a balance sheet account takes the Non-Specific department');
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
      ok(/^\ufeff?External ID,Subsidiary,Journal Date,Posting Period,Currency,Exchange Rate,Memo,Reversing Entry,Reversal Date,Account,Department,Project,Program,Debit,Credit,Line Memo$/.test(rowsCsv[0] || ''), 'pl: the CSV carries the NetSuite header and line fields');
      ok(await p.evaluate(() => { const x = Object.values(DATA.je).filter(j => /^Capitalize /.test(j.memo || ''));
        return x.length > 0 && x.every(j => j.lines.every(l => /^1/.test(l.account) ? l.department === 'Non-Specific' : l.department !== 'Non-Specific')
          && new Set(j.lines.map(l => l.project + '|' + l.program)).size === 1 && !!j.lines[0].project); }),
         'pl: a Capitalize entry\'s asset line is Non-Specific and both lines carry the bill\'s Project and Program');
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
    if (ns){
      const f = (rec.fixes || {})[ns.id] || {};
      ok(rec.dec[ns.id].v === 'netsuite' && f.path === 'Edited in NetSuite' && f.document === ns.doc && f.ref === ns.ref && !f.in_import && !f.external_id,
         'gl: the record carries the path, the document and the reference ID of the item edited in NetSuite');
      ok(((rec.fixes || {})[id] || {}).path === 'Reclass' && rec.fixes[id].in_import && !!rec.fixes[id].external_id, 'gl: and the reclass path, with its External ID');
    }
    await ctx.close();
    const c2 = await b.newContext(); const q = await c2.newPage();
    q.on('pageerror', e => errs.push(k + ' load: ' + e.message));
    await q.goto('file://' + FILES[k]); await q.waitForTimeout(400);
    await q.evaluate(() => show('settings'));
    await q.setInputFiles('#recfile', recPath); await q.waitForTimeout(300);
    ok(await q.locator('#ask').isVisible(), k + ': loading asks first, on the page');
    await q.click('[data-askok]'); await q.waitForTimeout(200);
    ok(await q.evaluate(id => (S.dec[id] || {}).v === 'modify' && (S.je[id] || [])[0].department === 'Finance', id), k + ': record loads the decision and the edit');
    if (ns) ok(await q.evaluate(n => (S.dec[n] || {}).v === 'netsuite' && decided(n), ns.id), 'gl: the record loads Edited in NetSuite');
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
    const nsId = k === 'gl' ? await A.evaluate(() => $('#p-dept [data-flag] [data-v="netsuite"]').closest('[data-item]').dataset.item) : null;
    if (nsId){
      await A.evaluate(id => decide(id, 'netsuite', 'n'), nsId); await sleep(1500);
      ok(await Bp.evaluate(id => (S.dec[id] || {}).v === 'netsuite' && decided(id) && /^Edited in NetSuite · Alice Reviewer/.test($('[data-item="' + id + '"] .stp').textContent), nsId),
         'B sees A\'s Edited in NetSuite, named');
    }
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
    if (nsId) ok(await R.evaluate(id => (S.dec[id] || {}).v === 'netsuite', nsId), 'an earlier Edited in NetSuite is brought in');
    for (const p of pages) await p.context().close();
  }
  ok(errs.length === 0, 'no page errors' + (errs.length ? ': ' + errs.slice(0, 3).join(' | ') : ''));
  await b.close();
  console.log(fails ? fails + ' failed' : 'all passed');
  process.exit(fails ? 1 : 0);
})();
