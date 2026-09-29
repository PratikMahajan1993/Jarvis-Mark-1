# Orb Formulas (owner-chosen, particles.casberry.in style)

**Locked:** 2026-09-29. Model: [`EXPERIENCE_DECISIONS.md`](EXPERIENCE_DECISIONS.md) X5. Engine: [`PLATFORM_DECISIONS.md`](PLATFORM_DECISIONS.md) P6.

Each formula is a casberry-compatible function body, pasted **verbatim** between `USER CODE START` and `USER CODE END` into `frontend/src/substrate/formulas/<id>.ts`. It runs in the substrate worker for every particle on every frame.

**Contract:** `i`, `count`, `time`, `target.set(x, y, z)`, `color.setHSL(h, s, l)` / `color.set(...)`, and `addControl(id, label, min, max, initial)`. `setInfo` and `annotate` are no-ops in Jarvis, and `THREE.Vector3` is a stub used only by `annotate`.

## Rules shared by every formula

- **Idle** = the owner's exported `PARAMS`. If the export has no `PARAMS`, the slider defaults inside the formula are idle.
- **Colour** = the formula's own colour. It is not replaced by the section accent (owner confirmed).
- **Speed controls are clock rates** (for smoothness). Every speed control in these formulas only ever multiplies `time`:
  - Cortex: `t = time * pulseSpeed`
  - ASCI: `time * flow`
  - CHAT GPT: plain `time`
  
  Changing that control directly would jump the phase by `Δspeed × uptime`, which scrambles the swarm after a few minutes. So a speed control stays pinned at its idle value in the formula. The state value instead changes the rate of that formula's **own integrated clock**: `clock += dt × (stateSpeed / idleSpeed)`. The phase stays continuous, and the apparent speed matches the slider.
  
  Formula files list these in `speedControls`. Formulas with no speed control get a generic clock rate.
- **Clocks never restart.** Every formula's clock starts at boot and keeps advancing even when its section is off screen, so a shape never resets when you arrive at it.
- **Other controls** (chaos, distortion, neuroactivity) scale amplitudes, so they ease directly (springs, about 400 ms).
- **Fit:** at boot the worker samples each formula at idle and measures its bounding box. The section's `placement.height` then fits that box to the screen, whatever the formula's world units (ASCI is about 160 units tall; CHAT GPT reaches a radius of about 100).
- **Render (common to all three exports):** 20,000 instanced tetrahedra (size 0.25), flat colour, camera at z = 100 with a 60° field of view, auto-rotate, bloom (threshold 0, strength 1.8, radius 0.4). Particles ease toward targets at 0.1 per frame at 60 fps, made frame-rate independent (`k = 1 − 0.9^(dt·60)`). The exports' fog (`near 0.01`, default far) has no visible effect and is dropped.

| Section | Formula | File | Status |
|---|---|---|---|
| Casual | Cortex Dinamico | `cortex-dinamico.ts` | Received |
| Monitor | ASCI System | `asci-system.ts` | Received |
| Engineering | CHAT GPT ("Living Hyperfield") | `chat-gpt.ts` | Received |

---

## Cortex Dinamico — Casual

**Placement:** large and centred. The outer shell spans about 78% of the section's content height. Dim 1.0.
**Speed controls:** `pulseSpeed`.

**Idle `PARAMS` (owner confirmed):**

```json
{"radiusOuter":37.2,"radiusInner":18.8,"neuroActivity":0,"chaosFactor":0,"pulseSpeed":3.4}
```

**State controls:**

| State | chaosFactor (0–2) | pulseSpeed (0–5, clock rate) | neuroActivity (0–1) | Notes |
|---|---|---|---|---|
| idle | 0 | 3.4 | 0 | Owner export |
| listening | 0.3 | 2.0 | 0 | Calmer, attentive |
| thinking / executing | 1.4 | 4.6 | 0 | Agitated shell |
| speaking | 0.3 + 0.9·level | 3.4 | 0 | `level` = TTS amplitude |
| hitl | 0.2 | 1.2 | 0.83 | Hue shifts from blue to amber through the formula's own colour mix. The orb is already centred. |

**Formula (verbatim):**

```js
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
```

---

## ASCI System — Monitor

**Placement:** tall. The structure's fitted height is 70% of the viewport, centred horizontally, with its bottom edge above the command baton (`--chrome-bottom` plus a gutter). Dim 1.0.
**Speed controls:** `flow`.

**Idle `PARAMS`:**

```json
{"scale":45,"flow":0.7,"chaos":0.65,"twist":1.4}
```

**State controls:**

| State | flow (0–3, clock rate) | chaos (0–2) | Notes |
|---|---|---|---|
| idle | 0.7 | 0.65 | Owner export |
| listening | 0.45 | 0.35 | Calmer, attentive |
| thinking / executing | 1.6 | 1.2 | Faster, more organic |
| speaking | 0.7 | 0.5 + 0.9·level | Distortion follows the voice |
| hitl | 0.3 | 0.3 | The palette is already red-orange (hue 0.015–0.07), so HITL tints toward amber `#FFB020` at 0.65 **and** adds a 0.5 Hz brightness pulse to read clearly. The orb moves to the centre. |

`scale` and `twist` stay at idle in every state.

**Formula (verbatim):**

```js
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
```

---

## CHAT GPT ("Living Hyperfield") — Engineering

**Placement:** side orb at the right edge, upper third (centre about 0.93, 0.18). Fitted height is about 0.2 of the viewport. **Dim 0.35**, but state changes apply at full strength.
**Idle:** default formula. The export's `PARAMS` is empty and the formula has no controls.
**Speed controls:** none, so it uses the generic clock rate.

**State modifiers (generic):**

| State | Clock rate | Brightness | Tint |
|---|---|---|---|
| idle | 1.0 | 1.0 | — |
| listening | 0.7 | 1.25 | — |
| thinking / executing | 2.0 | 1.1 | — |
| speaking | 1.0 | 1 + 0.6·level | — |
| hitl | 0.5 | 1.0, with a 0.5 Hz pulse | Amber `#FFB020` at 0.65. This contrasts with its cyan-to-violet palette (hue 0.55–0.87). The orb moves to the centre. |

**Formula (verbatim):**

```js
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
```
