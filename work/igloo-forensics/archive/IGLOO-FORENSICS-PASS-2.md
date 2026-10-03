# Igloo — forensic investigation, pass 2

**Adversarial review and experience choreography · 3 October 2026 · desktop scope**

Igloo's strongest transferable quality is its control over **how a composition becomes available, responds, and comes to rest**. It combines continuous travel with scene-specific settling, independently staged text, material feedback, and selective preservation of visual anchors. Identifying the rendering libraries does not explain that choreography.

This report challenges [Pass 1](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics/archive/IGLOO-FORENSICS-PASS-1.md) against its retained evidence and a small, targeted second browser run. It is neither a Jarvis redesign nor an implementation plan. Visual identity, assets, branding and exact technology choices are outside the transferable conclusions.

**Confidence discipline:** **Confirmed** means verified production code, captured runtime state, or inspected pixels; the supporting modality is specified. **Strongly inferred** means an interpretation supported by multiple mechanisms/observations, without causal isolation. **Speculative** means unresolved. Source timings describe intended control, not measured latency or guaranteed smoothness. Perceived-polish rankings are interpretations, not experimental results.

**Evidence key:** `Bxx` refers to Pass 1's [bundle snippets](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/bundle-snippets.json). `Sxx` refers to Pass 2's [source extracts](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/source-snippets.json), sliced independently from the production bundle. Offsets are zero-based UTF-16 code units. `P:<label>` identifies a sample in [probe.json](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/probe.json); a [compact state index](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/probe-summary.json) accompanies it. These references apply to the archived hash, not arbitrary future builds.

The [probe](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/probe.cjs) checked that the fetched production bundle exactly matched the archive: SHA-256 `54e3068a859b5b027d55e474b7ccf5aadf8df071e27689b3cfac073ad62cca48`. A browser-local response adapter exposed the controller without changing its methods. It recorded 37 states using Edge, 1440 × 900, DPR 1, without Spector. Selected missing phases were reached by **directly setting logical progress**; these are controlled interventions, not evidence of natural input trajectories. Wheel, project open/close, finale hover and ArrowRight were real inputs. Screenshot work adds time: filenames such as `open-300` denote requested incremental waits, not 300 ms since the click. Use recorded `time` values. The final idle sample approached the destination with its tween still active; it does not certify completed settling. No audio recording or performance benchmark was made.

## 1. Pass 1 adversarial assessment

**Confirmed — source/runtime/GPU evidence:** Pass 1's central architecture survives challenge: custom logical scrolling over a stationary browser document; three main scene outputs; a separate detail output; source-controlled overlap and cyclic progress; a shader compositor; MSDF typography; and independent camera/object paths. The captured composite → global UI → bloom → SMAA ordering also survives inspection. Existing GPU extracts establish this without another expensive capture: hero command 241 uses the introductory compositor, cube command 225 uses the main compositor, and detail command 84 has detail progress 1. [Retained draw evidence](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/spector-cube1-draws.json), B15/B22/B37.

**Confirmed — evidence limitations:** Pass 1's screenshots are not a motion trace. `behaviors.cjs` waits 1.8 s between wheel inputs, then evaluates, captures and writes; snapshot timestamps are farther apart. Its inputs repeatedly encounter inactivity behavior. `deep-desktop.cjs` also mixes wheel pulses and long waits, without logging logical progress. “Frame N after wheel N” cannot identify a unique scene destination, transition duration, or cause of movement. A six-second footer wait does not prove rest when source centering can last twenty seconds. [Behavior script](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/behaviors.cjs), [deep script](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/deep-desktop.cjs).

**Strongly inferred — assessment:** The main weakness is interpretive selectivity. Pass 1 devotes substantial attention to container formats, attachment sizes, library versions and command counts, while underexplaining who controls time, why some text holds position, and how a transition keeps the viewer oriented. Those implementation facts can be correct and still have little explanatory value for cinematic feeling.

Pass 1 generally avoids claiming proven 60 FPS, fully dynamic lighting, active depth of field, or causal proof of polish. Those restraints should survive. Its “coordinated control of the entire frame” thesis is reasonable, but should be narrowed: different subsystems share state while retaining different eligibility rules, clocks and spatial roles. They do not all obey one animation timeline.

## 2. Corrections and disputed findings

1. **Confirmed — Pass 1 §11 is wrong about finale hover selecting a shape.** Visit hover refreshes its reveal/text and emits a cue. Arrow hover blinks the arrow. Selection changes on Left/Right keys, a half-screen click, or a qualified horizontal swipe. The probe retained `currentLink=0` on Visit hover and changed it to 1, then 2, on ArrowRight. Pass 1's `deep-footer-hover.png` still displays LinkedIn. Its label is not evidence of a morph. S13–S15; P:`finale-visit-hover`, `finale-right-180`, `finale-medium`.

2. **Confirmed — “main UI in an orthographic scene” is too broad.** Global logo/sound/scroll/close and detail copy are orthographic. The hero manifesto belongs to the perspective hero scene, numerically positioned to look screen anchored. Cube annotations billboard toward the camera while following transformed cube anchors. Finale Visit belongs to the entry scene; arrows are attached to the particle group. S09–S11/S14/S15/S20/S21. This changes what survives the environmental compositor.

3. **Confirmed — the supporting bundle analysis is wrong to generalize hero scrolling as increasing fragment displacement.** The scroll-fragmentation factor decreases from 1 to 0 over hero local progress 0–.4. Pointer influence increases separately toward .495. Forward travel from the normal hero composition does not monotonically explode the igloo. S05/S06. Pass 1's broader claim that fragments really move remains valid.

4. **Confirmed — idle centering is scene dependent.** The hero has no interior `autoCenter` method. Its intro deliberately places progress near global .66, and boundary return can target that composition; later interior stops are free. In the probe, wheel +300 moved .66 → .885 and remained there after several seconds. Cubes select the nearest object; entry targets a finale after local progress .15. Treating .66 as the destination of every stop is false. S01/S03/S07/S12; P:`hero-wheel-1800`.

5. **Confirmed — two seconds is a boundary-centering baseline, not a universal duration.** Root adds scene-offset-dependent time. For example, the incoming hero calculation yields approximately 3.3165 s before rounding its destination; entry's incoming calculation yields 2.6 s. These are source-derived tween durations. B22/S01.

6. **Confirmed — “velocity” is neither raw wheel speed nor total scene speed.** It accumulates absolute movement introduced inside the root smoothing step, decays and clamps. `centerScroll` directly tweens `y` and synchronizes both targets; this need not feed the same movement accumulator. In the probe, automatic travel continued from `y=7.530302` to `9.127326` while recorded velocity was zero. Thus “all moving views produce velocity effects” would be wrong. Pass 1's equation is correct; its meaning needs this qualification. S01; P:`entry-idle-1400`, `entry-idle-1700`.

7. **Confirmed — route gating does not wait for every visual tail.** Detail navigation unlocks at delay +2 s; its camera tail continues to delay +2.5 s. Close restores main scroll after 1 s, while the primary blend lasts 1.25 s and cube recovery lasts 1.45 s. “Prevents overlapping choreography” should mean preventing conflicting primary navigation, not eliminating all overlap. S02/S07/S18.

8. **Confirmed — selected-object continuity does not establish a shared mesh.** Cube interior and detail object are separate mesh instances with related cached geometry and different materials/cameras. The viewer can retain object identity while the renderer replaces its representation. S08/S17/S22. Likewise, outline-to-solid construction uses overlapping representations, not a demonstrated geometry morph.

## 3. Important findings Pass 1 missed

**Confirmed — source:** Cube labels combine progress eligibility and clock animation. Camera-relative proximity triggers connector growth (~.2 s), glyph appearance (~.4 s), and unscrambling (~.75 s); exit uses short fades. The letters do not simply scrub backward and forward with every wheel delta. S09–S11.

**Confirmed — source/runtime:** Entry inactivity can complete the remaining journey. At interior local progress above .15, its destination is .76, not the nearest portal. A small wheel input after placement at .4 led to automatic travel toward .76. The user can initiate movement and then let an authored sequence finish it. S12; P:`entry-idle-*`.

**Confirmed — source:** The finale morph swaps the attraction volume while retaining simulated particle positions and velocities. Noise briefly rises and recedes; the floor gets a separate three-second phase change; link text and arrows refresh. There is persistent material state underneath a discrete selection. S13/S16.

**Confirmed — source:** Particle initialization advances the computation for approximately 1,000 ms of accumulated simulation delta before its visibility uniform is enabled. This is shape preparation, distinct from a loading overlay or shader compilation. It is not proof of a one-second visible startup delay. S16, offset 1367171.

**Strongly inferred — visual/source synthesis:** Sparse transit space is part of the pacing. The controlled midpoint between portfolio objects shows mostly atmosphere, with one enclosure exiting above and another arriving below. Information density drops between composed stops. That breathing space is lost if the experience is described only as “three project cubes.” [Midpoint capture](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/between-cubes.png), S07.

## 4. Igloo's actual interaction model

**Confirmed — source:** One continuous, cyclic logical coordinate `y` drives the main experience; the browser itself does not scroll. The loop is 10.85 units. Scene heights are hero 2.35, cubes 3, entry 5.5. Local progress includes a one-unit virtual viewport: `(view bottom − scene top)/(scene height + 1)`. Scene overlap is consequently an interval, not an instantaneous switch. S01, B16/B18/B19.

Useful global intervals are hero → cubes **1.35–2.35**, cubes → entry **4.35–5.35**, and entry → hero **9.85–10.85**, excluding exact endpoint/rounding qualifications. Cube destinations are **2.35, 3.35, 4.35**; finale local .76 maps to **9.29**. They are animation coordinates, not native scroll offsets.

**Confirmed — source:** Continuous position and discrete destinations coexist. Wheel input chooses a target; smoothing makes motion continuous; inactivity applies different destination policies. Intro, detail open/close, label reveals and link changes introduce timed events. Independent time animation, camera pointer response and persistent simulations continue at unchanged `y`.

**Strongly inferred — model:** The experience alternates **travel, presentation, inspection and release**. Travel is input-led until settling takes over. Presentation stabilizes a focal object. Inspection exchanges a tactile object view for readable detail. Release restores the selected context or carries the viewer toward the finale. These are behavioral roles, not four hidden source classes.

## 5. Scene-by-scene choreography map

### 5.1 Loading and constructed arrival

**Confirmed — source/pixels:** Before interaction, a flat gray field holds the DOM ASCII loader. Asset/upload readiness leads into an automatic construction scene. There is no wheel requirement for this arrival. Outline and cage establish spatial structure; solid fragments, terrain and atmosphere join while the first representations dissolve. [Existing arrival contact sheet](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/desktop-intro-contact.png), S03.

Relative to the intro clock: outline materializes 0–2.5 s; cage reveal starts at 0 and its fade runs 2.1–5.1 s; solid materialization runs 1.1–3.35 s; terrain/mountain reveal extends approximately .7–8.2 s. Camera blending from the high arrival view runs 2–7.5 s. UI starts its own reveal at 4.5 s; bloom intensity eases from 1.5 to 1 over 2.5–4.5 s. These are overlapping envelopes, not consecutive loading steps.

**Confirmed — source:** `playInAnimation` resolves at five seconds, enabling the main interaction before every reveal/camera tail is finished. Loader outro, readiness, interaction availability and visual completion are separate milestones. Audio routing exists, but an audible arrival is contingent on context/decoding/mute state. B02/B14/B48–B50/S03.

**Strongly inferred — continuity:** The outline is a promise of the later object. Matching location and silhouette let filled fragments appear to grow out of the technical scaffold. Background formation makes the object belong to a world instead of popping into a finished image.

### 5.2 Hero: composed but alive

**Confirmed — source/runtime:** Intro settles near `y=.66`, hero local progress approximately .4955. The igloo, snow-covered foreground and mountains establish a stable central composition; manifesto and global identity occupy opposing upper regions. Rest retains time motion, pointer-responsive fragment displacement, low-amplitude camera motion and wind texture activity. P:`hero-settled`; S03–S06/S19/S20.

Pointer proximity changes fragment matrices through filtered displacement/rotation, while displaced versus assembled shading and emission respond with it. The ground receives an approximate interaction glow (S24). A bright opening is therefore not solely an actual moving light. Wheel advances the hero camera path: position and target lower on different envelopes, then position shifts laterally/deeper. The text remains visually anchored until its own visibility rules change.

**Confirmed — source:** Forward scroll fragmentation decreases over early local progress; pointer and autonomous displacement remain separate. Interior wheel motion can settle wherever smoothing ends. Scene exit uses the compositor rather than turning the hero into a portfolio enclosure. Wind gain follows scene progress and fades near exit; heard output was not verified. S04–S06/S20.

### 5.3 Hero → portfolio

**Confirmed — source/pixels:** Wheel-led `y` enters the one-unit overlap. Hero and cubes are rendered concurrently with independent cameras. A textured diagonal wash, displacement and chromatic edges obscure parts of the outgoing terrain while the portfolio environment enters. The manifesto is in the outgoing scene and can be distorted; the global logo/sound remain clearer above the composite. [Controlled overlap](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/hero-cubes-overlap.png), S01/S20/S22.

**Strongly inferred — continuity:** Neutral cold color, bright fragments, suspended fine particles and stable global controls connect the two representations. The image resembles movement through a material veil. There is no evidence that mountain geometry becomes the cube, or that both occupy one continuous world. Stopping in the overlap invokes boundary centering rather than holding an arbitrary half-transition forever. S01.

### 5.4 Pudgy Penguins → Overpass → Abstract

**Confirmed — source/runtime:** Each stop presents one refractive enclosure, a recognizable inner object, geometric traces, a project title and explore prompt. The probe reached all three centers. The camera and its target travel vertically together by `−23 × local progress`; recorded base-camera y values were −5.75, −11.5 and −17.25. Object distance-dependent rotation complements this transport; slower independent motion remains. [Overpass](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/overpass.png), [Abstract](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/abstract.png), S07/S08.

This is travel within the **same cube scene**, not three whole-screen scene composites. Enclosures pass through the frame, separated by atmosphere. Their annotation groups enter eligibility windows, then complete timed line/glyph reveals. Idle chooses the nearest cube with a distance-dependent duration around 1.6–2.4 s. Distance-derived rotation decreases toward the centered pose; velocity-linked FOV approaches 45 degrees as activity decays. S07–S11.

Pointer movement on the surface writes UV-space frost history, affecting the material beyond a single hover frame. Refraction, plexus feedback and filtered shard-audio gain accompany it; runtime visual comparison alone cannot separate frost from continuing rotation and lighting. Existing [frost capture](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/deep-cube1-frost.png), B27/B41. The temperature-like readouts are interface animation data here, not verified physical measurements.

### 5.5 Portfolio object → detail → selected object

**Confirmed — source/runtime:** Clicking an eligible cube opens its matching route and disables main wheel travel. It also centers the selected object if necessary. Let that centering duration be `D`; the reveal delay is `a=D/2`, allowing centering and opening to overlap. S02. The probe opened Abstract and returned to `y=4.35`, preserving its selected cube rather than resetting to Pudgy. P:`abstract-open-*`, `abstract-close-*`.

Outgoing camera z moves from 5 toward 1.5; extra rotation/pointer influence is suppressed and the plexus gets a click envelope. Primary composite progress runs over 1.25 s after `a`, secondary over 1.25 s after `a+.75`. Meaningful detail mixing starts around primary .4. Incoming camera z approaches 2.5 from 4 over two seconds starting at `a+.5`. S02/S07/S18/S22.

The environment darkens into a blue-black field; a separate darker, caustic-shaded version of the selected object remains behind the copy. At `a+1.2`, a text-show event begins glyph staging while camera travel continues. Logo/sound persist; Close becomes available; the explore annotations leave. The global copy is rendered after the environmental composite, so its reveal is independently legible. S17/S18/S21, B44. [Detail appearance](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/deep-detail-ready.png).

In detail, wheel input belongs to a separate clamped/smoothed text group with edge fading; it does not move the main world. Pass 1's 900-pixel viewport did not require overflow, so scrolling long copy remains source-confirmed rather than demonstrated. On Close, copy hides, the camera retreats and the detail blend reverses. The selected cube restores its camera/pointer/rotation over 1.45 s, with main input resuming after 1 s. Small visual tails coexist with restored control. S02/S07/S18, B44/B45.

### 5.6 Portfolio → portal traversal

**Confirmed — source/pixels:** Continued wheel travel enters the cube/entry overlap. The enclosure leaves above while broken rings emerge within the same gray atmospheric vocabulary. Global controls persist. This boundary is an image composite; no object-to-ring geometry transformation was found. [Boundary capture](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/cubes-entry-overlap.png), S01/S12/S22.

Inside entry, the camera descends toward y≈−9.83 while its target changes separately. Its up vector rotates through π and blends toward conventional up; z and FOV change as well. The rings have supporting rotations but stay at authored vertical levels. Camera translation/orientation supplies most of the traversal; ring motion alone cannot explain it. S12.

Three local-progress regions around **.28, .375, .465** carry portal audio proximity peaks. Shader `uRingProximity` pulses align with the scrubbed timeline's internal phases. Angular/noise distortion, square displacement and glare intensify near authored crossings. They are progress events, not generic high-speed camera shake. [First crossing](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/entry-p0-28.png), [later crossing](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/entry-p0-465.png), S12, B29.

There is no authored rest at each ring. Once interior progress exceeds .15, inactivity drives toward .76; duration is `clamp(abs(logical distance) × 4, 2, 20)` seconds. New main scroll input can interrupt centering. P:`entry-idle-*`, S01/S12.

### 5.7 Portal → particle chamber

**Confirmed — source/pixels:** This transition happens within **entry**, not via another main-scene seam. On its 9.2-unit scrubbed timeline, particles become visible at 1.5 and gain opacity through 4; initial glow recedes over 3.9–4.9; formation noise recedes over 3.5–5. Floor enters at 3.4, forcefield at 4, cylindrical text at 4.5, with smoke and ambient particles overlapping. Those numbers are internal phase units, not guaranteed wall-clock seconds under wheel control. S12.

Rings/tunnel/snow disappear by roughly local .52; the room ring appears after .53. The central bright disturbance resolves into a particle-built character while the camera shifts from downward traversal toward a frontal presentation. The incoming subject already exists during the outgoing rings. [Chamber emergence](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/entry-p0-55.png).

**Strongly inferred — continuity:** The brightest central region becomes the next focal subject; ring and platform motifs continue to frame it. This is continuity of attention and overlapping layers. It is not evidence that the ring fragments become the particles.

### 5.8 Finale selection and loop release

**Confirmed — source/runtime:** Near local .76/global 9.29, camera orientation is nearly conventional, FOV nearly 30, and a particle subject sits between illuminated circular forms. Arrows and the selected bottom link are enabled only within `.64 < progress < .9`. This aligns input availability with a usable presentation. S12–S16; P:`entry-p0-76`.

Pointer fluid input perturbs particle state; movement also feeds particle-audio response. Visit hover refreshes the current label. Left/Right keys or half-screen clicks change selection; the dedicated Visit click suppresses carousel advancement and opens the current destination. No external links were clicked in this pass. S13–S15.

Selection immediately replaces the attraction volume/scale, introduces extra noise that decays over .5 s, and retains the particle simulation. Floor phase changes over three seconds and arrows/link text refresh. The probe changed the character to X and then Medium without changing `y`. These are distinct selection transitions inside one resting scene. [X selection](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/finale-right-settled.png), [Medium selection](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/finale-medium.png). Filenames do not certify that every particle had converged.

Continued vertical travel hides finale UI as eligibility ends, then overlaps entry and hero at the loop seam. Source wrapping and Pass 1's positive traversal corroborate return to the hero; this pass did not film the full seam or negative wrap. The global identity persists, while the landscape returns. Exact perceptual seamlessness remains unverified. S01/S12; [retained loop return](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/deep-loop-after-footer.png).

## 6. Transition anatomy

Four mechanisms must remain distinct:

- **Confirmed — image replacement:** Hero/cubes/entry boundaries render two worlds and mix their outputs through a textured seam. Continuity is manufactured by the compositor and persistent UI. S01/S22.
- **Confirmed — spatial travel:** Moving between cubes and through portals changes cameras, object pose and eligibility within one scene. These transitions do not require swapping the entire rendered world. S07/S12.
- **Confirmed — timed inspection:** Project opening replaces representations while centering, pushing a camera, suppressing motion and staging readable copy. Its outgoing and incoming envelopes intentionally overlap. S02/S07/S18.
- **Confirmed — persistent-state reformation:** Finale selection changes a simulation target while retaining particle state. It has discrete intent and continuous resolution. S13/S16.

**Strongly inferred — shared anatomy:** Each mechanism preserves something the viewer can track, destabilizes a bounded part of the image, lets the next focal element become recognizable, and then reduces competing motion. The anchor may be a subject, a bright region, framing, or global controls. It need not be a literal shared mesh.

Transition masking has a cost: the controlled mid-cube view contains little actionable content, and frost/distortion can obscure recognition. That supports “authored transit” as an interpretation; it does not establish uninterrupted usability or an appropriate interaction for a task-heavy product.

## 7. Camera/object/UI/shader coordination

**Confirmed — source:** Camera motion establishes viewpoint; geometry responds locally; shaders change material appearance and hide representation changes; typography chooses when information is readable. These roles cooperate without sharing identical motion curves. S03–S22.

The hero fragment response couples actual transforms with preauthored assembled/displaced shading and emissive treatment. The cube scene pairs vertical camera transport with enclosure rotation, material history and anchored labels. Detail suppresses extra motion as the copy arrives. Entry pairs camera orientation with portal proximity distortion, then reveals a new focal subject before removing the traversal layers. Finale selection adds a brief disturbance while its longer floor response sustains the event.

**Confirmed — GPU/source:** Global UI enters after the environmental compositor but before global bloom/SMAA. It can remain crisp through an environmental frost seam while still sharing the frame's glow/output treatment. Scene-local annotations behave differently because they are already inside the scene textures. This division explains visual continuity more usefully than “everything is WebGL.” B37/S20/S21/S22; retained cube/detail draw extracts.

**Strongly inferred:** Consistent gray/cold environments, bright focal accents and a restrained typographic vocabulary help unrelated scene representations feel connected. Material maps, LUTs, emissive shaders and compositing establish this appearance; it should not be described as entirely live physical lighting. No exact baked/live lighting allocation or causal ranking was measured.

## 8. User input, smoothing and settling behavior

**Confirmed — source:** Desktop wheel delta scales by .00075. Raw target → bounded intermediate target uses FPS-adjusted .075 interpolation with a limited step; intermediate target → displayed `y` uses .15. Raw target is constrained near displayed progress, so an oversized single event can discard excess motion. ArrowUp/Down inject ±.1125 logical units. These constants are mechanism evidence, not transferable tuning recommendations. S01, B46.

The accumulated velocity envelope decays with FPS-adjusted .98 friction and is unsigned. Cube FOV responds as `45 − 5 × velocity`. It persists after wheel input, but is not a trustworthy measure of all camera motion. The fixed active compositor slope does not follow it; the old velocity-dependent slope is commented out. B15/S01/S07/S22.

**Confirmed — source/runtime:** Inactivity is detected from unchanged `targetY2`, not a direct last-wheel timestamp. After 1.4 s it requests either boundary resolution or scene-specific settling. Boundary tweens, nearest-cube centering and entry centering toward the finale are different policies; entry can also return backward toward .76 from beyond that composition. Hero interior has no obligatory destination. `centerScroll` rounds the destination to two decimals, directly tweens `y`, and synchronizes its targets. P:`hero-wheel-*`, `entry-idle-*`; S01.

**Confirmed — source:** Pointer camera smoothing is additional to progress smoothing. Camera-wrapper lerp settings filter pointer angular/target/roll terms; they do not prove the whole base camera path is separately eased. Actual camera position can differ from `basePosition`, and hidden scene cameras can retain stale values while their compositor is skipped. Read samples only with scene visibility. S19; P camera/visibility fields.

**Strongly inferred — experience:** User agency varies deliberately. Continuous input controls travel; inactivity can restore presentation or finish a dramatic passage; timed reveals finish small communication events. “Smooth scroll” is too imprecise to capture that division. Authored rest means a readable, stable focus with restrained life, not zero animation.

## 9. What creates the perceived cinematic polish

The following ranking is **Strongly inferred**, grounded in the mechanisms above; no ablation study isolated their effects.

1. **Compositions with recovery behavior.** Portfolio subjects become centered and legible; finale travel has a destination. Free interior hero rest prevents a universal snap model. Stability supplies contrast to movement.
2. **Staging across different clocks.** Structure precedes substance in arrival; subject centering overlaps inspection; copy arrives during camera approach; labels finish after entering a proximity window. Interest and comprehension emerge in sequence.
3. **Attention continuity across replacement.** Stable global controls and recognizable subjects outlast environmental change. Bright central disturbances resolve into focal objects. Literal geometry continuity is often unnecessary.
4. **Feedback expressed through the scene.** Pointer effects alter fragments, ice history and particle motion. Interaction feels consequential because response belongs to the material being inspected.
5. **Restraint at the destination.** Extra motion is suppressed for detail reading; portal distortion is localized to crossings; formation noise subsides as the finale becomes recognizable. Effects have an envelope and a reason to end.
6. **Prepared presentation.** Upload/compile preparation and particle preconditioning reduce the chance of exposing an unfinished first appearance. The strategy is confirmed; absence of hitches is not.

**Speculative:** Sound may substantially increase perceived weight and cohesion. Progress/interaction-linked gain and cue events support that intent, but no independent listening established the audible result, latency or perceptual contribution. Visual evidence already supports the choreography without assuming sound was heard.

## 10. High-value transferable principles

These are **Strongly inferred principles**, not prescriptions for another product's appearance or renderer.

- Define the usable resting composition as carefully as the journey toward it. Decide where inactivity should help, where it should leave the user's position alone, and where it may finish a sequence.
- Separate continuous position from discrete intent. A smooth coordinate can coexist with selected objects and explicit destinations.
- Let communication finish its own reveal after eligibility is established. Avoid making every glyph's readability fluctuate with each tiny input reversal.
- Preserve a recognizable anchor through major changes, even when its underlying representation changes.
- Coordinate camera, object, material and information without forcing them to move simultaneously or share one easing curve.
- Give transition effects bounded phases: establish, disturb, reveal, recover. Their disappearance is part of the choreography.
- Distinguish feedback from navigation. Visit hover acknowledges attention; selection input reforms the subject; Visit click opens its destination.
- Prepare the first visible state before exposing it. Loading completion and presentation readiness are different concerns.

These principles can be expressed without ice, a landscape, particles, shader typography, cinematic cameras, or Igloo's package choices.

## 11. Low-value details that should not influence another product

**Confirmed facts, low transfer value:** Three/GSAP version numbers; KTX2 codec variants; exact render-target formats and dimensions; 150,000 particles; transmission sample counts; fullscreen triangle choice; the shadow-root arrangement; cube vertical spacing; the 10.85-unit loop; exact FOVs, delays and smoothing coefficients. They explain this implementation or aid verification. They are not reasons to reproduce it.

**Strongly inferred:** MSDF and one-frame rendering make certain effects convenient, but all-WebGL text is not a general condition of polish. The retained accessibility tree exposes little of the visible interface. Infinite travel, automatic portal completion, long centering and information-free transit can conflict with other products' goals. Transfer the judgment about continuity and arrival, not the mechanics by default.

The highest-value GPU result here is the **ordering of environmental transition and persistent UI**, not a command-count budget. Pass 1's low-level inventory remains useful as an appendix to a consolidated reference, rather than its narrative center.

## 12. Remaining unknowns

- **Unknown:** Audible mix, first-gesture cue execution, latency, spatialization and perceptual importance. Downloaded assets and emitted events do not establish playback.
- **Unknown:** Full reverse traversal, negative loop wrap and the exact visual quality of the cyclic seam. Direction-sensitive entry shader behavior exists in source; full reversal was not captured here.
- **Unknown:** Rapid input interruption during detail return, browser history/deep-link recovery and long-copy overflow. Source paths exist; this focused run exercised centered Abstract open/close only.
- **Unknown:** Exact wall-clock timing under ordinary interaction. Direct phase placements resolve composition/state questions; sparse screenshots do not measure transitions or their velocity profiles.
- **Unknown:** Hardware-independent smoothness and the causal benefit of warm-up. Five scene upload promises are awaited, but two main-plane `_upload()` calls are initiated without awaiting them; not every possible pass is proven prepared before readiness. S23, B08/B09.
- **Unknown:** Complete accessibility/reduced-motion/failure behavior, cross-browser and mobile choreography. Desktop scope is inherited from Pass 1; retained mobile files were not promoted into conclusions.
- **Unknown:** Exact lighting provenance and how much each effect contributes to perceived polish. Asset/source evidence narrows the mechanisms without reconstructing original authoring files or isolating aesthetic causes.

The second probe recorded no console warning/page-error events in its observed sequence. That is bounded evidence, not an error-free-site claim. Its first attempts encountered sandbox network denial and a controller serialization error; the successful run filtered numeric fields and completed. It was not a GPU capture. Production data and Pass 1 evidence were preserved.

## 13. Findings that should survive into the final consolidated reference

1. **Confirmed:** Logical scroll is continuous and cyclic; destination behavior is scene specific. Preserve the distinction between free hero interior rest, cube centering, boundary resolution and entry completion.
2. **Confirmed:** Choreography combines scrubbed travel, timed interaction/reveal envelopes and persistent simulation. Internal timeline units and wall-clock durations must be labeled separately.
3. **Confirmed:** Camera travel, object transforms and shader changes perform different jobs. Some apparent world rotation is camera orientation; some apparent illumination is linked material shading.
4. **Confirmed:** Cross-scene continuity often comes from compositing; cube/detail object identity persists perceptually across separate representations. Portal-to-chamber continuity is overlapping layers inside one scene.
5. **Confirmed:** Global UI survives the environmental compositor; perspective annotations belong to the world or are deliberately screen positioned. All visible text should not be grouped as orthographic overlay.
6. **Confirmed:** Finale shape selection is click/key/swipe driven. Hover acknowledges attention without selecting the next volume.
7. **Confirmed:** Input velocity is a filtered activity envelope, not raw input speed or all-camera speed. Portal impacts are authored progress cues; the active seam slope is fixed.
8. **Confirmed:** Preparation, interaction readiness and complete visual settling are distinct. Gates can unlock before authored tails finish.
9. **Strongly inferred:** The most useful cinematic principles are staged readability, attention continuity, material feedback, bounded disturbance and deliberate recovery to a composed state.
10. **Speculative:** Audio's perceived contribution remains unverified; it must not become a confident explanation in the consolidated reference.

Keep Pass 1's verified technical evidence available, correct its interaction claims, and let the consolidated narrative be organized around what the viewer experiences and what controls that experience.
