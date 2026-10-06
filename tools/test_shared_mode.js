// Shared mode tests for the consoles (Console 1.8.8 on): standalone, null db, two clients on a
// mocked Artifact db, conflicts, read-only, downloads, live redraw, a rerun, and the
// adapter-first static check. Needs Playwright with Chromium.
//   node tools/test_shared_mode.js [version]      (default 1.8.8; builds out/aug2026 first)
let chromium; try { ({ chromium } = require('playwright')); }
catch (e) { ({ chromium } = require(process.env.PLAYWRIGHT || '/Users/anniebritton/.npm/_npx/520e866687cefe78/node_modules/playwright')); }
const fs = require('fs');
const B = require('path').resolve(__dirname, '..') + '/';
const VER = process.argv[2] || '1.8.8';
const FILES = { gl: B + 'gl-coding-review/out/aug2026/serif-gl-coding-review-aug2026-v' + VER + '.html',
                pl: B + 'pl-flux/out/aug2026/serif-pl-flux-aug2026-v' + VER + '.html' };
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

  // ---- static: no localStorage key is read before the adapter ----
  console.log('static');
  for (const k of ['gl', 'pl']){
    const html = fs.readFileSync(FILES[k], 'utf8');
    const js = html.slice(html.indexOf('const D = window.__SERIF_RUN__'));
    const store = js.indexOf('const Store = ('), shared = js.indexOf('const Shared = ('), end = js.indexOf('\n})();', shared);
    const firstRead = js.indexOf('Store.getItem(', end);
    const outside = (js.slice(0, store) + js.slice(end)).match(/localStorage\./g) || [];
    ok(store > 0 && firstRead > store, k + ': Store is defined before the first saved-state read');
    ok(outside.length === 0, k + ': no localStorage access outside the adapter (' + outside.length + ')');
    ok(!/api\.anthropic\.com|window\.storage/.test(html), k + ': no api.anthropic.com or window.storage');
  }

  // ---- standalone: localStorage round trip, unchanged ----
  console.log('standalone');
  for (const k of ['gl', 'pl']){
    const ctx = await b.newContext({acceptDownloads: true}); const p = await ctx.newPage();
    p.on('pageerror', e => errs.push(k + ' standalone: ' + e.message));
    await p.goto('file://' + FILES[k]); await p.waitForTimeout(800);
    const id = await p.evaluate(() => { const id = D.findings[0].finding_id; decide(id, 'question');
      decisions[id].note = 'Asked AP'; persist(); return id; });
    await p.reload(); await p.waitForTimeout(800);
    const d = await p.evaluate(id => decisions[id], id);
    ok(d && d.verdict === 'question' && d.note === 'Asked AP', k + ': decision survives a reload from localStorage');
    ok(await p.locator('#sharedbar').isHidden(), k + ': no shared banner');
    const [dl] = await Promise.all([p.waitForEvent('download', {timeout: 4000}).catch(() => null),
      p.evaluate(() => exportLog())]);
    ok(!!dl, k + ': export downloads as before' + (dl ? ' (' + dl.suggestedFilename() + ')' : ''));
    await ctx.close();
  }

  // ---- db resolves null: falls back to localStorage ----
  console.log('null db');
  { const ctx = await b.newContext(); const p = await ctx.newPage();
    p.on('pageerror', e => errs.push('null db: ' + e.message));
    await p.exposeFunction('__hub', async () => null);
    await p.addInitScript(MOCK, {uid: 'u_A', name: 'Alice Reviewer', canWrite: true, canEdit: true, withDb: false});
    await p.goto('file://' + FILES.gl); await p.waitForTimeout(900);
    const id = await p.evaluate(() => { const id = D.findings[1].finding_id; decide(id, 'no_entry'); return id; });
    await p.reload(); await p.waitForTimeout(900);
    ok(await p.evaluate(id => (decisions[id] || {}).verdict === 'no_entry', id), 'null db: decision kept in localStorage');
    ok(await p.locator('#sharedbar').isHidden(), 'null db: no shared banner');
    ok(await p.evaluate(() => !Shared.on()), 'null db: shared mode off');
    await ctx.close(); }

  // ---- shared: two (then three) clients on one mocked db ----
  for (const k of ['gl', 'pl']){
    console.log('shared ' + k);
    const store = new Map(); const pages = []; const held = new Set(); const queued = [];
    const RULE_ADMIN = path => path.startsWith('signoff/');
    const levels = {u_A: {write: true, admin: true}, u_B: {write: true, admin: false}, u_C: {write: false, admin: false}};
    const notify = path => pages.forEach(pg => {
      if (held.has(pg)) { queued.push([pg, path]); return; }
      pg.evaluate(pth => window.__dbChanged && window.__dbChanged(pth), path).catch(() => {}); });
    const hub = async (op, path, body, uid) => {
      if (op === 'get') return store.has(path) ? store.get(path) : null;
      if (op === 'list') return Array.from(store.entries()).filter(([pp]) => pp.split('/').slice(0, -1).join('/') === path)
        .map(([pp, bb]) => ({path: pp, body: bb}));
      const lv = levels[uid] || {};
      if (!lv.write || (RULE_ADMIN(path) && !lv.admin)) return 'invalid_argument';
      if (op === 'set') store.set(path, body);
      if (op === 'update') store.set(path, Object.assign({}, store.get(path), body, {runs: Object.assign({}, (store.get(path) || {}).runs, body.runs)}));
      if (op === 'del') store.delete(path);
      setTimeout(() => notify(path), 10); return null;
    };
    const open = async (uid, name, canWrite, canEdit) => {
      const ctx = await b.newContext({viewport: {width: 1440, height: 900}}); const p = await ctx.newPage();
      p.on('pageerror', e => errs.push(k + ' ' + uid + ': ' + e.message));
      await p.exposeFunction('__hub', hub);
      await p.addInitScript(MOCK, {uid, name, canWrite, canEdit, withDb: true});
      await p.goto('file://' + FILES[k]); pages.push(p); return p;
    };
    const A = await open('u_A', 'Alice Reviewer', true, true);
    const Bp = await open('u_B', 'Bob Checker', true, false);
    await sleep(1500);
    ok(await A.evaluate(() => Shared.on()) && await Bp.evaluate(() => Shared.on()), 'both clients in shared mode');
    ok((await A.textContent('#sharedbar')).indexOf('Shared mode: decisions are visible to everyone with access to this page.') === 0, 'banner shown');
    ok(await A.locator('.twho').isHidden(), 'reviewer name field hidden in shared mode');

    // two people, two different findings
    const ids = await A.evaluate(() => D.findings.slice(0, 4).map(f => f.finding_id));
    await A.evaluate(id => { decideOne(id, 'question'); decisions[id].note = 'Asked AP about this'; persist(); }, ids[0]);
    await Bp.evaluate(id => { decideOne(id, 'no_entry'); decisions[id].note = 'Coding is right'; persist(); }, ids[2]);
    await sleep(1800);
    const seenA = await A.evaluate(id => decisions[id], ids[2]), seenB = await Bp.evaluate(id => decisions[id], ids[0]);
    ok(seenA && seenA.verdict === 'no_entry' && seenA.by === 'Bob Checker', 'A sees B\'s decision, named Bob Checker: ' + JSON.stringify(seenA && {v: seenA.verdict, by: seenA.by}));
    ok(seenB && seenB.verdict === 'question' && seenB.note === 'Asked AP about this' && seenB.by === 'Alice Reviewer', 'B sees A\'s decision and note, named Alice Reviewer');
    const dump = JSON.stringify(Array.from(store.entries()));
    ok(!/Alice|Bob|Cara/.test(dump), 'no name anywhere in the shared db');
    ok(/"by_uid":"u_A"/.test(dump) && /"by_uid":"u_B"/.test(dump), 'decisions carry user ids');
    ok(Array.from(store.keys()).every(pth => /^[A-Za-z0-9_\-.~:@+/]+$/.test(pth) && pth.split('/').every(sg => sg.length <= 200)), 'every path keeps to the grammar');
    ok(Array.from(store.keys()).some(pth => pth.indexOf('review/aug2026/runs/') === 0), 'namespaced by period and run: ' + Array.from(store.keys())[0]);

    // flux commentary (pl) or a schedule row (gl) by different people
    if (k === 'pl'){
      const code = await A.evaluate(() => TABLE.sections[0].rows[0].account_code);
      await A.evaluate(c => { fluxNotes[c] = 'Timing of the Aug invoice'; persistNotes(); }, code);
      await sleep(1200);
      ok(await Bp.evaluate(c => fluxNotes[c], code) === 'Timing of the Aug invoice', 'B sees A\'s flux commentary');
      const drafts = await A.evaluate(() => Object.keys(DR.commentary || {}).length);
      ok(!Array.from(store.keys()).some(pth => /\/notes\//.test(pth) && store.get(pth).v === undefined), 'notes docs well formed (' + drafts + ' drafts embedded)');
    } else {
      const key = await A.evaluate(() => { const t = VTABLES[0], r = t.sections[0].rows[0]; return rowKeyOf(t, r); });
      await Bp.evaluate(kk => { rowDec[kk] = {outcome: 'question', note: 'Asked the budget owner', at: new Date().toISOString(), by: byWho()}; persistRows(); }, key);
      await sleep(1200);
      const r = await A.evaluate(kk => rowDec[kk], key);
      ok(r && r.outcome === 'question' && r.by === 'Bob Checker', 'A sees B\'s schedule row decision (key ' + key + ')');
    }

    // live redraw keeps scroll and the field being typed in
    await A.evaluate(() => show('decisions'));
    await A.evaluate(() => { const v = $('#v-decisions'); v.scrollTop = 300; });
    await A.evaluate(() => { const t = document.createElement('textarea'); t.id = 'typingtest'; t.value = 'half typed';
      $('#v-decisions').appendChild(t); t.focus({preventScroll: true}); });
    const before = await A.evaluate(() => $('#v-decisions').scrollTop);
    await Bp.evaluate(id => { decideOne(id, 'question'); decisions[id].note = 'Second question'; persist(); }, ids[3]);
    await sleep(1500);
    ok(await A.evaluate(() => document.activeElement && document.activeElement.id === 'typingtest' && document.activeElement.value === 'half typed'), 'a field being typed in is not redrawn');
    ok(await A.evaluate(id => (decisions[id] || {}).verdict === 'question', ids[3]), 'the change still arrived in the data');
    ok(Math.abs((await A.evaluate(() => $('#v-decisions').scrollTop)) - before) < 2, 'scroll position kept (' + before + ')');
    await A.evaluate(() => { document.activeElement.blur(); $('#typingtest').remove(); });

    // conflict: B edits the same finding without having seen A's change
    held.add(Bp);
    await A.evaluate(id => { decisions[id].note = 'A changed this'; persist(); }, ids[0]);
    await sleep(900);
    await Bp.evaluate(id => { decisions[id].note = 'B changed this too'; persist(); }, ids[0]);
    await sleep(1200);
    held.delete(Bp); queued.splice(0).forEach(([pg, pth]) => pg.evaluate(x => window.__dbChanged(x), pth).catch(() => {}));
    await sleep(600);
    const toastB = await Bp.textContent('#toast');
    ok(/changed this a moment ago/.test(toastB), 'B is told the write lost: "' + toastB + '"');
    ok(await Bp.evaluate(id => decisions[id].note, ids[0]) === 'A changed this', 'B now shows A\'s version');
    const stored = Array.from(store.entries()).find(([pth, bb]) => bb.k === ids[0]);
    ok(stored && stored[1].v.note === 'A changed this', 'the shared record kept A\'s version');

    // sign-off: Editors only
    await A.evaluate(() => show('decisions')); await Bp.evaluate(() => show('decisions'));
    await sleep(300);
    ok(/Editors of this page sign off/.test(await Bp.evaluate(() => ($('#signoff') || {}).textContent || '')), 'a Contributor sees that Editors sign off');
    await A.evaluate(() => { signoff.prepared = {name: byWho(), at: new Date().toISOString(), by: byWho()}; persistSign(); renderSign(); });
    await sleep(1300);
    const sg = await Bp.evaluate(() => signoff.prepared);
    ok(sg && sg.name === 'Alice Reviewer', 'B sees A\'s sign-off, named at render time');
    ok(store.has('signoff/aug2026-' + (await A.evaluate(() => String(M.run_id).replace(/[^A-Za-z0-9]/g, '').slice(0, 16)))), 'sign-off kept under the Editors-only path');
    await Bp.evaluate(() => { signoff.reviewed = {name: 'x', at: '', by: byWho()}; persistSign(); });
    await sleep(900);
    ok(!JSON.stringify(Array.from(store.values())).includes('"reviewed"'), 'a Contributor\'s sign-off is never written');
    await Bp.evaluate(() => { delete signoff.reviewed; renderSign(); });

    // read-only viewer
    const C = await open('u_C', 'Cara Viewer', false, false);
    await sleep(1500);
    ok(/not change it/.test(await C.textContent('#sharedbar')), 'Viewer sees the read-only banner');
    ok(await C.evaluate(id => (decisions[id] || {}).verdict, ids[2]) === 'no_entry', 'Viewer reads the shared decisions');
    const n0 = store.size;
    const free = await C.evaluate(() => D.findings.map(f => f.finding_id).find(i => !decisions[i] &&
      !(V.entries||[]).some(x => (x.finding_ids||[]).indexOf(i) > -1)));
    await C.evaluate(id => { decideOne(id, 'manual'); }, free);
    await sleep(1200);
    const cd = await C.evaluate(id => decisions[id], free);
    ok(store.size === n0 && !cd, 'Viewer\'s decision is reverted and never written' + (cd ? ' ' + JSON.stringify(cd) + ' size ' + store.size + '/' + n0 : ''));

    // downloads through the capability
    await A.evaluate(() => exportLog()); await sleep(400);
    const saved = await A.evaluate(() => window.__saved);
    ok(saved.length === 1 && /\.csv$/.test(saved[0].filename), 'export saved through downloads: ' + JSON.stringify(saved));
    await A.evaluate(() => exportQuestions()); await sleep(300);
    ok((await A.evaluate(() => window.__saved.length)) === 2, 'Questions export saved through downloads');

    // the decision record holds the shared state, other reviewers' decisions included
    await A.evaluate(() => exportRecord()); await sleep(300); await A.click('#ask-ok'); await sleep(500);
    const rec = JSON.parse(await A.evaluate(() => window.__lastData));
    ok(rec.decisions[ids[2]] && rec.decisions[ids[2]].verdict === 'no_entry' && rec.decisions[ids[2]].by === 'Bob Checker' && rec.signoff.prepared,
       'saved record holds B\'s decision and the sign-off');

    // a rerun of the same close: the earlier run's decisions come in
    const html = fs.readFileSync(FILES[k], 'utf8').replace(/"run_id": ?"([0-9a-f]{6})/, (m, h) => m.replace(h, 'ffffff'));
    const tmp = FILES[k].replace('.html', '.rerun-test.html'); fs.writeFileSync(tmp, html);
    const R = await (async () => { const ctx = await b.newContext({viewport: {width: 1440, height: 900}}); const p = await ctx.newPage();
      p.on('pageerror', e => errs.push(k + ' rerun: ' + e.message));
      await p.exposeFunction('__hub', hub);
      await p.addInitScript(MOCK, {uid: 'u_A', name: 'Alice Reviewer', canWrite: true, canEdit: true, withDb: true});
      await p.goto('file://' + tmp); pages.push(p); return p; })();
    await sleep(1600);
    ok(await R.evaluate(() => Object.keys(decisions).filter(i => decisions[i].verdict).length) === 0, 'a rerun starts with fresh state');
    ok(await R.locator('#carryrun').isVisible().catch(() => false) || await R.evaluate(() => !$('#carryrun').hidden), 'the rerun offers the earlier run\'s decisions');
    await R.evaluate(() => carryRun()); await sleep(800);
    await R.click('#ask-ok'); await sleep(1500);
    const carried = await R.evaluate(() => Object.keys(decisions).filter(i => decisions[i].verdict).length);
    ok(carried >= 3, 'earlier run\'s decisions brought in: ' + carried);
    await R.evaluate(() => Shared.flush());
    ok(Array.from(store.keys()).filter(pth => /\/runs\/ffffff/.test(pth) && /\/decisions\//.test(pth)).length >= 3, 'what was brought in is written to the shared review');
    fs.unlinkSync(tmp);
    for (const pg of pages) await pg.context().close();
  }

  console.log('errors', errs.length ? errs : 'none');
  console.log(fails ? fails + ' FAILED' : 'ALL PASSED'); process.exitCode = fails ? 1 : 0;
  await b.close();
})();
