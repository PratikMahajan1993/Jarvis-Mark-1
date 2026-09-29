/* eslint-disable prefer-const */
import { defineOrbFormula } from "./types";

export default defineOrbFormula({
  id: "cortex-dinamico",
  name: "Cortex Dinamico",
  params: { radiusOuter: 37.2, radiusInner: 18.8, neuroActivity: 0, chaosFactor: 0, pulseSpeed: 3.4 },
  speedControls: ["pulseSpeed"],
  body(i, count, target, color, time, addControl, setInfo, annotate, THREE) {
    // USER CODE START
const radiusOuter = addControl("radiusOuter", "Cortical Radius", 10, 50, 30);
const radiusInner = addControl("radiusInner", "Deep Radius", 5, 25, 15);
const neuroActivity = addControl("neuroActivity", "Neuroactivity Level", 0, 1, 0.0);
const chaosFactor = addControl("chaosFactor", "Synaptic Chaos", 0, 2, 0.5);
const pulseSpeed = addControl("pulseSpeed", "Pulse Speed", 0, 5, 1.0);

let t = time * pulseSpeed;
let iNorm = i / count;
let layer = iNorm < 0.5 ? 0 : 1;
let localI = layer === 0 ? i : i - (count / 2);
let totalLocal = count / 2;

let phi = Math.acos(1 - 2 * (localI + 0.5) / totalLocal);
let theta = Math.sqrt(totalLocal * Math.PI) * (localI + 0.5);

let r = layer === 0 ? radiusOuter : radiusInner;
let x = r * Math.sin(phi) * Math.cos(theta);
let y = r * Math.sin(phi) * Math.sin(theta);
let z = r * Math.cos(phi);

let noiseX = Math.sin(t * 0.5 + phi * 3) * Math.cos(t * 0.3 + theta * 2);
let noiseY = Math.cos(t * 0.4 + phi * 2) * Math.sin(t * 0.6 + theta * 3);
let noiseZ = Math.sin(t * 0.7 + phi + theta);

let moveAmt = layer === 0 ? chaosFactor * 1.5 : chaosFactor * 0.5;
x += noiseX * moveAmt;
y += noiseY * moveAmt;
z += noiseZ * moveAmt;

let pulse = Math.sin(t * 2 + i * 0.01) * 0.05 + 1;
x *= pulse;
y *= pulse;
z *= pulse;

target.set(x, y, z);

let hStart = 0.6;
let s = 0.8;
let l = 0.5;
let hEnd = 0.0;
let hMix = neuroActivity;
let hFinal = hStart * (1 - hMix) + hEnd * hMix;

let lVar = layer === 0 ? 0.5 : 0.3 + (neuroActivity * 0.4);
let sVar = layer === 0 ? 0.8 : 0.6 + (neuroActivity * 0.3);

color.setHSL(hFinal, sVar, lVar);

if (i === 0) {
    setInfo("Neuroplasticity Brain", "Outer: Synaptic Chaos | Inner: Deep Activity");
    annotate("core", new THREE.Vector3(0, 0, 0), "Neural Core");
}
    // USER CODE END
    void s;
    void l;
  },
});
