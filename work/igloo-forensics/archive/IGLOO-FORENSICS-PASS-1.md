# Igloo — forensic analysis, pass 1

**Target:** <https://igloo.inc>, redirecting to <https://www.igloo.inc/>.  
**Inspection date:** 3 October 2026, Asia/Calcutta.  
**Scope:** the desktop browser experience. Mobile layout details are excluded following the owner's scope correction. This is technical reference material, not a redesign, implementation plan, or recommendation for Jarvis.

## How to read this report

- **Confirmed:** directly observed in the inspection browser, verified in the downloaded production code/asset, or explicitly documented by an identified creator. Each claim specifies which kind of confirmation applies. Source-confirmed code is not automatically a measured runtime outcome.
- **Strongly inferred:** several independent observations support the conclusion, but the exact implementation or provenance is not fully established.
- **Speculative:** plausible but unverified. Speculation is confined to explicitly labeled hypotheses and unknowns; it is not used to identify the stack.

Evidence is retained under [work/igloo-forensics-pass-1/evidence](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence). The inspection scripts and tooling are isolated under `work/igloo-forensics-pass-1/`; application source and dependencies were not changed. A future agent should start with this report, the evidence index in section 13, and the exact-offset [bundle snippets](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/bundle-snippets.json).

The primary browser runs use installed Microsoft Edge controlled by Playwright and Chrome DevTools Protocol (CDP), on Windows, with a 1440 × 900 CSS-pixel viewport and DPR 1. The graphics context reports Intel UHD Graphics 630 through ANGLE/Direct3D11. This is hardware rendering in the observed context, not a SwiftShader result. Headless automation, screenshots, instrumentation and video recording affect timing; observations are not a performance benchmark. Desktop resize checks use 1920 × 1080 and 1024 × 768 where noted.

**Tooling status:** Browser/DOM/shadow-root instrumentation, CDP network/accessibility/performance inspection, HAR, screenshots/video, public bundle/binary inspection, web research and **direct Spector.js GPU capture** were used. The [official Spector.js MCP server](https://github.com/BabylonJS/Spector.js/tree/master/mcp) source was downloaded into isolated tooling, but dependency installation failed in the sandbox and the escalated install approval was canceled. It was **not built or connected; no MCP tool calls were made**. The five GPU captures below use Spector directly, not MCP. No global Codex configuration was changed. [spector-setup.json](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/spector-setup.json) records the limitation. The local MCP client/preload scripts are prepared but unexecuted.

## 1. Executive technical overview

**Confirmed — production source and browser:** Igloo is principally a custom real-time WebGL2 application, with Three.js rendering and a small Svelte shell. It does not construct the visible experience as a long sequence of ordinary DOM sections. The browser document remains viewport-height and `window.scrollY` stays at zero while the scene changes.

**Confirmed — production source:** Three.js r165, GSAP 3.12.5 and `postprocessing` 6.35.5 are embedded in the live 3D bundle. GSAP supplies the frame clock, scripted envelopes and scroll-scrubbed timelines. A custom controller owns wheel input, smoothing, velocity, idle centering, section overlap and cyclic progress. Finding the word `ScrollTrigger` in GSAP's optional bridge is insufficient evidence that ScrollTrigger powers the site.

**Confirmed — production source:** Three primary scene composers—`igloo`, `cubes`, and `entry`—feed a fullscreen shader compositor. An additional project-detail scene and an orthographic UI scene bring the total to five scene roles. The architecture combines authored geometry/textures with real-time camera movement, batched fragment transforms, GPU simulations, custom transmission/frost shaders, scene color correction, bloom and SMAA.

**Confirmed — browser and source:** Text, logo and controls belong to the WebGL scene. The actual canvas is in a closed shadow root. An empty `body.innerText` and zero canvases from normal document selectors therefore do not mean the scene is missing. Retaining the shadow-root reference during creation reveals a canvas carrying `data-engine="three.js r165"`.

**Strongly inferred — synthesis of verified mechanisms:** The polish comes from coordinated control of the entire frame: separate animation envelopes for geometry, light-like emissions, camera, typography, transition distortion and audio; deliberate idle destinations; shader/texture preparation before introduction; and rendering work constrained to visible states. These mechanisms are verified individually. Their relative contribution to perceived polish has not been experimentally isolated.

## 2. Detected technology stack

| Technology | Confidence | Direct evidence and limits |
|---|---|---|
| WebGL2 | **Confirmed** | Intercepted context creation and queried live GL version; startup checks require it. No observed WebGPU renderer. |
| Three.js r165 | **Confirmed** | Runtime canvas engine attribute; bundle revision constant `165`; renderer and material implementation. |
| Svelte | **Confirmed** | Compiled component lifecycle, fragment updates, `$destroy`, `$on`, loader transitions, and App3D imports of the shared runtime. Exact Svelte version unknown. |
| GSAP 3.12.5 | **Confirmed** | Vendored version; application ticker, `.to()`, timelines, custom eases and `.progress()` calls. |
| `postprocessing` 6.35.5 | **Confirmed** | Bundle license/version header; active composer, bloom and SMAA call sites. |
| Vite build tooling | **Strongly inferred** | Modulepreload helper, `vite:preloadError`, dynamic import helper and hashed chunks; creator also names Vite. Exact version/build configuration unknown. |
| BVH-accelerated raycasting / `three-mesh-bvh` family | **Strongly inferred** | Active geometry bounds-tree construction and accelerated/first-hit raycast path. Creator lists “three-mesh-bhv,” apparently a transposition. Exact package/version not identified. |
| Draco | **Confirmed** | `.drc` requests, decoder wrapper and WASM requests, decoding/caching path. |
| KTX2 / Basis texture processing | **Confirmed** | KTX2 resources and Basis transcoder JS/WASM requests; texture loader capability selection. Not every KTX2 file is Basis-compressed. |
| Web Workers and Web Audio | **Confirmed** | Font/bitmap/EXR/audio workers and actual resource requests; decoded PCM becomes Web Audio buffers. |
| ScrollTrigger / Lenis / React / React Three Fiber | **Not established** | No active application call sites found for these systems. React in inspection tooling must not be confused with Igloo's stack. |

**Confirmed — creator-reported historical authoring, not inferred from browser filenames:** Abeto's [2024 case study](https://www.awwwards.com/igloo-inc-case-study.html) credits Abeto/Bureaux and names Houdini/Blender, Figma/Photoshop/Affinity Photo and DaVinci Resolve. It describes constrained procedural crystal modeling, custom VDB export, real-time intro shaders, SDF-based UI glitches, staged texture loading and shader compilation. Current runtime evidence independently supports the 3D/shader/SDF/volume/loading architecture, but does not reconstruct the artists' original project files or prove every current asset followed that workflow.

## 3. Page / scene architecture

### 3.1 Document and application shell

**Confirmed — fetched HTML:** The initial response is only 1,410 decoded bytes. It contains metadata, favicons and one module script; the body is initially empty. The bootstrap creates `#app`, displays a DOM ASCII loader, imports `App3D-f554a111.js`, waits for readiness, then removes the loader after its outro.

**Confirmed — browser:** After loading, the ordinary DOM is essentially `#app > #webgl > div`, with a closed shadow root holding the canvas. There are no conventional visible DOM headings, buttons or project cards in the inspected main state. The Chrome accessibility tree exposes an unnamed Canvas and generic containers, not the visible manifesto, sound control or project labels. This is an observation of the inspected states, not a comprehensive accessibility audit.

### 3.2 Scene roles

| Scene role | Confidence | Content and responsibility |
|---|---|---|
| `igloo` | **Confirmed** | Snowy landscape, fragmented igloo, outline/cage introduction, snow/numeric points, shared UI/manifesto. |
| `cubes` | **Confirmed** | Three vertically sequenced ice enclosures containing portfolio objects; custom refraction, frost interaction and project hit targets. |
| `entry` | **Confirmed** | Portal/ring traversal, camera inversion and particle/contact finale. Internal name `entry` refers to this later experience; it is not proof that it is the first page section. |
| detail | **Confirmed** | Selected project object, distinct camera and copy group, scrolling MSDF text and external links. |
| UI | **Confirmed** | Orthographic overlay: logo, scroll hint, sound state, close control and supporting text. |

**Confirmed — source:** Root construction creates all scene instances and awaits their upload promises. Logical section lengths are 2.35, 3 and 5.5; total loop length is 10.85 units. They are animation coordinates, not HTML heights or meters. The three cubes currently correspond to Pudgy Penguins, Overpass and Abstract.

**Confirmed — source:** Routes include `/` and `/portfolio/:project`, with hashes `pudgy-penguins`, `overpass` and `abstract`. Route transitions gate input to avoid overlapping choreography. Direct navigation has a special initialization path; deep-link behavior must be tested separately from clicking an already visible cube.

## 4. Scroll and transition system

### 4.1 Input and progress

**Confirmed — browser:** Wheel input changes the image while native scroll remains zero and document height remains 900 at the 1440 × 900 viewport. ArrowDown is registered and exercised. The canvas owns non-passive wheel input; `html/body` disable overflow, and the canvas disables native touch actions and text selection.

**Confirmed — source:** The controller tracks a raw target `targetY2`, an intermediate target `targetY1`, and displayed `y`. Desktop wheel delta is scaled by **0.00075**. Arrow input contributes ±150 before that scale, or ±0.1125 logical units. Firefox line-mode wheels receive a separate normalization; Chromium pixel-mode wheels are used directly.

**Confirmed — source:** The first smoothing stage uses FPS-adjusted interpolation with coefficient **0.075** and a bounded step; the second uses **0.15**. The raw target is constrained relative to displayed progress by **750 × 0.00075 = 0.5625** logical units. A very large single wheel event can therefore lose excess requested motion. Scroll velocity accumulates movement, decays with FPS-adjusted friction **0.98**, and is clamped to [0,1]. These are per-frame control parameters, not time durations.

**Confirmed — source:** Progress wraps modulo **10.85**, with negative values corrected. A section's local progress is `(view bottom − section top)/(section height + 1)`. The controller identifies overlapping scenes and renders one or two scene composers as needed. Apparent section boundaries are shader blends between scene outputs rather than browser elements passing a viewport threshold.

### 4.2 Idle centering

**Confirmed — source and desktop experiment:** After **1.4 seconds** without target changes, the controller selects an idle destination. General boundary centering uses a two-second tween; cubes use roughly **1.6–2.4 seconds**; late `entry` centering can take **2–20 seconds**, depending on distance. Small wheel inputs spaced far apart repeatedly returned the image toward the hero. The captured behavior sequence must not be interpreted as a fixed linear scroll timeline.

Useful source-derived settled positions, not browser scroll offsets:

- Hero intro center: approximately **0.65825**.
- Cube centers: **2.35**, **3.35**, **4.35**.
- Particle finale center: approximately **9.29**.

### 4.3 Transition construction

**Confirmed — source, visually corroborated:** A fullscreen triangle samples scene render textures. A transition data texture supplies red-channel ice cutting, green-channel technical displacement and blue-channel slope distortion. The shader applies aspect correction, parallax, displaced sampling, blue-noise modulation and a five-iteration chromatic-aberration function. Screenshots show a frost-like diagonal wash and RGB fringes through the scene seam.

**Confirmed — source limitation:** An old velocity-dependent diagonal-cut expression is commented out. The active slope is fixed at `−0.2 × aspect`. Although a progress-velocity uniform is updated, that is not evidence that the active seam angle follows velocity.

**Confirmed — source:** Project detail transitions use separate envelopes: primary detail progress rises over **1.25 s / power3.in**, and secondary progress over **1.25 s / sine.out**, delayed **0.75 s**. The composite begins mixing the detail texture after primary progress reaches approximately 0.4, with frost/displacement/chromatic effects. Close uses different reverse envelopes, including a 0.6-second secondary reset.

## 5. WebGL rendering architecture

### 5.1 Context and canvas

**Confirmed — runtime:** The principal canvas is **1440 × 900** drawing-buffer pixels at the tested DPR 1. Context attributes report `alpha:true`, `antialias:false`, `depth:false`, `stencil:false`, `premultipliedAlpha:true`, `preserveDrawingBuffer:false`. A separate 300 × 150 WebGL2 context appears during capability probing; it is not a second visible scene canvas.

**Confirmed — source/runtime reconciliation:** The application's wrapper requests alpha false, but the bundled Three.js context-creation code requests alpha true. The live queried attribute is the authoritative context result. Likewise, default framebuffer depth false does not imply the offscreen scene targets have no depth attachments.

**Confirmed — runtime:** Reported GL version is WebGL2/OpenGL ES 3.0 Chromium. Available extensions include floating-point color buffers, float-linear filtering, parallel shader compilation, S3TC/BPTC compression, timer queries, anisotropic filtering and multidraw. Maximum texture size is 16,384. Extension availability is not proof that every extension is used by an active pass.

### 5.2 Frame dataflow

**Confirmed — application source:**

```text
Input + GSAP ticker
    -> smoothed scene progress / pointer / clocks / uniforms
    -> visible igloo/cubes/entry offscreen scene rendering
       (cube scene also prepares a transmission/refraction texture)
    -> scene-local correction / LUT / effect shader
    -> fullscreen triangle: scene A/B seam + detail blend
    -> orthographic WebGL UI
    -> global bloom
    -> high-quality SMAA / output encoding
    -> canvas
```

**Confirmed — source and GPU capture:** The main composer sorts the final gamma/SMAA path last. Captured commands show the scene composite and UI writing the same main target before luminance extraction, six bloom downsample levels, five upsample levels, bloom combine, SMAA edges/weights and the final screen effect. Thus the UI is included before global bloom. The startup hero frame uses a simpler `tScene/uIntro/uColor` compositor; after intro readiness the root replaces it with the full scene/detail transition material. The first scroll does not trigger that replacement.

**Confirmed — source:** Shared uniforms/UBOs carry time, frame-delta adjustment, render resolution and UI resolution. Scenes use their own camera objects and shared input state. The fullscreen primitive is an oversized triangle, avoiding the diagonal seam and extra edge of a two-triangle fullscreen quad.

### 5.3 Geometry and simulation

**Confirmed — source:** The igloo uses batched geometry, per-piece matrices and an options data texture. Each piece receives filtered displacement/rotation from pointer proximity, time and scroll progression. Matrix updates and shader batch IDs support actual moving fragments; this is not a prerecorded igloo video.

**Confirmed — source:** Cube shells use a custom `MeshPhysicalMaterial` subclass with altered transmission chunks and an auxiliary mipmapped render target. The scene renders inner objects and backfaces for transmission, then renders front-facing shells using that result. App construction chooses **three custom transmission samples**; the helper's default sample count is not the active value. Cube roughness, refraction and interaction are linked through custom shader uniforms.

**Confirmed — source:** The finale draws **150,000 GPU particles**. Ping-pong targets retain positions/velocities; a 3D signed-distance/gradient texture guides attraction to target shapes. Curl/bitangent noise and a fluid-velocity input drive motion. The code also defines a 128-resolution fluid system, two pressure iterations and zero curl-strength in this configuration. This is evidence of the bundled application's GPU system, not an identified external fluid-simulation package.

### 5.4 Spector.js capture findings

**Confirmed — direct Spector.js instrumentation:** Five actual WebGL frame captures were saved, covering hero arrival, the first cube, that cube after pointer motion, settled Pudgy Penguins detail and the particle finale. The uninstrumented baseline was collected separately. Captures expose compiled shader source, ANGLE-translated shader source, uniforms, draw state, framebuffer attachments and thumbnails.

| Captured state | GL commands | Draw commands | Active programs | Reported triangles | Reported points |
|---|---:|---:|---:|---:|---:|
| Hero arrival / intro still active | 469 | 48 | 29 | 117,213 | 257 |
| Pudgy Penguins cube | 450 | 38 | 25 | 74,160 | 18 |
| Cube after pointer/frost interaction | 453 | 38 | 25 | 74,160 | 18 |
| Settled project detail | 392 | 44 | 22 | 31,056 | 10,250 |
| Particle finale | 507 | 50 | 33 | 108,771 | 150,060 |

**Confirmed — capture semantics:** Draw counts include one `multiDrawElementsWEBGL` API command as one command, where present; that call may contain multiple subdraws. Primitive totals are Spector's analyzer output. Program counts are unique bound program IDs seen on draws. These single frames are not peak counts or a stable performance budget. All captured shader compile/link statuses were successful. A false validation-status flag is not by itself a failed link. Absence of captured `getError` results does not justify a universal “no GL errors” claim.

**Confirmed — live attachments:** Scene color targets use **RGBA16F**, often with **DEPTH_COMPONENT24** renderbuffers. The finale's particle compute draw has **two RGBA32F attachments at 388 × 388**; that grid holds 150,544 texels, while a separate point draw requests exactly **150,000 points**. Finale fluid targets include **128 × 128 RGBA16F**; the cube frost target is **512 × 512 RGBA16F**. Bloom runs from 720 × 450 through 23 × 15 and back up; SMAA intermediates include full-resolution **RGBA8** targets. These measurements establish active formats on this GPU instead of guessing from generic library defaults.

**Inspection caveat:** Normal document canvas enumeration misses the closed root. Late Spector injection also initially failed to detect frames. The successful direct run retains the closed root and injects the official Spector bundle before application startup using a browser-local response adapter; the remote site is unchanged. Spector instrumentation/readback adds substantial overhead. The hero sample is an arrival-phase frame with the intro compositor still active, so it is deliberately not labeled a settled-hero frame. Compact summaries and draw/shader extracts are in [spector-summary.json](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/spector-summary.json); raw captures are roughly 19–24 MB each.

**Confirmed — capture limitation:** The instrumented run logged `GL_INVALID_OPERATION` warnings for `glReadPixelsRobustANGLE` format/type combinations. The baseline run did not. **Strongly inferred:** these are Spector readback/thumbnail limitations on this rendering path; they are not established as a production-site defect. Treat attachment thumbnails and inspector error summaries cautiously while retaining the verified command/state/shader evidence. [deep-console.json](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/deep-console.json) records the warnings.

## 6. Animation system

### 6.1 Clocks and timelines

**Confirmed — source:** GSAP's ticker is the shared frame clock, emitting pre-render, render and post-render events. Defaults include `power2.inOut`, 0.6-second duration and automatic overwrite. Custom Bezier eases are registered for entry and igloo choreography.

**Confirmed — source:** Paused GSAP timelines are advanced with `.progress(scene.progress)`. A “14-second” segment inside such a timeline describes its internal mapping; it does not promise a fourteen-second wall-clock scroll transition. By contrast, the auto-playing intro, detail opening and idle-center tweens have real clock durations.

### 6.2 Intro choreography

**Confirmed — source, with loading/intro screenshots:**

| Envelope | Relative start / duration | Role |
|---|---|---|
| Outline materialization | 0 / 2.5 s | Establishes the object's technical silhouette. |
| Cage reveal | 0 / 4 s | Builds the surrounding structure. |
| Cage fade | 2.1 / 3 s | Overlaps the arrival of solid geometry. |
| Solid igloo materialization | 1.1 / 2.25 s | Introduces the filled fragments. |
| Landscape/mountain reveal | approximately 0.7–8.2 s overall | Extends the environment behind the object. |
| Camera intro blend | 2 / 5.5 s | Blends from high intro camera into the normal camera. |
| UI intro event | 4.5 s | Starts the interface's own reveal choreography. |

The scene's intro method resolves after five seconds even while some timeline tails continue. Asset-ready, loader disappearance, intro start and complete visual settling are distinct events. The DOM loader glyph fades over 250 ms, while its overlay fades over 750 ms.

### 6.3 Cameras and transformations

**Confirmed — source:** Hero camera starts with FOV 30 and a configured position near `(−14,4,14)`, targeting `(0,1,0)`. Intro moves it from a high position near `(−14,21,14)`. Pointer displacement, subtle shake and timeline paths are combined; object motion alone cannot explain the scene change.

**Confirmed — source:** Cube camera position and target translate vertically with section progress. Its active FOV is **45 − 5 × abs(scroll velocity)**, providing a modest velocity-dependent lens change. Detail entry also adjusts base-camera distance and suppresses extra rotation/pointer influence.

**Confirmed — source:** The portal camera changes vertical position, target, z travel, FOV from 22 toward 30 and the camera's up vector through π before blending toward the conventional orientation. Timed proximity pulses align the post shader with ring crossings. Some apparent whole-scene rotation is camera orientation, while rings and particles also have their own transforms.

**Confirmed — source:** Detail camera travels from z 4 toward z 2.5 over two seconds after a half-second delay. Selected project geometry keeps a small sinusoidal multi-axis rotation. The copy reveal is independently timed, so camera, object and text do not share one generic fade.

## 7. Shader and visual-effect observations

| Effect | Confidence / mechanism | What the evidence does not prove |
|---|---|---|
| Scene seam | **Confirmed:** multi-channel data texture, aspect-corrected diagonal cut, displacement, blue noise and RGB-separated samples. | Not a DOM mask or proven velocity-dependent seam angle. |
| Global bloom | **Confirmed:** application adds bloom with six mip/downsample levels. | Bright appearance alone does not measure HDR energy or exact GPU cost. |
| Antialiasing | **Confirmed:** main MSAA disabled; active high-quality SMAA path. | Not proof every auxiliary framebuffer has identical sampling settings. |
| Scene color grade | **Confirmed:** igloo/cube 3D LUTs, tetrahedral interpolation; igloo brightness gradient. | Does not establish a runtime color-grading editor. |
| Cube refraction | **Confirmed:** custom physical-material shader, mipmapped/bicubic transmission sampling, normal/roughness/environment data and chromatic variation. | Native Three transmission defaults are not the complete effect. |
| Pointer frost | **Confirmed:** UV hit from accelerated raycasting splats into 512 × 512 ping-pong history; updates gated to at least 0.015 s. | Texture history is not proof of a full physical ice-growth simulation. |
| Portal distortion | **Confirmed:** noise/angular distortion, square displacement, HSV adjustments and blue-noise glare gated by ring proximity. | No verified camera-attached lens-flare package. |
| Particle morphs | **Confirmed:** velocity/position compute targets + 3D gradient/SDF target texture + noise/fluid inputs. | Not CPU tweening 150,000 DOM elements; no proven external physics engine. |
| UI scramble | **Confirmed:** MSDF atlas UV jumps and line/glyph weights; opacity/blink/displacement uniforms. | Not primarily CSS text-replacement animation. |

**Confirmed — negative source check:** Generic helpers for depth of field, god rays, selective bloom, Gaussian/Kawase blur and progressive texture replacement exist in the bundle. No active application call sites were found for those helpers. Some film-grain/RGB-shift blocks are commented out. These are not reported as active effects.

**Strongly inferred — source plus appearance:** Much of the static environmental shading is carried by authored color/material maps while dynamic glows, refraction, particles and transition effects are computed at runtime. The split between baked illumination and active lighting needs further material/frame analysis; avoid describing all terrain lighting as fully dynamic or fully baked.

## 8. Asset pipeline and loaded resources

### 8.1 Observed first-load inventory

**Confirmed — baseline Resource Timing snapshot:** 101 resource entries account for **17,113,170 encoded-body bytes**, approximately **16.32 MiB**, excluding the HTML navigation response. This is that run's resource snapshot, not a universal transfer budget, compressed GPU-memory total or total bytes on the wire. HTTP overhead is excluded; worker-initiated resources may not be completely represented by the main page's timing buffer.

| Resource group | Entries | Encoded-body bytes | Confidence |
|---|---:|---:|---|
| JavaScript | 8 | 568,876 | **Confirmed** |
| WASM decoders | 2 | 314,851 | **Confirmed** |
| Draco geometry | 22 | 586,525 | **Confirmed** |
| KTX2 textures/data | 49 | 12,700,764 | **Confirmed** |
| Ogg audio | 18 | 2,939,575 | **Confirmed** |
| Font JSON | 1 | 1,334 | **Confirmed** |
| Favicon PNG | 1 | 1,245 | **Confirmed** |

The 3D JavaScript chunk is **1,487,415 decoded bytes** and **422,990 encoded-body bytes** in the baseline browser run. The bootstrap is 16,546 decoded bytes and 6,037 encoded-body bytes. Network/header evidence reports Brotli. These are concrete payload measurements, not bundle-analyzer estimates.

### 8.2 Geometry and textures

**Confirmed — source and network:** `.drc` resources include mountain/ground, igloo/batched fragments, cage/outline/patch, intro particles, three cubes, project models, shattered rings, floor and smoke/trail geometry. The decoder uses WebAssembly where available, workers and cached load promises. No `.glb` or `.gltf` request appears in the inspected baseline, despite generic loader capabilities in the code.

**Confirmed — network:** KTX2 resources include scene colors, roughness/normal maps, LUTs, caustics, bokeh, noise, frost and transition data, numbers, UI symbols and MSDF font atlases. Large cube normal maps contribute roughly a megabyte each to encoded body payloads. The presence of texture names such as “bokeh” does not establish an active post-processing DOF pass.

**Confirmed — representative binary header:** `volumes/medium_32.ktx2` is a **32 × 32 × 32**, single-level 3D texture, `vkFormat=37`, `supercompressionScheme=2`. The [Khronos KTX specification](https://registry.khronos.org/KTX/specs/2.0/ktxspec.v2.html) identifies scheme 2 as Zstandard. This is a real volume resource; KTX2 is a container, so the Basis transcoder's presence must not be generalized into “every texture uses Basis.” Other volume filenames imply 64-sized grids, but their dimensions remain source/name evidence until each header is inspected.

### 8.3 Font and audio processing

**Confirmed — downloaded font metadata:** The UI font atlas reports `type: msdf`, size 42, dimensions **512 × 1024**, distance range **4**, and **100 glyphs**, with metrics and kerning. It provides layout data rather than a normal DOM font file.

**Confirmed — source/network:** Dedicated workers include `msdfworker-ac346fa7.js`, `bitmapworker-046527f8.js`, `exrworker-41cbee65.js` and `audioworker-036a09db.js`; Draco/Basis have their own decode paths. The EXR environment map and PMREM handling are verified in source, while the baseline main-page timing list alone does not prove every worker's fetch.

**Confirmed — network:** Eighteen Ogg clips include background music, wind/room/igloo ambience, portal/particle/shard sounds, beeps, project opening/closing/click/text cues and UI/manifesto/logo effects. They download in the inspected run even when the UI says Sound: Off. Muted output is not deferred audio downloading.

## 9. Typography and UI rendering

**Confirmed — source, metadata and browser:** The main UI uses MSDF text meshes in an orthographic scene. The font worker builds geometry; glyph and line weights control reveal/falloff; shaders shift atlas UVs for scrambling and technical effects. This lets text, glow, compositing and reveal remain inside the same frame pipeline.

**Confirmed — bootstrap declaration only:** IBM Plex Mono Regular/Medium WOFF/WOFF2 faces are also declared with `font-display:swap`. No WOFF/WOFF2 request appears in the baseline main experience. Their declarations are not evidence that the visible text uses DOM font rendering. The loader is an exception: it is a DOM element with a monospace pseudo-element and CSS content animation.

**Confirmed — source:** Logo hover reruns an approximately 0.25-second shader glitch/reveal and emits an audio cue. Scroll instruction reveal combines separate 0.4/0.75-second envelopes, with a 0.5-second hide. Project links use per-link reveal staggering and hover scrambling. The interface is numerically laid out against viewport dimensions rather than relying on ordinary CSS flow.

**Confirmed — desktop scope:** Width/height thresholds select UI sizes and margins. In the 1440 × 900 browser, the small-layout branch applies because width is below 1600. Large/small desktop configurations specify logo widths 200/160 and margins 125/90 versus 45/45. This report does not cover the separate mobile branch. Pixel coordinates captured at one viewport should not be treated as fixed control locations at another.

## 10. Performance techniques

**Confirmed — application paths:**

1. **Prepared startup:** texture-load promises, `compileAsync`, explicit texture initialization and a dummy render target draw occur before scenes report uploaded. Temporarily relaxed visibility/culling allows otherwise hidden materials to be prepared, then visibility is restored.
2. **Controlled pixel cost:** initial DPR is capped rather than blindly matching the device. Adaptive DPR starts after warm-up, samples FPS over multi-second windows, reduces the multiplier below 30 FPS and increases at 60 FPS, within 0.6–1.0 of the selected base; it stops after repeated direction reversals. This verifies the control loop, not that it always reaches 60 FPS.
3. **Visibility-driven scene work:** only scene composers intersecting current scroll progress render; once detail fully covers the frame, background composers are skipped.
4. **Batching/instancing:** igloo pieces use batched matrices/data textures; particles use points or instanced quads and GPU state rather than per-particle DOM/CPU object updates.
5. **Worker decode and cached promises:** Draco, KTX2, bitmap, font, EXR and audio paths move work off the main thread where configured and avoid duplicate asset work.
6. **Selective updates:** mesh visibility windows, disabled static matrix auto-updates, frost update throttling, bloom downsampling and branches avoiding fully hidden scene reads reduce work.

**Confirmed — observed loading sequence:** The timed desktop screenshot run showed an ASCII loader, then outline/cage construction, then filled terrain/igloo and UI. Its mutation log places loader creation around 1.59 s after navigation start, an app/shadow-root change around 5.12 s, and loader removal around 5.90 s. Those timestamps belong to one instrumented run; they are not an advertised load time or stable LCP.

**Limit:** LCP/FCP and DOM text paint are incomplete measures of a continuously rendered canvas experience. No synthetic score, universal frame-rate claim, mobile performance conclusion or measured GPU-memory total is asserted here. RAF scheduling intervals collected with instrumentation are explicitly separate from GPU timing.

## 11. Interaction catalogue

| Interaction | Confidence | Observed or source-verified response |
|---|---|---|
| Wheel through main experience | **Confirmed — runtime/source** | Scene/camera progression, bounded smoothing, shader seams; native page scroll stays zero. |
| Idle after scrolling | **Confirmed — runtime/source** | Recenters toward authored scene destinations; can undo spaced small inputs. |
| ArrowDown / ArrowUp | **Confirmed — binding/source; ArrowDown exercised** | Feeds custom scroll controller rather than browser document scroll. |
| Pointer over igloo | **Confirmed — source; visual movement observed** | Proximity-dependent batched fragment motion, filtered transforms and camera displacement. Independent time motion remains active. |
| Ice-cube hover/move | **Confirmed — source** | BVH ray hit maps pointer into texture UVs, writes frost history, updates hover state/audio. Runtime capture outcomes are indexed separately. |
| Click portfolio cube | **Confirmed — source** | Navigates into matching detail route with gated frost/composite/camera/UI choreography. |
| Wheel inside detail copy | **Confirmed — source** | Root scene scrolling stops; detail's own clamped/smoothed WebGL text group scrolls and fades at screen edges. |
| Close detail | **Confirmed — source** | Reverse envelopes, camera restoration, eventual main-scroll re-enable after return-home delay. |
| Sound toggle | **Confirmed — desktop screenshot/source** | Control changes Sound: Off to Sound: On; Web Audio gain/context path governs playback. Audible output was not independently recorded in this pass. |
| Logo hover | **Confirmed — source** | Replays short glitch envelope and an audio event; not a CSS transform on a DOM logo. |
| Footer pointer | **Confirmed — source** | Fluid-velocity input perturbs the particle system. |
| Footer link hover | **Confirmed — source** | Selects volumetric shape target and associated UI effects; active names map to LinkedIn, X and Medium. |
| External project/social link click | **Confirmed — source only** | Uses `window.open(..., '_blank')`; outbound destinations were not clicked merely to demonstrate the screen. |
| Desktop viewport resize | **Confirmed — source** | Render target/camera/UI resolution and numerical layout are recomputed. Runtime screenshots are retained for visual comparison. |

**Confirmed — source:** Input uses custom raycast hit targets on scene meshes, translating them into hover/move/drag/click events. Cursor changes belong to the canvas style; `document.body` may still report `cursor:auto`. DOM button counts are therefore a poor inventory of available controls.

**Confirmed — additional desktop checks:** Clicking the centered Pudgy Penguins cube changed the URL to `/portfolio/pudgy-penguins`, exposed its dark detail scene/copy and Close control, and closing returned to `/`. Wheel input in this 900-pixel-high detail viewport did not visibly translate the copy because the displayed content fit; the existence of a separate text-scroll controller remains source-confirmed, with overflow behavior requiring a narrower/shorter detail test. Continued wheel input reached the particle/social finale and then returned to the igloo, corroborating positive loop wrap. Desktop resize screenshots show the experience recomposing at 1920 × 1080 and 1024 × 768.

**Confirmed — audio behavior:** The first successful click/key gesture resumes the audio context and automatically unmutes the controller. The cube click therefore changed Sound: Off to Sound: On without a separate sound-control click. The sound control can subsequently toggle state. This is broader than a strict “audio starts only when the sound button is clicked” model.

## 12. Network / dependency observations

**Confirmed — baseline:** Observed public network URLs are same-origin `www.igloo.inc` assets plus local blob worker URLs. No application API call, third-party analytics request, remote CMS request or persistent socket was observed in this run. This is a bounded observation, not proof those systems never exist.

**Confirmed — response headers:** Public responses expose Cloudflare headers/server identification and Vercel cache/region identifiers. It is reasonable to identify those browser-visible delivery layers. They do **not** establish a private backend topology, account arrangement, database, server framework or internal infrastructure.

**Confirmed — caching varies:** The document and some assets return `public, max-age=0, must-revalidate`; the main 3D bundle and music show `max-age=14400, must-revalidate`. ETags/Last-Modified and Brotli are visible. Hashed filenames do not mean every resource is served with immutable caching. `last-modified` is delivery metadata and not a trustworthy original launch/build date.

**Confirmed — observed console:** Baseline console contained creator credit linking `abeto.co`; no page error or WebGL warning appeared in that capture. This is not exhaustive error coverage across all routes/devices.

### Public-source cross-check

- [Abeto's Igloo case study](https://www.awwwards.com/igloo-inc-case-study.html), displayed date **31 October 2024**, is the most useful creator-written account. The live source supports its stack, shader transition, SDF UI, volume and warm-up themes. Its historical authoring claims and qualitative optimization statements are not substituted for measured current behavior.
- [Creator showcase post on the Three.js forum](https://discourse.threejs.org/t/landing-site-igloo-inc/67249), **25 June 2024**, corroborates creator association and the original Three.js context.
- [Awwwards site record](https://www.awwwards.com/sites/igloo-inc) credits Abeto/Bureaux and lists **23 July 2024** as Site of the Day. Its “Infinite Scroll” category is corroborative taxonomy; the actual looping controller is verified from production source.
- The original social announcement linked from the forum could not be directly read due to access failure. No claim relies on its unseen content.
- No verified official public production-source repository was found. Educational recreations that use React/R3F/Lenis, or name ScrollTrigger/Substance without evidence, were excluded as proof of the original site.

## 13. Evidence table with confidence levels

**Local evidence convention:** `B01`–`B50` refer to [bundle-snippets.json](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/bundle-snippets.json). Offsets are **zero-based JavaScript UTF-16 string code units**, not UTF-8 bytes or line numbers. The minified identifiers/offsets only apply to the downloaded hashes. [bundle-analysis.md](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/bundle-analysis.md) adds source context.

| ID | Finding | Confidence | Evidence / reproducible reference |
|---|---|---|---|
| E01 | Minimal HTML + dynamic 3D bootstrap | **Confirmed** | `home.html`; B01/B02; `desktop.har`. |
| E02 | Svelte shell | **Confirmed** | `index-2eb69c09.js` lifecycle/runtime; App3D imports. |
| E03 | Three r165 | **Confirmed** | B03; retained closed-shadow canvas in `desktop-behavior.json`. |
| E04 | GSAP 3.12.5 active ticker/tweens | **Confirmed** | B05/B06. |
| E05 | postprocessing 6.35.5 active composer | **Confirmed** | B04/B10/B11/B37. |
| E06 | Vite bundling | **Strongly inferred** | Bootstrap helper/event/chunks; historical creator account. |
| E07 | Main canvas hidden from ordinary selectors | **Confirmed** | B11; `desktop-entry.json` versus retained root in `desktop-behavior.json`. |
| E08 | Five scene roles, three main scroll scenes | **Confirmed** | B16/B18/B19/B20/B21/B22. |
| E09 | Native scroll disabled | **Confirmed** | B01; all baseline snapshots `scrollY=0`, document height 900. |
| E10 | Custom two-stage bounded smoothing | **Confirmed** | B22/B46. |
| E11 | 10.85-unit cyclic controller | **Confirmed — source/runtime wrap** | B22; source scene heights; `deep-loop-after-footer.png`. |
| E12 | Idle centering after 1.4 s | **Confirmed** | B22; `desktop-behavior-contact.png`, paced-input script. |
| E13 | Shader seam and chromatic frost-like displacement | **Confirmed** | B15; `desktop-contact.png`, scroll screenshots. |
| E14 | Main context and hardware renderer | **Confirmed** | `desktop-entry.json` GL details. |
| E15 | Alpha-wrapper/context discrepancy explained | **Confirmed** | B07/B47 and queried GL attributes. |
| E16 | Batched igloo fragments | **Confirmed — source** | B24; pointer screenshots corroborate behavior. |
| E17 | Custom cube transmission | **Confirmed — source** | B25/B26/B18. |
| E18 | BVH-style hit testing | **Strongly inferred — identity; active behavior confirmed in source** | B26/B27. |
| E19 | 512² frost history | **Confirmed — source** | B27/B41. |
| E20 | 150,000 GPU volume particles | **Confirmed — source** | B28; target volume header. |
| E21 | MSDF UI, not visible DOM copy | **Confirmed** | B12/B30/B35; `font-msdf.json`; DOM/AX captures. |
| E22 | Glyph-atlas scrambling | **Confirmed — source** | B31/B32. |
| E23 | Intro overlapping timings | **Confirmed** | B17; `desktop-intro-contact.png`; loader mutation log. |
| E24 | Scroll-scrubbed camera timelines | **Confirmed — source** | B17/B18/B19; distinguish clock and progress. |
| E25 | Texture/shader preparation before ready | **Confirmed — source** | B08; initialization sequence. |
| E26 | Adaptive DPR mechanism | **Confirmed — source** | B09/B23; not a guaranteed FPS result. |
| E27 | Resource counts/body-byte budget | **Confirmed** | `network-summary.json`, `desktop-entry.json`, `desktop.har`. |
| E28 | Draco/KTX2/decoder workers | **Confirmed** | B34/B36; JS/WASM/DRC/KTX2 network entries. |
| E29 | 32³ volume with Zstandard scheme | **Confirmed** | `volume-header.json`, `volume-medium-32.ktx2`, Khronos format definition. |
| E30 | Audio downloaded while muted | **Confirmed** | 18 Ogg entries plus Sound: Off screenshot; B14/B33. |
| E31 | Sound-state toggle | **Confirmed** | `desktop-sound-toggle.png`; source Web Audio path. |
| E32 | Separate detail-copy scroll | **Confirmed — source** | B44/B45; tested 900px detail copy fit without scroll displacement. |
| E33 | Browser-visible Cloudflare/Vercel delivery | **Confirmed** | `desktop-network.json`, `network-summary.json`; no private backend conclusion. |
| E34 | No observed API/analytics socket in baseline | **Confirmed — bounded observation** | `desktop.har` and response URL list. |
| E35 | Authored/environment shading contributes to appearance | **Strongly inferred** | Material/color-map paths plus scene appearance; baking extent unmeasured. |
| E36 | Creator's historical modeling/export workflow | **Confirmed — creator reported** | Linked 2024 case study; no original DCC project access. |
| E37 | Actual draw/program/primitive counts | **Confirmed — bounded frames** | Five raw `spector-*.json` captures, `spector-summary.json`. |
| E38 | Active RGBA16F, RGBA32F MRT and depth24 formats | **Confirmed** | Capture `DrawCall.frameBuffer` state; `spector-*-draws.json`. |
| E39 | UI → bloom → SMAA order | **Confirmed — capture/source** | Program/framebuffer command sequence, B50 and capture excerpts. |
| E40 | GPU draw requests 150,000 points | **Confirmed** | Finale `drawArrays` command 179, args `[0,0,150000]`. |
| E41 | Click-open-close and positive loop wrap | **Confirmed — runtime** | `deep-detail-*.png`, `deep-footer.png`, `deep-loop-after-footer.png`. |
| E42 | First-gesture automatic audio unmute | **Confirmed — source/runtime state** | B49; Off before cube click, On in detail screenshots. |
| E43 | Startup compositor switches after intro | **Confirmed** | B48; hero program 2 versus full composite in later captures. |

### Screenshot and recording guide

- [Intro contact sheet](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/desktop-intro-contact.png): timed loader → technical geometry → filled scene.
- [Continuous-scroll contact sheet](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/desktop-contact.png): hero, seam, portfolio objects and portal approach.
- [Paced-input contact sheet](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/desktop-behavior-contact.png): shows idle return/centering; it does not cover the entire loop.
- [Desktop behavior data](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/desktop-behavior.json): exact retained shadow-root contents, loading observations, viewport and resource snapshots; its `video` field points to the recorded desktop WebM.
- [Baseline HAR](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/desktop.har): network metadata, without embedded response bodies.
- [GPU capture summary](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/spector-summary.json): counts, formats, active programs and analyzer results; sibling draw/shader JSON files avoid opening large thumbnail-rich captures.
- [Project detail](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/deep-detail-ready.png), [particle finale](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/deep-footer.png), [loop return](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/deep-loop-after-footer.png): exercised desktop route/scene states.
- [Evidence manifest](D:/Cursor/Jarvis-UI-UX/work/igloo-forensics-pass-1/evidence/evidence-manifest.json): file sizes and SHA-256 hashes of source/data evidence, excluding pre-scope-correction mobile artifacts and image/video files.

## 14. Important unknowns requiring deeper investigation

1. **Full runtime GPU budget:** five frames establish counts/formats for sampled states, but transition peaks, settled-hero differences, per-pass GPU timing, complete render-target memory and sustained uninstrumented frame rate remain unmeasured. Do not equate Spector's capture/readback time with GPU frame time or its memory estimates with a physical VRAM measurement.
2. **Shader ownership boundaries:** source reveals custom code and vendored helpers; original module names, authorship history and build graph are absent without verified source maps/repository.
3. **Complete material/lighting split:** how much terrain/cube shading is authored/baked, which active shadow maps/lights contribute, and whether all instances share the same quality tier.
4. **Compression choices per asset/GPU:** representative volume is Zstandard-compressed RGBA data; 2D textures may select another compressed GPU format. Need actual upload/internal-format evidence for the complete set.
5. **Original DCC/export tools:** exact VDB exporter, channel quantization, crystal-growth implementation, artist graph/node settings and geometry metadata. **Speculative:** some offline preprocessing may be highly bespoke; no original files were available to verify its exact form.
6. **Desktop browser coverage:** only a Chromium-family browser on one GPU was exercised. Firefox/Safari input normalization, extension availability, shader output and audio behavior remain untested.
7. **Reduced-motion/fallback semantics:** no comprehensive runtime coverage of reduced-motion, keyboard focus, screen-reader navigation, context loss, WebGL2 failure or failed assets. The baseline unnamed canvas is evidence of limited exposed semantics, not a complete standards verdict.
8. **Audio result:** cues/gain paths and downloads are verified; audible mix/latency/spatialization were not recorded and listened to independently.
9. **Deep-link/history correctness:** browser back/forward, reload during detail transitions and direct detail URLs require dedicated tests.
10. **Private systems:** browser evidence does not reveal private backend services, databases or organizational infrastructure. These are outside the scope of this forensic pass.

## 15. Recommended targets for a second forensic pass

These are further inspection targets, not design recommendations for another application.

1. **Capture a controlled state matrix:** settled hero, first scene seam, each cube, active frost trail, detail at transition/settled/text-scroll, each portal proximity pulse, finale idle and each social shape morph. Record logical progress and wall-clock phase along with each capture.
2. **Reconstruct the exact active frame graph:** associate every draw with program, render target, attachment formats, viewport, blend/depth state and texture inputs. Compare source-predicted composite → UI → bloom → SMAA ordering to captures.
3. **Measure actual timing:** uninstrumented control run, instrumented run, GPU timer queries where reliable, JS profiler, long tasks and compilation/upload events. Explicitly distinguish load readiness, intro duration, CPU frame cost, GPU frame cost and dropped frames.
4. **Track simulation state:** identify particle MRT formats/count padding, volume decode scales, fluid target layout, frost history decay and update cadence; inspect uniforms over several adjacent frames rather than reading one shader alone.
5. **Inspect all relevant binary headers:** volume dimensions/codec, LUT dimensions, texture mip chains, GPU-transcoded formats and Draco custom attributes/piece counts. Compare those facts to the creator's historical authoring account.
6. **Exercise desktop route/input edge cases:** click-open-close, deep-link reload, back/forward, wheel reversal, idle centering, complete positive/negative wrap, blocked input during transitions and details with long copy.
7. **Desktop responsiveness and accessibility:** wide/narrow window resizing, DPR changes on monitor movement, zoom, reduced-motion, Tab/focus/Enter behavior, unnamed canvas semantics and WebGL/context-loss fallback. Mobile layouts remain outside this pass's scope.
8. **Complete MCP setup if authorized:** install the official server's dependencies, build it, and verify its tool inventory/captures with the prepared adapter. Closed-root discovery and early Spector injection are known requirements here. Compare MCP analyzer counts with raw captures: extension multidraw names and time-unit handling should be checked rather than trusting summaries blindly.
