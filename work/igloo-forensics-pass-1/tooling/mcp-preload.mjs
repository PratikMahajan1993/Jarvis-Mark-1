// Inspection adapter only. The downloaded official MCP server is unmodified.
import fs from 'node:fs';
import {chromium} from './spector-server/Spector.js-master/mcp/node_modules/playwright/index.mjs';
import {BrowserManager} from './spector-server/Spector.js-master/mcp/dist/browser-manager.js';
const launch=chromium.launch.bind(chromium);
chromium.launch=opts=>launch({...opts,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
const ensure=BrowserManager.prototype.ensureBrowser;
BrowserManager.prototype.ensureBrowser=async function(){
 const page=await ensure.call(this);if(page.__iglooAdapted)return page;page.__iglooAdapted=true;
 await page.setViewportSize({width:1440,height:900});
 await page.addInitScript(()=>{window.__inspectionRoots=[];const attach=Element.prototype.attachShadow;Element.prototype.attachShadow=function(opts){const root=attach.call(this,opts);window.__inspectionRoots.push(root);return root};const query=document.querySelectorAll.bind(document);document.querySelectorAll=function(sel){if(sel!=='canvas')return query(sel);return [...query(sel),...window.__inspectionRoots.flatMap(r=>[...r.querySelectorAll('canvas')])];};});
 await page.route('https://www.igloo.inc/__inspection_spector.js',r=>r.fulfill({status:200,contentType:'application/javascript',body:fs.readFileSync(new URL('./spector-server/Spector.js-master/dist/spector.bundle.js',import.meta.url))}));
 await page.route('https://www.igloo.inc/',async r=>{const response=await r.fetch();let html=await response.text();html=html.replace('<script type="module"','<script src="/__inspection_spector.js"></script><script>window.__spectorInstance=new SPECTOR.Spector();window.__spectorInstance.spyCanvases();window.__lastCapture=null;window.__spectorInjected=true;</script><script type="module"');await r.fulfill({response,body:html});});
 const wait=page.waitForSelector.bind(page);page.waitForSelector=(selector,opts)=>selector==='canvas'?page.waitForFunction(()=>document.querySelectorAll('canvas').length>0,{},{timeout:opts?.timeout||20000}):wait(selector,opts);
 const dollar=page.$.bind(page);page.$=async selector=>selector==='canvas'?(await page.evaluateHandle(()=>document.querySelectorAll('canvas')[0])).asElement():dollar(selector);
 return page;
};
