import { defineOrbFormula } from "./types";

export default defineOrbFormula({
  id: "asci-system",
  name: "ASCI System",
  params: { scale: 45, flow: 0.7, chaos: 0.65, twist: 1.4 },
  speedControls: ["flow"],
  body(i, count, target, color, time, addControl, setInfo, annotate, THREE) {
    // USER CODE START
const scale = addControl("scale", "Field Scale", 10, 100, 45);
const flow = addControl("flow", "Flow Speed", 0, 3, 0.7);
const chaos = addControl("chaos", "Organic Distortion", 0, 2, 0.65);
const twist = addControl("twist", "Spatial Twist", 0, 4, 1.4);

const u = i / (count > 1 ? count - 1 : 1);
const band = Math.floor(u * 120);
const local = u * 120 - band;
const angle = local * Math.PI * 2 + band * 0.618 + time * flow;

const waveA = Math.sin(angle * 3.0 + band * 0.13 + time * flow);
const waveB = Math.cos(angle * 2.0 - band * 0.09 + time * flow * 0.7);
const waveC = Math.sin(band * 0.21 + time * flow * 0.5);

const radius = scale * (
0.35 +
0.28 * Math.sin(band * 0.17 + time * flow) +
0.22 * waveA
);

const spiral = band * 0.055 + time * flow * 0.2;
const distortion = chaos * scale * 0.18;

const px = Math.cos(angle + spiral) * radius +
Math.sin(band * 0.31 + time * flow) * distortion;

const py = (band - 60) * scale * 0.028 +
waveA * scale * 0.22 +
waveB * distortion;

const pz = Math.sin(angle * twist + spiral) * radius +
waveC * scale * 0.35;

target.set(px, py, pz);

const hue = 0.015 + 0.055 * (
0.5 + 0.5 * Math.sin(angle + time * flow * 0.4)
);

const light = 0.28 + 0.5 * (
0.5 + 0.5 * Math.sin(band * 0.12 + angle * 2.0)
);

color.setHSL(hue, 1.0, light);

if (i === 0) {
setInfo(
"Living Data Field",
"A flowing computational swarm inspired by glowing ASCII systems, organic interference, and bold digital typography."
);
annotate(
"core",
new THREE.Vector3(0, 0, 0),
"BE BOLD"
);
}
    // USER CODE END
  },
});
