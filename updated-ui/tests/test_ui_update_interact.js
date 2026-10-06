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
 // GL
 let p=await (await b.newContext({viewport:{width:1440,height:900}})).newPage(); p.setDefaultTimeout(10000); p.on('pageerror',e=>errs.push('gl: '+e.message));
 await p.goto('file:///Users/anniebritton/Downloads/serif-gl-coding-review-aug2026-ui-update.html'); await p.waitForTimeout(1000);
 await go(p, 'CapEx Flags'); await p.waitForTimeout(300);
 const vendors=await p.$$eval('#vttbl tr.xp, #vttbl tr[data-xk]', t=>t.length);
 ok(vendors>=3, 'CapEx Flags lists its vendors ('+vendors+')');
 const key=await p.evaluate(()=>{const t=VTABLES.find(x=>x.id==='vendors'); const r=t.sections[0].rows.find(r=>VF_OF(r)==='capex'); const k=rowKeyOf(t,r);
   rowDec[k]={outcome:'clear',note:'Not a capital item',at:new Date().toISOString(),by:'Test'}; persistRows(); renderAll(); return k;});
 await p.waitForTimeout(300);
 const ct=await p.textContent('.tnav button[data-label="CapEx Flags"] .navct');
 ok(ct==='2', 'CapEx count drops to 2 after a decision ('+ct+')');
 await go(p, 'Audit Log'); await p.waitForTimeout(300);
 ok((await p.textContent('#audittbl')).indexOf('Not a capital item')>-1, 'Audit Log shows the decision');
 await go(p, 'Dept & Entity'); await p.waitForTimeout(300);
 ok(await p.locator('#vtpost .chsech').count()===0, 'Dept & Entity has no ledger checks');
 await p.reload(); await p.waitForTimeout(900);
 ok(await p.evaluate(k=>(rowDec[k]||{}).outcome==='clear',key), 'decision survives reload');
 await go(p, 'Overview'); await p.waitForTimeout(300);
 const dgo=await p.locator('#checklist tr.xp').count(); ok(dgo>=6,'close checklist lists the pages ('+dgo+')');
 // Flux
 p=await (await b.newContext({viewport:{width:1440,height:900}})).newPage(); p.setDefaultTimeout(10000); p.on('pageerror',e=>errs.push('pl: '+e.message));
 await p.goto('file:///Users/anniebritton/Downloads/serif-pl-flux-aug2026-ui-update.html'); await p.waitForTimeout(1000);
 await go(p, 'Balance Sheet Flux'); await p.waitForTimeout(300);
 const ta=p.locator('textarea[data-bsn]').first(); await ta.fill('Cash up on the JPM sweep'); await p.waitForTimeout(200);
 await p.reload(); await p.waitForTimeout(900); await go(p, 'Balance Sheet Flux'); await p.waitForTimeout(300);
 ok(await p.locator('textarea[data-bsn]').first().inputValue()==='Cash up on the JPM sweep', 'balance sheet commentary saves');
 await go(p, 'Adjustments'); await p.waitForTimeout(400);
 const secs=await p.$$eval('#v-entries .chsech', h=>h.map(x=>x.textContent));
 ok(secs.some(s=>s.indexOf('Section B')===0), 'Adjustments has Section A and B: '+JSON.stringify(secs));
 const before=await p.textContent('.tnav button[data-label="Adjustments"] .navct');
 const id=await p.evaluate(()=>chExtra().find(x=>x.title.startsWith('Section B')).ids.find(openAt)); await p.click('#adjextra [data-decide-row="'+id+'"][data-verdict="no_entry"]'); await p.waitForTimeout(300);
 await p.locator('#adjextra textarea[data-rownote="'+id+'"]').fill('Forecast to be updated'); await p.waitForTimeout(300);
 await p.evaluate(()=>renderNavCounts());
 const after=await p.textContent('.tnav button[data-label="Adjustments"] .navct');
 ok(Number(after)<Number(before), 'deciding a Section B line lowers the Adjustments count ('+before+' to '+after+')');
 await go(p, 'SOX & GAAP'); await p.waitForTimeout(300);
 const h=await p.$$eval('#v-decisions h3', x=>x.map(y=>y.textContent));
 ok(['Source Data Validation','GL Tie-Out','Policy Application Summary','AI Disclosure','Sign-off'].every(t=>h.indexOf(t)>-1), 'SOX & GAAP sections present');
 await go(p, 'Executive Overview'); await p.waitForTimeout(300);
 await p.hover('.wf-col >> nth=0'); await p.waitForTimeout(200);
 ok(/Lab Supplies/.test(await p.textContent('#tip')), 'waterfall tooltip shows');
 ok(await p.locator('#v-overview .chtile').count()===10 && await p.locator('#checklist').count()===0, 'Executive Overview: his ten tiles, nothing else of ours');
 console.log('errors',errs.length?errs:'none'); console.log(fails?fails+' FAILED':'ALL PASSED'); await b.close();
})()
