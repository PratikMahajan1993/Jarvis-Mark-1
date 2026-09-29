# Orb Formulas (owner-chosen, particles.casberry.in style)

**Locked:** 2026-09-29. Model: [`EXPERIENCE_DECISIONS.md`](EXPERIENCE_DECISIONS.md) X5.

Each formula is a casberry-compatible function body. It is pasted **verbatim** between `USER CODE START` and `USER CODE END` into `frontend/src/substrate/formulas/<id>.ts`, where it runs in the substrate worker for every particle on every frame.

**Contract:** `i`, `count`, `time`, `target.set(x, y, z)`, `color.setHSL(h, s, l)` / `color.set(...)`, and `addControl(id, label, min, max, initial)`. `setInfo` and `annotate` are no-ops in Jarvis.

**Idle values** are the owner's exported `PARAMS`. States move only the controls listed in each section's "State controls" table, and the values ease between states (never jump).

| Section | Formula | Status |
|---|---|---|
| Casual | Cortex Dinamico | Formula received (below) |
| Monitor | ASCI System | **Awaiting owner export** |
| Engineering | CHAT GPT | **Awaiting owner export** |

---

## Cortex Dinamico — Casual

**Placement:** large, centred in the section; the outer shell spans about 78% of the section's content height.
**Render settings (from the owner's export):** 20,000 instanced tetrahedra (size 0.25), flat colour, camera at z = 100 with 60° field of view, slow auto-rotate, bloom (strength 1.8, radius 0.4, threshold 0). Each particle eases toward its target by 0.1 per frame at 60 fps; Jarvis uses the frame-rate-independent equivalent.

**Idle `PARAMS`:**

```json
{"radiusOuter":37.2,"radiusInner":18.8,"neuroActivity":0,"chaosFactor":0,"pulseSpeed":3.4}
```

**State controls** (Synaptic Chaos `chaosFactor` 0–2, Pulse Speed `pulseSpeed` 0–5, Neuroactivity `neuroActivity` 0–1):

| State | chaosFactor | pulseSpeed | neuroActivity | Notes |
|---|---|---|---|---|
| idle | 0 | 3.4 | 0 | Owner export |
| listening | 0.3 | 2.0 | 0 | Calmer, attentive |
| thinking / executing | 1.4 | 4.6 | 0 | Agitated shell |
| speaking | 0.3 + 0.9·level | 3.4 | 0 | `level` = TTS amplitude |
| hitl | 0.2 | 1.2 | 0.83 | Hue shifts from blue to amber through the formula's own colour mix; the orb is already centred |

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

**Placement:** tall. The structure's height is 70% of the viewport, and its bottom edge sits above the command baton.
**State controls:** Flow Speed and Organic Distortion. Ranges and values are set once the export arrives, following the same pattern as Cortex: listening calms, thinking speeds flow and distortion up, speaking drives distortion from `level`, and hitl slows flow and tints amber while the orb moves to the centre.
**Formula:** *awaiting the owner's export (same "export code" format as Cortex Dinamico).*

---

## CHAT GPT — Engineering

**Placement:** side orb at the right edge, upper third; dimmed but reactive.
**Idle:** default formula values.
**State controls:** none named. States use the generic modifiers: time-scale (thinking ×2), brightness (listening, and speaking with `level`), and an amber tint plus centring for hitl.
**Formula:** *awaiting the owner's export.*
