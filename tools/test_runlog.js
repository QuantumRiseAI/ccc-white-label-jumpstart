let chromium; try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require(process.env.PLAYWRIGHT || '/Users/anniebritton/.npm/_npx/520e866687cefe78/node_modules/playwright')); }
const B=require('path').resolve(__dirname,'..')+'/';
(async()=>{const b=await chromium.launch();const errs=[];
for (const [f,w] of [['gl-coding-review/out/aug2026/serif-gl-coding-review-aug2026-v1.8.8.html',1440],['pl-flux/out/aug2026/serif-pl-flux-aug2026-v1.8.8.html',1440],['pl-flux/out/aug2026/serif-pl-flux-aug2026-v1.8.8.html',420]]){
 const n=f.split('/')[0]+'-'+w;
 const p=await (await b.newContext({viewport:{width:w,height:900},deviceScaleFactor:2})).newPage(); p.on('pageerror',e=>errs.push(e.message));
 await p.goto('file://'+B+f); await p.waitForTimeout(1000);
 console.log(n,'| bar:', (await p.locator('.tnav').innerText()).replace(/\s+/g,' '), '| overview has exports:', await p.locator('#v-overview h3',{hasText:'Exports this month'}).count());
 await p.locator('.trun button').click(); await p.waitForTimeout(400);
 console.log('  crumb', await p.textContent('#crumb'), '| sections', await p.locator('#v-runlog h3').allInnerTexts(), '| decisions still has build record:', await p.locator('#v-decisions h3',{hasText:'Build record'}).count());
 if (w===1440){
   await p.evaluate(()=>{decide(D.findings[0].finding_id,'question');});
   await p.locator('.nav button[data-view="decisions"]').first().evaluate(b=>b.click()); await p.waitForTimeout(300);
   await p.click('#reset'); await p.waitForTimeout(300);
   console.log('  dialog open', await p.locator('#ask').evaluate(d=>d.open), '| ok disabled', await p.locator('#ask-ok').isDisabled());
   await p.fill('#ask-type','clea'); console.log('  "clea" ok disabled', await p.locator('#ask-ok').isDisabled());
   await p.locator('#ask .pill--knockout').click(); await p.waitForTimeout(300);
   console.log('  after cancel decided', await p.evaluate(()=>!!decisions[D.findings[0].finding_id]));
   await p.click('#reset'); await p.waitForTimeout(300); await p.fill('#ask-type','Clear');
   console.log('  "Clear" ok disabled', await p.locator('#ask-ok').isDisabled()); await p.click('#ask-ok'); await p.waitForTimeout(300);
   console.log('  after confirm decisions', await p.evaluate(()=>Object.keys(decisions).length));
 }
}
console.log('errors',errs.length?errs:'none');await b.close()})()
