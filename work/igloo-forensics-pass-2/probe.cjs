const {chromium}=require('C:/Users/asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const out=path.join(__dirname,'evidence');fs.mkdirSync(out,{recursive:true});
const archive=fs.readFileSync(path.join(__dirname,'../igloo-forensics-pass-1/evidence/App3D-f554a111.js'),'utf8');
const result={method:'Browser-local response adapter exposes root; source identical check required. No Spector. Direct progress placements are interventions, not natural scroll.',states:[],events:[],console:[]};
(async()=>{
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
try {
const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1});const page=await context.newPage();
page.on('console',m=>{if(m.type()==='error'||m.type()==='warning')result.console.push({type:m.type(),text:m.text()})});page.on('pageerror',e=>result.console.push({type:'pageerror',text:e.message}));
await page.route('**/App3D-f554a111.js',async route=>{const response=await route.fetch();const source=await response.text();result.source={identical:source===archive,sha256:crypto.createHash('sha256').update(source).digest('hex'),patch:'const f=new jF; -> const f=new jF;window.__igloo=f;'};if(source!==archive)throw Error('Production archive differs');await route.fulfill({response,body:source.replace('const f=new jF;','const f=new jF;window.__igloo=f;')});});
await page.goto('https://www.igloo.inc/',{waitUntil:'domcontentloaded',timeout:60000});
await page.waitForFunction(()=>window.__igloo?.currentSection==='home',{},{timeout:90000});await page.waitForTimeout(4500);
async function state(label,shot=false){const s=await page.evaluate(()=>{const r=window.__igloo;const vector=v=>v?.toArray?.();const camera=c=>({position:vector(c.position),basePosition:vector(c.basePosition),target:vector(c.baseTarget),up:vector(c.up),fov:c.fov});const uni=m=>Object.fromEntries(Object.entries(m?.uniforms||{}).filter(([k,v])=>typeof v.value==='number'||typeof v.value==='boolean').map(([k,v])=>[k,v.value]));return{time:performance.now(),url:location.href,scrollY,scroll:Object.fromEntries(Object.entries(r.scroll).filter(([k,v])=>typeof v==='number')),autoCenter:Object.fromEntries(Object.entries(r.autoCenter).filter(([k,v])=>typeof v==='number'||typeof v==='boolean')),detailIndex:r.detailIndex,isDetailOpen:r.isDetailOpen,root:uni(r.material),scenes:r.scrollComposers.map(c=>{const s=c.passes[0].scene;return{name:s.constructor.name,progress:s.progress,visible:s.isSceneVisible,camera:camera(s.camera),timelineDuration:s.timeline?.duration?.(),post:uni(s.___composerPass?.material),currentLink:s.containerparticles?.currentLink,uiEnabled:s.containerparticles?.UI?.enabled,particleCompute:uni(s.containerparticles?.mesh?.computationMaterial),floorAdditionalTime:s.floor?.additionalTime}}),detailCamera:camera(r.detailScene.camera),audioMuted:r.audioController.muted};});s.label=label;result.states.push(s);if(shot)await page.screenshot({path:path.join(out,label+'.png')});fs.writeFileSync(path.join(out,'probe.json'),JSON.stringify(result,null,2));console.log(label,JSON.stringify({y:s.scroll.y,velocity:s.scroll.velocity,auto:s.autoCenter.animating,link:s.scenes[2].currentLink}));}
async function place(y,label,wait=850){await page.evaluate(y=>{const r=window.__igloo;r.stopAutoCenter();Object.assign(r.scroll,{y,targetY1:y,targetY2:y,velocity:0});r.autoCenter.needed=false;r.autoCenter.lastTarget=y;},y);result.events.push({type:'direct-placement',y,label});await page.waitForTimeout(wait);await state(label,true);}
await state('hero-settled',true);
await page.mouse.wheel(0,300);result.events.push({type:'wheel',deltaY:300});for(const dt of [100,200,500,900,1200,1800]){await page.waitForTimeout(dt);await state('hero-wheel-'+dt,false);}
await place(1.85,'hero-cubes-overlap');await place(2.35,'pudgy');await place(2.85,'between-cubes');await place(3.35,'overpass');await place(4.35,'abstract');
await page.mouse.click(720,450);result.events.push({type:'click',at:[720,450],label:'abstract-open'});for(const dt of [150,300,500,900,1200]){await page.waitForTimeout(dt);await state('abstract-open-'+dt,true);}
await page.mouse.click(1350,65);result.events.push({type:'click',at:[1350,65],label:'abstract-close'});for(const dt of [200,500,1000]){await page.waitForTimeout(dt);await state('abstract-close-'+dt,true);}
await place(4.85,'cubes-entry-overlap');
for(const p of [.20,.28,.375,.465,.55,.64,.76])await place(5.35+6.5*p-1,'entry-p'+String(p).replace('.','-'));
await page.mouse.move(720,835);await page.waitForTimeout(750);await state('finale-visit-hover',true);
await page.keyboard.press('ArrowRight');result.events.push({type:'key',key:'ArrowRight'});await page.waitForTimeout(180);await state('finale-right-180',true);await page.waitForTimeout(1900);await state('finale-right-settled',true);
await page.keyboard.press('ArrowRight');await page.waitForTimeout(2200);await state('finale-medium',true);
await place(6.95,'entry-idle-start',150);await page.mouse.wheel(0,80);result.events.push({type:'wheel',deltaY:80,label:'entry-idle-arm'});for(const dt of [1600,1400,1700,2000]){await page.waitForTimeout(dt);await state('entry-idle-'+dt,true);}
await context.close();
}finally{fs.writeFileSync(path.join(out,'probe.json'),JSON.stringify(result,null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});

