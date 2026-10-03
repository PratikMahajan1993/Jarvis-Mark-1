import fs from 'node:fs';import path from 'node:path';import {fileURLToPath}from'node:url';
import {Client}from'./tooling/spector-server/Spector.js-master/mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import {StdioClientTransport}from'./tooling/spector-server/Spector.js-master/mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
const root=path.dirname(fileURLToPath(import.meta.url)),out=path.join(root,'evidence');
const transport=new StdioClientTransport({command:process.execPath,args:['--import',path.join(root,'tooling/mcp-preload.mjs'),path.join(root,'tooling/spector-server/Spector.js-master/mcp/dist/index.js')],stderr:'pipe'});
const client=new Client({name:'igloo-forensics-pass1',version:'1.0.0'});const stderr=[];
await client.connect(transport);if(transport.stderr)transport.stderr.on('data',b=>stderr.push(String(b)));
try{
 const inventory=await client.listTools();fs.writeFileSync(path.join(out,'spector-mcp-tools.json'),JSON.stringify(inventory,null,2));console.log('MCP tools',inventory.tools.map(t=>t.name).join(','));
 for(const [name,args] of [['load_url',{url:'https://www.igloo.inc/'}],['list_canvases',{}],['select_canvas',{index:0}],['get_context_info',{}],['capture_frame',{quickCapture:true}],['get_draw_calls',{}],['get_shaders',{}],['get_textures',{}],['get_webgl_state',{}],['get_console_logs',{}],['take_screenshot',{}]]){
  if(name==='capture_frame')await new Promise(r=>setTimeout(r,16000));
  const result=await client.callTool({name,arguments:args},undefined,{timeout:120000});
  const texts=result.content.filter(x=>x.type==='text').map(x=>x.text);const media=result.content.filter(x=>x.type==='image');media.forEach((x,i)=>fs.writeFileSync(path.join(out,`mcp-${name}-${i}.png`),Buffer.from(x.data,'base64')));fs.writeFileSync(path.join(out,`mcp-${name}.json`),JSON.stringify({isError:result.isError||false,content:result.content.filter(x=>x.type!=='image'),imageFiles:media.map((_,i)=>`mcp-${name}-${i}.png`)},null,2));console.log(name,'error?',!!result.isError,texts.join('\n').slice(0,1400));
 }
}finally{fs.writeFileSync(path.join(out,'spector-mcp-stderr.json'),JSON.stringify(stderr,null,2));await client.close();await transport.close();}
