const {chromium}=require('C:/Users/asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');const out=path.join(__dirname,'evidence');
(async()=>{const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--enable-unsafe-swiftshader']});
 const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1}); const page=await context.newPage();const logs=[];page.on('console',m=>logs.push({type:m.type(),text:m.text()}));page.on('pageerror',e=>logs.push({type:'error',text:e.message}));
 await page.addInitScript(()=>{window.__roots=[];const orig=Element.prototype.attachShadow;Element.prototype.attachShadow=function(args){let r=orig.call(this,args);window.__roots.push(r);return r};});
 await page.route('https://www.igloo.inc/__inspection_spector.js',r=>r.fulfill({status:200,contentType:'application/javascript',body:fs.readFileSync(path.join(__dirname,'tooling','spector.bundle.js'))}));
 await page.route('https://www.igloo.inc/',async r=>{const res=await r.fetch();let html=await res.text();html=html.replace('<script type="module"','<script src="/__inspection_spector.js"></script><script>window.__spector=new SPECTOR.Spector();window.__spector.spyCanvases();</script><script type="module"');await r.fulfill({response:res,body:html});});
 const client=await context.newCDPSession(page);await page.goto('https://www.igloo.inc/',{waitUntil:'domcontentloaded'});await page.waitForTimeout(14000);
 async function shot(label){await page.screenshot({path:path.join(out,'deep-'+label+'.png')});console.log('SHOT',label,page.url());}
 async function capture(label){const data=await page.evaluate(async()=>{const canvas=window.__roots.flatMap(r=>[...r.querySelectorAll('canvas')]).find(c=>c.width>300);return await new Promise((resolve,reject)=>{const id=setTimeout(()=>reject(new Error('capture timeout')),35000);__spector.onCapture.add(c=>{clearTimeout(id);resolve(c)});__spector.onError.add(e=>{clearTimeout(id);reject(new Error(JSON.stringify(e)))});__spector.captureCanvas(canvas,0,false,false)});});fs.writeFileSync(path.join(out,`spector-${label}.json`),JSON.stringify(data));console.log('CAPTURE',label,Object.keys(data),data.commands?.length);}
 await shot('hero');await capture('hero');
 const frames=await page.evaluate(()=>new Promise(resolve=>{let a=[],last;function f(t){if(last)a.push(t-last);last=t;if(a.length>=180)resolve(a);else requestAnimationFrame(f)}requestAnimationFrame(f)}));fs.writeFileSync(path.join(out,'desktop-idle-frame-intervals.json'),JSON.stringify({note:'RAF scheduler intervals after Spector instrumentation; not GPU timings or a production benchmark',intervals:frames},null,2));
 async function advance(count){await page.mouse.move(720,450);for(let i=0;i<count;i++){await page.mouse.wheel(0,400);await page.waitForTimeout(650);}}
 await advance(6);await page.waitForTimeout(3800);await shot('cube1');await capture('cube1');
 await page.mouse.move(550,350);for(let i=0;i<25;i++){await page.mouse.move(550+i*12,350+i*6);await page.waitForTimeout(18)}await page.waitForTimeout(150);await shot('cube1-frost');await capture('cube1-frost');
 await page.mouse.click(720,450);await page.waitForTimeout(350);await shot('detail-transition-350');await page.waitForTimeout(2500);await shot('detail-ready');
 if(page.url().includes('/portfolio/')){await capture('detail');await page.mouse.wheel(0,600);await page.waitForTimeout(900);await shot('detail-scrolled');await page.mouse.click(1350,75);await page.waitForTimeout(2300);await shot('detail-close');}
 await advance(18);await page.waitForTimeout(1800);await shot('entry-early');await advance(4);await page.waitForTimeout(6000);await shot('footer');await capture('footer');
 await page.mouse.move(1180,630);await page.waitForTimeout(700);await shot('footer-hover');
 await advance(10);await page.waitForTimeout(2500);await shot('loop-after-footer');
 await page.setViewportSize({width:1920,height:1080});await page.waitForTimeout(1000);await shot('desktop-wide');
 await page.setViewportSize({width:1024,height:768});await page.waitForTimeout(1000);await shot('desktop-narrow');
 fs.writeFileSync(path.join(out,'deep-console.json'),JSON.stringify(logs,null,2));await context.close();await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
