const fs=require('fs'),path=require('path'),crypto=require('crypto');
const source=fs.readFileSync(path.join(__dirname,'../igloo-forensics-pass-1/evidence/App3D-f554a111.js'),'utf8');
const spans=[
['S01','root-input-and-idle',1476559,6800],['S02','root-route-choreography',1480421,3600],
['S03','hero-construction',1195644,5400],['S04','hero-scroll-path',1200300,1600],
['S05','hero-fragment-response',1180962,2019],['S06','hero-shading-displacement',1177517,2100],
['S07','cube-camera-and-rendering',1304184,5800],['S08','cube-object',1295632,8552],
['S09','cube-title',1265588,3792],['S10','cube-readout',1269380,3753],['S11','cube-cta',1273133,3730],
['S12','entry-path-and-overlap',1404905,6800],['S13','finale-selector',1351514,3900],
['S14','finale-visit',1347327,4187],['S15','finale-arrows',1339417,4800],
['S16','particle-continuity',1355503,14700],['S17','detail-object',1454696,3600],
['S18','detail-scene',1472532,2300],['S19','camera-wrapper',861351,3300],
['S20','hero-manifesto',1182981,9903],['S21','global-ui',1450450,1986],
['S22','compositor',1098956,7200],['S23','preparation-barriers',1475574,985],
['S24','ground-interaction-glow',1110002,6700]
];
const out={source:'work/igloo-forensics-pass-1/evidence/App3D-f554a111.js',sha256:crypto.createHash('sha256').update(source).digest('hex'),offset_basis:'Zero-based UTF-16 JavaScript string code units; end-exclusive length. Some spans begin inside methods.',snippets:spans.map(([id,role,offset,length])=>({id,role,offset_utf16:offset,length_utf16:length,snippet:source.slice(offset,offset+length)}))};
fs.writeFileSync(path.join(__dirname,'evidence/source-snippets.json'),JSON.stringify(out,null,2));
const r=JSON.parse(fs.readFileSync(path.join(__dirname,'evidence/probe.json')));
const summary=r.states.map(s=>({label:s.label,t:s.time,y:s.scroll.y,target:s.scroll.targetY2,velocity:s.scroll.velocity,auto:s.autoCenter.animating,url:s.url,detail:s.root.uDetailProgress,entryP:s.scenes[2].progress,entryFov:s.scenes[2].camera.fov,entryCamera:s.scenes[2].camera.basePosition,entryUp:s.scenes[2].camera.up,ring:s.scenes[2].post.uRingProximity,link:s.scenes[2].currentLink,extraNoise:s.scenes[2].particleCompute.uAdditionalNoise}));
fs.writeFileSync(path.join(__dirname,'evidence/probe-summary.json'),JSON.stringify({source:r.source,method:r.method,states:summary,console:r.console},null,2));console.log(JSON.stringify({spans:spans.length,states:r.states.length,identical:r.source.identical,console:r.console.length,hash:out.sha256}));
