# Igloo — final reference

**Desktop experience · evidence archived 3 October 2026 · reference for collaboration with Astra 6**

This document explains Igloo's interaction grammar, choreography and relevant rendering mechanisms. It consolidates the retained investigations into resolved conclusions. It is reference material for an original design directed by the user, not a Jarvis redesign or implementation plan.

**Evidence discipline:** **Confirmed** means verified in archived production code, captured runtime state or inspected images; source verification does not guarantee a runtime outcome. **Strongly inferred** identifies an interpretation supported by those mechanisms and observations, without experimental proof of its perceptual effect. **Speculative / Unknown** identifies unresolved explanations or untested behavior. Mechanism descriptions below are **Confirmed** unless qualified; explanations of why they matter and transferable principles are **Strongly inferred**.

Scope is the inspected desktop build. Some retained compositions were reached by directly setting logical progress: they establish what a phase contains, not its natural input trajectory or duration. Screenshots are not a continuous motion trace. No new forensic pass was performed for this synthesis.

## 1. Executive summary — what fundamentally makes Igloo work

Igloo combines **continuous movement with authored opportunities to stop, recognize and inspect**. The viewer can drive travel, while the application shapes arrival, selectively completes movement and stages information on separate clocks. A resting composition retains subtle life without requiring continued navigation.

Its cinematic quality appears to come from five cooperating decisions:

- **Composed destinations:** portfolio objects center themselves; the portal passage can complete toward a finale; hero interior travel remains free.
- **Overlapping staging:** structure, substance, camera and information arrive at different moments, with the next subject becoming available before the previous presentation disappears.
- **Continuity of attention:** recognizable objects, bright focal regions, framing and global controls bridge changes in representation.
- **Material feedback:** input affects fragments, surface history and particle state, so response belongs to the thing receiving attention.
- **Bounded disturbance and recovery:** distortion, noise and extra movement subside as recognition or reading becomes important.

These are **Strongly inferred** explanations of polish, not an experimentally established ranking. WebGL makes Igloo's particular expression possible; an all-WebGL interface is not the transferable requirement.

## 2. Mental model of the experience

The main journey follows one continuous, cyclic **logical progress coordinate**. The browser document stays viewport-height and native scroll remains stationary. Three main rendered environments cover the landscape/hero, portfolio enclosures, and portal/chamber/finale. Project detail branches into a separate presentation and returns to the selected portfolio context.

Think of the experience as **travel → presentation → optional inspection → release**, repeated across different scenes. These are interpretive roles, not source-code classes. Travel may be user-driven or completed by inactivity behavior; presentation stabilizes attention; inspection reallocates the frame toward readable detail; release restores context or carries the journey onward.

Two distinctions are essential:

- A **continuous coordinate** does not imply that every position is an equally intended resting composition.
- A **continuous-looking experience** does not imply one continuous 3D world or one persistent mesh. Separate rendered worlds and related object representations can preserve perceptual identity.

## 3. Interaction and scroll architecture

Wheel and vertical arrow input change a target. Two frame-rate-adjusted smoothing stages bring displayed progress toward it. Target displacement is bounded, so a very large input can discard excess requested movement. The system wraps progress to form a loop.

Adjacent environments overlap over an interval. During that interval both scene outputs can render, each with its own camera, and a shader mixes their images. Within the portfolio environment, movement between the three objects instead transports the camera through the same scene.

After roughly **1.4 seconds of unchanged target**, the controller requests boundary resolution or scene-specific settling. This is not a universal snap rule. New main-scroll input can interrupt centering. Detail mode assigns wheel input to its own text-scroll controller rather than the main journey.

The controller's “velocity” is an unsigned, filtered activity envelope accumulated through its smoothing path. It is neither raw wheel speed nor a measure of all camera movement. Automatic centering can move the view while that value is zero. Cube lens response uses it; portal impact cues use authored progress phases. The active main-scene seam slope is fixed, not velocity-driven.

Evidence: [controller and scene source extracts](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/source-snippets.json), S01/S07/S12/S22; [recorded state index](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/probe-summary.json).

## 4. Scene-by-scene choreography

### Loading and arrival

**What happens:** a gray field carries an ASCII loader. Asset/upload readiness leads into an automatic construction scene: outline and cage establish spatial structure, solid fragments and terrain appear, and the earlier representations dissolve. The camera descends from a high arrival view while environment and UI reveals continue independently. No wheel input is required.

**Why it appears important:** the silhouette promises the later object; matching location lets solidity feel earned. The environment develops around the subject instead of presenting a completed image all at once. This is overlapping representation, not a verified outline-to-solid geometry morph.

### Hero

**What happens:** the igloo, foreground and mountains form a stable composition. Manifesto and global identity balance the upper frame. Time animation, filtered pointer response, fragment displacement and modest camera motion keep it alive. Wheel travel changes camera position and target on different envelopes while the manifesto initially looks screen anchored.

The early scroll-driven fragmentation factor **decreases** as progress advances; pointer influence is separate. Forward travel does not monotonically explode the igloo. Interior hero stops can remain where smoothing ends.

**Why it appears important:** a recognizable assembly can tolerate local disturbance without losing identity. Camera movement and responsive material provide depth while the overall composition remains available to attention.

### Hero → portfolio

**What happens:** two independent scene images overlap. A textured diagonal wash, displaced sampling and chromatic fringes obscure outgoing terrain as the portfolio environment enters. The manifesto belongs to the outgoing scene and can be distorted; global logo and sound controls are drawn above this environmental transition.

**Why it appears important:** atmosphere and stable controls connect the worlds while the seam masks their replacement. There is no evidence that landscape geometry becomes an enclosure. Inactivity in the overlap resolves toward a composition rather than indefinitely holding an arbitrary blend.

### Portfolio objects

**What happens:** Pudgy Penguins, Overpass and Abstract occupy three authored stops in one vertically arranged environment. Camera position and target travel together; distance-related object rotation relaxes toward the centered pose. At each stop, a refractive enclosure frames a recognizable inner object, title, connector and explore prompt. Between stops, the frame becomes sparse atmosphere as one enclosure leaves and another arrives.

Labels enter a proximity window, then complete timed connector/glyph/unscrambling reveals. They do not simply scrub every letter with wheel movement. Inactivity selects the nearest object. Pointer movement writes surface history into the enclosure material.

**Why it appears important:** reduced density during transit creates a pause between presentations. The centered object earns information; the labels become readable after the scene establishes their subject. The cost is temporarily limited actionable content.

### Project detail → return to selected object

**What happens:** clicking an eligible enclosure opens its matching route and stops main wheel travel. If necessary, centering overlaps opening. The outgoing camera pushes inward, extra rotation/pointer influence is suppressed, and a frost/displacement blend reveals a darker detail environment. A separate representation of the selected object remains behind the copy.

Text begins its own reveal while the incoming camera still approaches. Logo/sound persist, Close becomes available, and portfolio annotations leave. Detail wheel input belongs to a clamped, smoothed text group with edge fading. Overflow-scroll capability is source-confirmed; the retained viewport did not require it.

Closing hides copy, reverses the blend and restores the selected enclosure's camera and response. Abstract open/close returned to Abstract, not the first object. Main input can resume before every recovery tail ends.

**Why it appears important:** subject identity carries the viewer from tactile presentation to explanation. Suppressing competing movement favors reading; returning to the selected context preserves orientation. Identity survives across separate meshes and materials, not a proven shared object instance.

### Portfolio → portal traversal

**What happens:** another cross-scene composite replaces the departing enclosure with broken rings. Inside the portal environment, camera descent, target changes, depth travel, lens change and rotation of the camera's up vector create traversal. Rings also rotate, but camera choreography explains much of the apparent world motion.

Distortion and glare pulse near authored ring crossings. These are progress-linked events, not a generic effect of high input velocity. There is no authored rest at each ring. Once sufficiently inside this environment, inactivity carries progress toward the finale; renewed scrolling can interrupt.

**Why it appears important:** localized crossings give the passage accents, while a destination prevents the dramatic transit from becoming an indefinite resting state.

### Portal → particle chamber

**What happens:** this change occurs within the same environment, without another main-scene seam. Particles become visible while traversal layers still exist. Floor, forcefield, cylindrical text, smoke and ambient particles join on staggered phases; rings/tunnel/snow recede. Initial brightness and formation noise diminish as a particle-built subject becomes recognizable and the camera turns toward frontal presentation.

**Why it appears important:** the central disturbance becomes the next subject, and circular framing carries attention into the chamber. Overlap supplies continuity; there is no evidence that portal fragments literally become particles.

### Finale

**What happens:** a particle subject rests between illuminated circular forms. Arrows and the selected Visit link are enabled in a limited progress window around this usable presentation. Pointer input perturbs the simulated particles.

**Selection is explicit:** Left/Right keys, half-screen clicks or a qualified horizontal swipe change the selected target. Visit hover refreshes its label; arrow hover blinks. Hover does not select a new shape. Visit click opens the current destination and suppresses carousel advancement. The retained runtime exercised keyboard selection; swipe is source-confirmed, not mobile-tested.

Selection replaces the attraction volume while retaining particle positions and velocities. Extra noise rises briefly and decays; floor response runs longer; arrows and link text refresh separately. This is discrete choice resolved through continuous simulated state.

**Why it appears important:** a short disturbance signals change, then recovery restores recognition. The subject feels like one responsive material reforming rather than disconnected objects swapping.

### Loop return

**What happens:** continued vertical travel removes finale-specific UI, overlaps the finale environment with the hero, and wraps progress. Positive traversal back to the igloo was captured. Global identity persists through environmental replacement.

**Limit:** the exact perceptual seamlessness of the wrap, full reverse traversal and negative wrap remain unverified.

Selected visual evidence: [arrival](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/desktop-intro-contact.png), [sparse portfolio transit](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/between-cubes.png), [detail](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/deep-detail-ready.png), [chamber emergence](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/entry-p0-55.png), [finale](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/entry-p0-76.png).

## 5. Transition anatomy

Igloo uses four distinct mechanisms:

1. **Image compositing:** adjacent environments render separately, then a textured shader seam mixes their outputs.
2. **Spatial travel:** portfolio stops and portal crossings use camera/object choreography inside one environment.
3. **Timed inspection:** project entry coordinates centering, representation replacement, camera approach, reduced response and readable copy.
4. **Stateful reformation:** finale selection changes a simulation target while retaining material state.

Their shared grammar is **Strongly inferred**: establish an anchor, disturb a bounded region, introduce the next focus, then recover a usable composition. Continuity can be perceptual rather than geometric.

The main seam combines a texture-defined cut, displacement, slope distortion, noise and chromatic sampling. It supplies an expressive veil over replacement. It is not the explanation for every transition, and it can temporarily obscure recognition. Duration and intensity belong to the purpose of a transition, not a universal decorative recipe.

## 6. Camera / object / material / UI coordination

Camera establishes viewpoint; geometry provides local response; material/shader changes express disturbance and conceal replacement; UI decides when information is available. Their curves and spatial responsibilities differ.

In the hero, fragment transforms couple with authored assembled/displaced shading and emission, including an approximate interaction glow on the ground. In the portfolio, camera transport cooperates with enclosure pose, refraction and surface history. Detail reduces extra motion while copy arrives. Portal camera orientation cooperates with crossing-local effects; chamber emergence overlaps those layers rather than waiting for a clean cut.

Text is not one uniform overlay:

- **Global UI:** logo, sound, scroll hint and Close occupy an orthographic layer. Persistence is selective; contextual controls have their own visibility rules.
- **Hero manifesto:** perspective-scene text positioned to appear screen anchored.
- **Portfolio annotations:** camera-facing groups attached to transformed enclosure anchors.
- **Detail copy:** an orthographic text group rendered after the environmental composite.
- **Finale controls:** Visit belongs to the portal/finale scene; arrows attach to the particle group.

Global UI is drawn **after environmental compositing but before global bloom and antialiasing**. It can stay clearer through a scene seam while sharing the frame's output treatment. Scene-local annotations are already inside the scene images and behave differently.

Evidence: source extracts S09–S11/S20–S22 and retained [cube draw sequence](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/spector-cube1-draws.json).

## 7. Resting states, settling and user agency

Rest is a stable focus, not a frozen frame. Inactivity policy depends on context:

- **Hero interior:** no obligatory snap to the intro composition. Boundary return can recover that composition, but interior stops remain free.
- **Environment overlap:** resolve the boundary toward an authored presentation.
- **Portfolio:** center the nearest object over a distance-dependent tween.
- **Portal/finale interior:** after the early threshold, move toward the finale rather than the nearest ring; from beyond the destination, this can move backward.
- **Detail:** retain the selected context and give wheel control to copy.

Cube centering is roughly 1.6–2.4 seconds in source; portal completion can span 2–20 seconds. These describe Igloo's behavior, not recommended tuning. Long automatic travel can be consequential to user agency.

Navigation gates prevent conflicting primary actions, not all animation overlap. During detail opening, the route-navigation gate unlocks before the camera tail completes; main-world wheel travel remains disabled throughout detail. During closing, main travel resumes before blend and recovery tails finish. Readiness for another action and complete visual rest are deliberately distinct.

## 8. Continuity and attention management

The strongest recurring anchor is **something recognizable surviving a change of context**: scaffold silhouette into solid hero, selected object into detail, bright central disturbance into particle subject, global identity across scene replacement.

Matching atmosphere, framing and focal contrast reinforce those bridges. Their contribution is **Strongly inferred**; literal shared geometry is often absent. A cold palette and circular motifs support this particular work but are not the principle.

Information density follows the journey. Sparse transit reduces competing detail; centered portfolio subjects gain annotations; inspection adds sustained copy while extra motion recedes; finale controls appear only around the presentation window. This makes readability a choreographed state, with a tradeoff: transit is less useful for immediate task access.

## 9. Motion and timing principles

A shared frame clock updates systems that retain different sources of time:

- **Progress-scrubbed paths:** camera transport, scene-local visibility and crossing effects map to logical position. An internal timeline's “seconds” are phase coordinates when its progress is externally driven, not guaranteed wall-clock durations.
- **Timed envelopes:** arrival, centering, detail opening/closing, label reveals and selection feedback run on clock time once triggered.
- **Ambient and simulation time:** subtle object motion, pointer filtering, surface history and particles can continue at unchanged progress.

Eligibility connects the clocks. A subject enters a useful region, which triggers a timed label reveal; a selection changes a target, which the ongoing simulation resolves. These systems cooperate without all moving together.

Arrival demonstrates overlap: solid geometry appears before scaffold fade finishes, camera approach continues after UI begins, and interaction becomes available before the longest reveal tails end. Finale selection demonstrates different decay lengths: extra noise recedes over about half a second while floor response continues for three seconds. Those timings explain the separation of roles, not values to copy.

## 10. Interaction and material feedback

Feedback is expressed through the subject's behavior:

- **Hero:** pointer proximity drives filtered fragment displacement/rotation with linked shading and emission.
- **Enclosures:** ray-hit UV coordinates write into a history texture used by the frost/material response. This remembers movement beyond an instantaneous hover frame; it is not established as physical ice growth.
- **Finale:** pointer-derived fluid input disturbs particles; selection changes attraction while retaining simulated state.
- **Text and controls:** short reveal, scramble or blink envelopes acknowledge attention separately from navigation.

The main UI uses distance-field glyph meshes and shader-driven atlas scrambling. Typography participates in staging and feedback rather than behaving as static captions. Exact font choice, glitches and shader text are Igloo's expression, not requirements for another product.

Audio cues and progress/interaction-linked gains are confirmed in source. In the retained build, a successful first click/key gesture resumes the audio context and automatically unmutes it; sound is not activated exclusively by the sound button. **Unknown:** audible mix, latency and perceptual contribution. Emitted events and downloaded audio do not prove what was heard.

## 11. Loading and presentation readiness

Igloo separates four milestones: **resources available → rendering/simulation prepared → interaction enabled → visual settling complete**.

Scene setup awaits upload promises, compiles shaders, initializes textures and performs preparation draws, including otherwise hidden materials. Particle initialization advances its simulation before enabling visibility. That preconditioning prepares the shape; it is not a measured one-second visible delay.

The loader outro and automatic arrival are presentation events with their own envelopes. The intro resolves around five seconds even though camera/environment tails continue. The startup compositor is replaced by the main transition compositor after intro readiness, not on the first scroll.

Preparation coverage has a limit: two main-plane upload calls are initiated without being awaited. The evidence therefore supports a deliberate warm-up strategy, not proof that every pass is ready before exposure or that first appearances never hitch. Adaptive pixel resolution and visibility-driven rendering likewise establish mechanisms, not hardware-independent smoothness.

Evidence: source extracts S02/S03/S16/S23 and [archived bundle excerpts](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/bundle-snippets.json), B08/B09/B22.

## 12. High-value transferable principles

These are **Strongly inferred principles**, available to an original design in any appropriate medium:

1. **Design arrival and rest together.** Igloo's centering policies make destinations usable; the transferable decision is when recovery should assist and when it should leave the user's position alone.
2. **Separate position, intent and response.** Continuous travel can coexist with selected subjects, timed reveals and ongoing material state. Each can answer a different user action.
3. **Stage readability.** Proximity-triggered labels and calmer detail presentations show why information need not move in lockstep with navigation.
4. **Preserve attention through replacement.** Object identity, framing or a stable control can bridge a change even when its representation is replaced.
5. **Give disturbance a recovery phase.** Effects should resolve toward recognition or action, with different subsystems allowed to finish at different times.
6. **Let feedback belong to its target.** Local material response can make input consequential; hover acknowledgement, selection and activation remain distinct intents.
7. **Treat density as part of pacing.** Igloo contrasts sparse travel with composed presentation. Whether that tradeoff is useful depends on the product's purpose.
8. **Prepare the state that will be shown.** Resource loading, technical preparation, permission to interact and visual completion are different concerns.

These principles inform judgment. They do not determine another product's appearance, renderer or interaction policy.

## 13. Igloo-specific mechanisms that should not be generalized

Igloo's branding, imagery, assets, ice aesthetic, typography and audio identity belong to Igloo. Its landscape, three enclosures, portals, particle subjects and looping presentation are authored content, not a reusable product structure.

Do not treat automatic portal completion, long centering, sparse transit, wide click regions or infinite travel as universal usability improvements. Do not carry over exact scroll constants, coordinate lengths, lens values, timings, shader recipes, particle counts or library choices.

All-WebGL text and custom hit testing give this work expressive control, but the retained accessibility tree exposed an unnamed canvas with little of the visible interface. That observation is not a full accessibility verdict; it is also no basis for assuming this architecture serves readable, task-heavy interfaces. **Nothing in this reference implies that Jarvis should become an all-WebGL application.**

## 14. Important technical architecture — only where relevant

The confirmed core is **Three.js/WebGL2 with a small Svelte shell, GSAP-driven frame/timeline control and a custom progress controller**. Active ScrollTrigger or Lenis control was not established. Three main scene outputs, a detail output and an orthographic UI role cooperate in one presentation pipeline.

The useful frame order is: **visible scene rendering and local effects → environmental/detail composite → global UI/detail copy → global bloom → antialiasing/output**. This explains why persistent controls can survive scene-local distortion while sharing final visual treatment.

Batched fragment transforms make the hero genuinely responsive. Custom transmission renders enclosure contents/backfaces for refractive shell sampling. Ping-pong textures retain frost and particle state; volume targets guide particle reformation. These mechanisms explain persistence and material behavior better than a list of effect names.

Worker decoding, cached loads, shader/texture preparation, hidden-scene skipping and adaptive resolution manage presentation cost. The static/dynamic lighting split remains incompletely known; bright regions should not automatically be described as moving physical lights. Active depth-of-field processing was not established.

Library versions, framebuffer formats, binary codecs, exact particle counts and capture command totals are omitted because they do not explain the interaction grammar. They remain in the [technical evidence inventory](D:/Cursor/Jarvis-UI-UX/IGLOO-FORENSICS-PASS-1.md) and [GPU capture summary](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/spector-summary.json). For resolved interaction mechanisms, use [source extracts](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-2/evidence/source-snippets.json), S01–S24, alongside the recorded state index. Source offsets apply only to the archived build.

## 15. Remaining uncertainties

**Speculative / Unknown:**

- Audible result and sound's contribution to cohesion; no independent listening or latency measurement established them.
- Complete reverse traversal, negative wrap and perceptual seamlessness of the loop.
- Rapid interruption during detail return, browser history/deep-link recovery and long-copy overflow behavior.
- Natural wall-clock transition profiles, sustained performance across hardware and the measured benefit of warm-up. Direct progress placements and sparse captures do not establish these.
- Full accessibility, reduced-motion, failed-resource/context-loss and fallback behavior; cross-browser and mobile choreography are outside the confirmed desktop coverage.
- Exact authored-versus-live lighting allocation and the causal contribution of individual effects to polish.

These limits qualify the reference; they are not a request for another investigation. The verified interaction model is sufficient to inform design judgment without filling the gaps with invented claims.

## 16. Astra reference summary

Before collaborating with the user, internalize these ideas:

- **Igloo is continuous in progress, selective in destinations.** Hero rest, cube centering, boundary resolution and portal completion follow different policies.
- **Travel, presentation and inspection have different demands.** Information becomes readable as the scene earns focus; extra movement recedes for explanation.
- **Several clocks cooperate.** Scrubbed paths, timed reveals and persistent simulation share state without sharing one universal timeline.
- **Continuity is often perceptual.** A recognizable subject, bright focal region, framing or stable UI can survive representation replacement.
- **Transitions overlap and recover.** Incoming elements can become recognizable before outgoing layers disappear; disturbance is bounded and settling completes the event.
- **Feedback, selection and activation are distinct.** Material response acknowledges input; explicit choice changes state; activation opens its destination.
- **Preparation precedes presentation, but readiness has stages.** Interaction can resume while remaining visual tails continue; loading completion does not mean every composition has settled.

Use these ideas to understand Igloo's polish, not to reproduce its surfaces or impose its interaction architecture. **The user remains the creative director.** This reference supplies evidence and a vocabulary for discussing an original design; it prescribes neither Jarvis's appearance nor its implementation.
