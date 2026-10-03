process.env.PLAYWRIGHT_BROWSERS_PATH=__dirname+'/tooling/browser-cache';
const {chromium}=require('C:/Users/asus/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');const out=path.join(__dirname,'evidence');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--enable-unsafe-swiftshader']});
 for(const mode of ['desktop','mobile']){
 const mobile=mode==='mobile';const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1440,height:900},deviceScaleFactor:mobile?3:1,isMobile:mobile,hasTouch:mobile,recordVideo:{dir:path.join(out,'videos'),size:mobile?{width:390,height:844}:{width:960,height:600}}});
 const page=await context.newPage();const log={mode,viewport:context._options?.viewport,steps:[],console:[],responses:[]};page.on('console',m=>log.console.push({type:m.type(),text:m.text()}));page.on('response',r=>log.responses.push({url:r.url(),status:r.status()}));
 await page.addInitScript(()=>{window.__forensics={roots:[],gl:[],loading:[],frameTimes:[],frames:0};let orig=Element.prototype.attachShadow;Element.prototype.attachShadow=function(args){const r=orig.call(this,args);window.__forensics.roots.push({root:r,mode:args.mode,host:this});return r};let get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){let r=get.call(this,type,...args);if(r&&/webgl/.test(type)&&!window.__forensics.gl.some(x=>x.ctx===r))window.__forensics.gl.push({ctx:r,type,canvas:this});return r};new MutationObserver(()=>window.__forensics.loading.push({t:performance.now(),loader:!!document.querySelector('#loader')})).observe(document,{childList:true,subtree:true});function tick(t){let f=window.__forensics;if(f.last)f.frameTimes.push(t-f.last);f.last=t;f.frames++;requestAnimationFrame(tick)}requestAnimationFrame(tick);});
 const client=await context.newCDPSession(page);await client.send('Accessibility.enable');await page.goto('https://www.igloo.inc/',{waitUntil:'domcontentloaded'});
 const start=Date.now();
 for(const at of [300,900,1800,3000,5000,9000]){await page.waitForTimeout(Math.max(1,start+at-Date.now()));await page.screenshot({path:path.join(out,`${mode}-intro-${at}.png`)});}
 async function snapshot(label){let state=await page.evaluate(()=>({time:performance.now(),scrollY,docHeight:document.documentElement.scrollHeight,viewport:{w:innerWidth,h:innerHeight,dpr:devicePixelRatio,mobileMatch:matchMedia('(max-width: 600px)').matches,reducedMotion:matchMedia('(prefers-reduced-motion: reduce)').matches},roots:window.__forensics.roots.map(x=>({mode:x.mode,host:x.host.outerHTML,html:x.root.innerHTML})),canvases:window.__forensics.gl.map(x=>({type:x.type,w:x.canvas.width,h:x.canvas.height,css:x.canvas.style.cssText,attrs:x.ctx.getContextAttributes()})),loading:window.__forensics.loading,frameTimes:window.__forensics.frameTimes.slice(-180),resources:performance.getEntriesByType('resource').map(x=>x.toJSON()),cursor:getComputedStyle(document.body).cursor}));log.steps.push({label,...state});await page.screenshot({path:path.join(out,`${mode}-${label}.png`)});fs.writeFileSync(path.join(out,`${mode}-behavior.json`),JSON.stringify(log,null,2));console.log(mode,label,JSON.stringify({viewport:state.viewport,canvases:state.canvases,cursor:state.cursor}));}
 await page.waitForTimeout(4000);await snapshot('ready');fs.writeFileSync(path.join(out,`${mode}-accessibility.json`),JSON.stringify(await client.send('Accessibility.getFullAXTree'),null,2));
 if(!mobile){
 await page.mouse.move(720,450);await snapshot('pointer-center');await page.mouse.move(1050,360,{steps:30});await page.waitForTimeout(500);await snapshot('pointer-right');
 await page.mouse.click(105,842);await page.waitForTimeout(800);await snapshot('sound-toggle');await page.mouse.click(105,842);
 await page.keyboard.press('ArrowDown');await page.waitForTimeout(1800);await snapshot('arrow-down');
 for(let i=0;i<16;i++){await page.mouse.wheel(0,500);await page.waitForTimeout(1800);await snapshot(`wheel-${i+1}`);}
 }else{
 async function swipe(){await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:195,y:690}]});for(let i=1;i<=12;i++){await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:195,y:690-i*40}]});await page.waitForTimeout(20)}await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});}
 for(let i=0;i<6;i++){await swipe();await page.waitForTimeout(1800);await snapshot(`swipe-${i+1}`);}await page.setViewportSize({width:844,height:390});await page.waitForTimeout(1800);await snapshot('landscape');
 }
 await context.close();log.video=await page.video().path();fs.writeFileSync(path.join(out,`${mode}-behavior.json`),JSON.stringify(log,null,2));
 }await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1;process.exit(1)});
