let chromium; try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require(process.env.PLAYWRIGHT || '/Users/anniebritton/.npm/_npx/520e866687cefe78/node_modules/playwright')); }
const SECTION = {'CapEx Flags':'Review','Prepaid Flags':'Review','Dept & Entity':'Review','Reviewed & Cleared':'Transparency','New This Period':'Transparency',
  'Audit Log':'Documentation','SOX Documentation':'Documentation','Export':'Documentation','Actual vs. Actual (MoM)':'Analysis','Actual vs. Budget':'Analysis',
  'By Department (MoM)':'Analysis','Payroll Analytics':'Analysis','Balance Sheet Flux':'Close Workflow','Adjustments':'Close Workflow','SOX & GAAP':'Close Workflow'};
async function go(p, label){ const sec = SECTION[label];
  if (sec){ const open = await p.locator('.tnav .tsub:not([hidden]) button[data-label="'+label+'"]').count();
    if (!open){ await p.click('.tnav .tgt:has-text("'+sec+'")'); await p.waitForTimeout(400); } }
  await go(p, ''+label+''); }
let fails=0; const ok=(c,m)=>{console.log((c?'  PASS ':'  FAIL ')+m); if(!c) fails++;};
(async()=>{const b=await chromium.launch();const errs=[];
const B='/Users/anniebritton/Library/CloudStorage/OneDrive-QuantumRise/Clients - Active - Documents/Serif (CCC)/1-Serif-FDE-Support/7-technical-documentation/serif-data-jumpstarts/';
for (const [f,n] of [['/Users/anniebritton/Downloads/serif-gl-coding-review-aug2026-ui-update.html','ui-update'],[B+'gl-coding-review/out/aug2026/serif-gl-coding-review-aug2026-v1.8.8.html','standard']]){
 const p=await (await b.newContext({viewport:{width:1440,height:900}})).newPage(); p.setDefaultTimeout(10000); p.on('pageerror',e=>errs.push(n+': '+e.message));
 await p.goto('file://'+f); await p.waitForTimeout(1000);
 if (n==='ui-update') await go(p, 'Dept & Entity'); else await p.locator('.nav button[data-vt="vendors"]').first().evaluate(b=>b.click()); await p.waitForTimeout(300);
 ok((await p.textContent('#vtonly')).trim()==='Show unflagged lines' && await p.isVisible('#vtonly'), n+': switch reads Show unflagged lines');
 // clear the first open row with no reason, the way the outcome button does
 const res=await p.evaluate(()=>{const t=VTABLES.find(x=>x.id==='vendors'); const spec=VT[t.kind](t);
   const r=t.sections.reduce((a,s)=>a.concat(s.rows),[]).find(r=>spec.needs(r) && (LAYOUT!=='ui-update' || inVf(r,'coding'))); const k=rowKeyOf(t,r);
   rowDec[k]={outcome:'clear', note:'', at:new Date().toISOString(), by:''}; syncFindings(r, rowDec[k], k); persistRows(); persist(); renderAll();
   const shown=[...document.querySelectorAll('#vttbl tbody tr')].some(tr=>tr.textContent.indexOf(r.vendor)>-1);
   return {vendor:r.vendor, done: rowDone(k), shown};});
 ok(res.done, n+': Cleared with no reason settles the row ('+res.vendor+')');
 ok(res.shown, n+': the cleared row stays on screen with unflagged lines hidden');
 const fd=await p.evaluate(()=>{const x=D.findings.find(y=>!hasEntry(y.finding_id)); decideOne(x.finding_id,'no_entry'); return decided(x.finding_id);});
 ok(fd, n+': a finding Cleared with no reason is decided');
 if(n==='ui-update'){ await go(p, 'Reviewed & Cleared'); await p.waitForTimeout(300);
   ok(await p.$$eval('#vttbl tbody tr.xp', t=>t.length)>=20 && !(await p.isVisible('#vtonly')), 'Reviewed & Cleared lists its vendors, no switch');
   await go(p, 'CapEx Flags'); await p.waitForTimeout(300);
   ok(!(await p.isVisible('#vtonly')), 'CapEx Flags: every line flagged, so no switch'); }
}
const p=await (await b.newContext()).newPage(); p.setDefaultTimeout(10000); p.on('pageerror',e=>errs.push('pl: '+e.message));
await p.goto('file:///Users/anniebritton/Downloads/serif-pl-flux-aug2026-ui-update.html'); await p.waitForTimeout(900);
await go(p, 'Actual vs. Actual (MoM)'); await p.waitForTimeout(300);
ok((await p.textContent('#fxonly')).trim()==='Show unflagged lines' && await p.isVisible('#fxonly'), 'flux pack: unflagged hidden by default');
console.log('errors',errs.length?errs:'none'); console.log(fails?fails+' FAILED':'ALL PASSED'); await b.close()})()
