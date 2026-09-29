import { defineOrbFormula } from "./types";

export default defineOrbFormula({
  id: "chat-gpt",
  name: "Living Hyperfield",
  params: {},
  speedControls: [],
  body(i, count, target, color, time, addControl, setInfo, annotate, THREE) {
    void addControl;
    // USER CODE START
const u = i / Math.max(1, count - 1);
const phi = Math.acos(1 - 2 * u);
const theta = i * 2.399963229728653 + time * 0.32;

const breathe = 1 + 0.22 * Math.sin(time * 1.7 + u * 18.0);
const warp = 1.0 + 0.28 * Math.sin(theta * 3.0 + time) * Math.sin(phi * 5.0);
const pulse = 1.0 + 0.16 * Math.sin(time * 2.4 + theta * 2.0 + phi * 7.0);

const radius = (18.0 + 42.0 * Math.pow(u, 0.42)) * breathe * warp * pulse;

const twist = time * 0.22 + radius * 0.018 + Math.sin(phi * 6.0 + time) * 0.35;
const ct = Math.cos(theta + twist);
const st = Math.sin(theta + twist);
const sp = Math.sin(phi);
const cp = Math.cos(phi);

const x = radius * sp * ct;
const y = radius * cp + Math.sin(theta * 4.0 + time * 1.3) * 3.5;
const z = radius * sp * st;

const fold = Math.sin(x * 0.09 + time) * Math.cos(z * 0.075 - time * 0.7);
const lift = fold * 5.5 + Math.sin(y * 0.12 + theta) * 2.5;

target.set(
x + fold * 2.2,
y + lift,
z + Math.cos(x * 0.06 + z * 0.08 + time) * 3.0
);

const hue = (0.55 + u * 0.32 + fold * 0.035 + time * 0.025) % 1.0;
const light = 0.42 + 0.18 * Math.abs(Math.sin(theta * 2.0 + time));
color.setHSL(hue, 0.9, light);

if (i === 0) {
setInfo("Living Hyperfield", "A breathing spherical field warped by layered interference waves.");
annotate("core", new THREE.Vector3(0, 0, 0), "INTERFERENCE CORE");
}
    // USER CODE END
  },
});
