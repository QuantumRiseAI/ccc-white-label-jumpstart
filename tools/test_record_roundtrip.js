let chromium; try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require(process.env.PLAYWRIGHT || '/Users/anniebritton/.npm/_npx/520e866687cefe78/node_modules/playwright')); }
const fs=require('fs');
const B=require('path').resolve(__dirname,'..')+'/';
(async()=>{const b=await chromium.launch();const errs=[];
for (const f of ['pl-flux/out/aug2026/serif-pl-flux-aug2026-v1.8.8.html','gl-coding-review/out/aug2026/serif-gl-coding-review-aug2026-v1.8.8.html']){
  const c1=await b.newContext({viewport:{width:1440,height:900},acceptDownloads:true}); const p1=await c1.newPage(); p1.on('pageerror',e=>errs.push(e.message));
  await p1.goto('file://'+B+f); await p1.waitForTimeout(1000);
  const ids=await p1.evaluate(()=>{const fs=D.findings.slice(0,2).map(x=>x.finding_id); decide(fs[0],'no_entry'); decide(fs[1],'question'); return fs;});
  await p1.locator('.nav button[data-view="decisions"]').first().evaluate(b=>b.click()); await p1.waitForTimeout(400);
  await p1.locator('[data-export=record]').first().click(); await p1.waitForTimeout(300);
  const [dl]=await Promise.all([p1.waitForEvent('download'), p1.click('#ask-ok')]);
  const path=await dl.path(); const rec=JSON.parse(fs.readFileSync(path,'utf8'));
  console.log(f.split('/')[0],'record decisions',Object.keys(rec.decisions).length, Object.values(rec.decisions).map(d=>d.verdict));
  // fresh browser, load it
  const c2=await b.newContext({viewport:{width:1440,height:900}}); const p2=await c2.newPage(); p2.on('pageerror',e=>errs.push(e.message));
  await p2.goto('file://'+B+f); await p2.waitForTimeout(1000);
  console.log('  fresh decided before', await p2.evaluate(ids=>ids.map(i=>!!(decisions[i]&&decisions[i].verdict)),ids));
  await p2.locator('.nav button[data-view="decisions"]').first().evaluate(b=>b.click()); await p2.waitForTimeout(300);
  await p2.setInputFiles('#recfile', path); await p2.waitForTimeout(600); await p2.click('#ask-ok'); await p2.waitForTimeout(1800);
  console.log('  after load', await p2.evaluate(ids=>ids.map(i=>decisions[i]&&decisions[i].verdict),ids), '| toast:', await p2.textContent('#toast'));
  // wrong file
  fs.writeFileSync(require('os').tmpdir()+'/notrec.json','{"a":1}'); await p2.setInputFiles('#recfile', require('os').tmpdir()+'/notrec.json'); await p2.waitForTimeout(400);
  console.log('  bad file toast:', await p2.textContent('#toast'));
  await c1.close(); await c2.close();
}
console.log('errors',errs.length?errs:'none');await b.close()})()
