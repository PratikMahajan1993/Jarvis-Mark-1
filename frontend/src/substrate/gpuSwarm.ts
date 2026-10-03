import type { GpuFormulaState, GpuFrame } from "./swarm";

const SIM_VERTEX = /* glsl */ `#version 300 es
precision highp float;
precision highp int;

in vec3 aPrev;
in vec3 aScatter;
out vec3 vPos;
out vec3 vCol;

uniform float uCount;
uniform float uBlend;
uniform float uGather;
uniform float uEaseK;
uniform float uReduced;

uniform int uIdA;
uniform int uIdB;
uniform float uClockA;
uniform float uClockB;
uniform vec2 uFitA;
uniform vec2 uFitB;
uniform vec4 uCortexA;
uniform vec4 uCortexB;
uniform float uPulseA;
uniform float uPulseB;
uniform vec4 uAsciA;
uniform vec4 uAsciB;

float hue2rgb(float p, float q, float t) {
  if (t < 0.0) t += 1.0;
  if (t > 1.0) t -= 1.0;
  if (t < 1.0 / 6.0) return p + (q - p) * 6.0 * t;
  if (t < 0.5) return q;
  if (t < 2.0 / 3.0) return p + (q - p) * (2.0 / 3.0 - t);
  return p;
}

vec3 hsl2rgb(float h, float s, float l) {
  float hh = mod(mod(h, 1.0) + 1.0, 1.0);
  float ss = clamp(s, 0.0, 1.0);
  float ll = clamp(l, 0.0, 1.0);
  if (ss == 0.0) return vec3(ll);
  float p = ll <= 0.5 ? ll * (1.0 + ss) : ll + ss - ll * ss;
  float q = 2.0 * ll - p;
  return vec3(
    hue2rgb(q, p, hh + 1.0 / 3.0),
    hue2rgb(q, p, hh),
    hue2rgb(q, p, hh - 1.0 / 3.0)
  );
}

vec3 finite3(vec3 p) {
  return vec3(p.x == p.x ? p.x : 0.0, p.y == p.y ? p.y : 0.0, p.z == p.z ? p.z : 0.0);
}

void evalCortex(int i, float time, vec4 cortex, float pulseSpeed, out vec3 pos, out vec3 col) {
  float radiusOuter = cortex.x;
  float radiusInner = cortex.y;
  float neuroActivity = cortex.z;
  float chaosFactor = cortex.w;
  float t = time * pulseSpeed;
  float iNorm = float(i) / uCount;
  float layer = iNorm < 0.5 ? 0.0 : 1.0;
  float localI = layer == 0.0 ? float(i) : float(i) - uCount * 0.5;
  float totalLocal = uCount * 0.5;
  float phi = acos(clamp(1.0 - 2.0 * (localI + 0.5) / totalLocal, -1.0, 1.0));
  float theta = sqrt(totalLocal * 3.141592653589793) * (localI + 0.5);
  float r = layer == 0.0 ? radiusOuter : radiusInner;
  float x = r * sin(phi) * cos(theta);
  float y = r * sin(phi) * sin(theta);
  float z = r * cos(phi);
  float noiseX = sin(t * 0.5 + phi * 3.0) * cos(t * 0.3 + theta * 2.0);
  float noiseY = cos(t * 0.4 + phi * 2.0) * sin(t * 0.6 + theta * 3.0);
  float noiseZ = sin(t * 0.7 + phi + theta);
  float moveAmt = layer == 0.0 ? chaosFactor * 1.5 : chaosFactor * 0.5;
  x += noiseX * moveAmt;
  y += noiseY * moveAmt;
  z += noiseZ * moveAmt;
  float pulse = sin(t * 2.0 + float(i) * 0.01) * 0.05 + 1.0;
  x *= pulse;
  y *= pulse;
  z *= pulse;
  pos = vec3(x, y, z);
  float hFinal = 0.6 * (1.0 - neuroActivity);
  float lVar = layer == 0.0 ? 0.5 : 0.3 + neuroActivity * 0.4;
  float sVar = layer == 0.0 ? 0.8 : 0.6 + neuroActivity * 0.3;
  col = hsl2rgb(hFinal, sVar, lVar);
}

void evalAsci(int i, float time, vec4 asci, out vec3 pos, out vec3 col) {
  float scale = asci.x;
  float flow = asci.y;
  float chaos = asci.z;
  float twist = asci.w;
  float denom = uCount > 1.0 ? uCount - 1.0 : 1.0;
  float u = float(i) / denom;
  float band = floor(u * 120.0);
  float local = u * 120.0 - band;
  float angle = local * 3.141592653589793 * 2.0 + band * 0.618 + time * flow;
  float waveA = sin(angle * 3.0 + band * 0.13 + time * flow);
  float waveB = cos(angle * 2.0 - band * 0.09 + time * flow * 0.7);
  float waveC = sin(band * 0.21 + time * flow * 0.5);
  float radius = scale * (0.35 + 0.28 * sin(band * 0.17 + time * flow) + 0.22 * waveA);
  float spiral = band * 0.055 + time * flow * 0.2;
  float distortion = chaos * scale * 0.18;
  float px = cos(angle + spiral) * radius + sin(band * 0.31 + time * flow) * distortion;
  float py = (band - 60.0) * scale * 0.028 + waveA * scale * 0.22 + waveB * distortion;
  float pz = sin(angle * twist + spiral) * radius + waveC * scale * 0.35;
  pos = vec3(px, py, pz);
  float hue = 0.015 + 0.055 * (0.5 + 0.5 * sin(angle + time * flow * 0.4));
  float light = 0.28 + 0.5 * (0.5 + 0.5 * sin(band * 0.12 + angle * 2.0));
  col = hsl2rgb(hue, 1.0, light);
}

void evalChat(int i, float time, out vec3 pos, out vec3 col) {
  float denom = max(1.0, uCount - 1.0);
  float u = float(i) / denom;
  float phi = acos(clamp(1.0 - 2.0 * u, -1.0, 1.0));
  float theta = float(i) * 2.399963229728653 + time * 0.32;
  float breathe = 1.0 + 0.22 * sin(time * 1.7 + u * 18.0);
  float warp = 1.0 + 0.28 * sin(theta * 3.0 + time) * sin(phi * 5.0);
  float pulse = 1.0 + 0.16 * sin(time * 2.4 + theta * 2.0 + phi * 7.0);
  float radius = (18.0 + 42.0 * pow(u, 0.42)) * breathe * warp * pulse;
  float twist = time * 0.22 + radius * 0.018 + sin(phi * 6.0 + time) * 0.35;
  float ct = cos(theta + twist);
  float st = sin(theta + twist);
  float sp = sin(phi);
  float cp = cos(phi);
  float x = radius * sp * ct;
  float y = radius * cp + sin(theta * 4.0 + time * 1.3) * 3.5;
  float z = radius * sp * st;
  float fold = sin(x * 0.09 + time) * cos(z * 0.075 - time * 0.7);
  float lift = fold * 5.5 + sin(y * 0.12 + theta) * 2.5;
  pos = vec3(x + fold * 2.2, y + lift, z + cos(x * 0.06 + z * 0.08 + time) * 3.0);
  float hue = mod(0.55 + u * 0.32 + fold * 0.035 + time * 0.025, 1.0);
  float light = 0.42 + 0.18 * abs(sin(theta * 2.0 + time));
  col = hsl2rgb(hue, 0.9, light);
}

void evalFitted(int id, int i, float time, vec4 cortex, float pulse, vec4 asci, vec2 fit, out vec3 pos, out vec3 col) {
  vec3 raw;
  if (id == 1) evalAsci(i, time, asci, raw, col);
  else if (id == 2) evalChat(i, time, raw, col);
  else evalCortex(i, time, cortex, pulse, raw, col);
  pos = finite3(vec3(raw.x * fit.y, (raw.y - fit.x) * fit.y, raw.z * fit.y));
}

void main() {
  int i = gl_VertexID;
  vec3 posA;
  vec3 colA;
  vec3 posB;
  vec3 colB;
  evalFitted(uIdA, i, uClockA, uCortexA, uPulseA, uAsciA, uFitA, posA, colA);
  vec3 pos;
  vec3 col;
  bool single = uIdA == uIdB || uBlend <= 0.001 || uBlend >= 0.999;
  if (single) {
    if (uBlend >= 0.999 && uIdA != uIdB) {
      evalFitted(uIdB, i, uClockB, uCortexB, uPulseB, uAsciB, uFitB, pos, col);
    } else {
      pos = posA;
      col = colA;
    }
  } else {
    evalFitted(uIdB, i, uClockB, uCortexB, uPulseB, uAsciB, uFitB, posB, colB);
    float u = float(i) / uCount;
    float b = uReduced > 0.5
      ? smoothstep(0.0, 1.0, uBlend)
      : smoothstep(0.0, 1.0, (uBlend - 0.15 * u) / 0.85);
    float bulge = uReduced > 0.5 ? 1.0 : 1.0 + 0.12 * sin(3.141592653589793 * b);
    pos = mix(posA, posB, b) * bulge;
    col = mix(colA, colB, b);
  }
  if (uGather < 1.0) pos = mix(aScatter, pos, uGather);
  vPos = mix(aPrev, pos, uEaseK);
  vCol = col;
}
`;

const SIM_FRAGMENT = /* glsl */ `#version 300 es
precision highp float;
out vec4 frag;
void main() { frag = vec4(0.0); }
`;

function compile(gl: WebGL2RenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error("[substrate] sim shader", gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function bufferWith(gl: WebGL2RenderingContext, data: Float32Array, usage: number): WebGLBuffer | null {
  const buffer = gl.createBuffer();
  if (!buffer) return null;
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, data, usage);
  return buffer;
}

function pack(gl: WebGL2RenderingContext, loc: WebGLUniformLocation | null, state: GpuFormulaState, cortex: boolean) {
  if (!loc) return;
  if (cortex) gl.uniform4f(loc, state.radiusOuter, state.radiusInner, state.neuroActivity, state.chaosFactor);
  else gl.uniform4f(loc, state.scale, state.flow, state.chaos, state.twist);
}

/**
 * Per-particle formulas and the position ease, on the GPU.
 * Clocks and placement stay on the CPU and arrive as uniforms.
 * Results are copied into the draw buffers ogl already bound.
 */
export class GpuSwarm {
  private readonly gl: WebGL2RenderingContext;
  private readonly count: number;
  private readonly program: WebGLProgram;
  private readonly tf: WebGLTransformFeedback;
  private readonly vao: WebGLVertexArrayObject;
  private readonly scatter: WebGLBuffer;
  private readonly pos: [WebGLBuffer, WebGLBuffer];
  private readonly col: [WebGLBuffer, WebGLBuffer];
  private read = 0;
  private checked = false;
  private readonly loc: Record<string, WebGLUniformLocation | null>;

  private constructor(
    gl: WebGL2RenderingContext,
    count: number,
    program: WebGLProgram,
    tf: WebGLTransformFeedback,
    vao: WebGLVertexArrayObject,
    scatter: WebGLBuffer,
    pos: [WebGLBuffer, WebGLBuffer],
    col: [WebGLBuffer, WebGLBuffer],
  ) {
    this.gl = gl;
    this.count = count;
    this.program = program;
    this.tf = tf;
    this.vao = vao;
    this.scatter = scatter;
    this.pos = pos;
    this.col = col;
    const names = [
      "uCount", "uBlend", "uGather", "uEaseK", "uReduced",
      "uIdA", "uIdB", "uClockA", "uClockB", "uFitA", "uFitB",
      "uCortexA", "uCortexB", "uPulseA", "uPulseB", "uAsciA", "uAsciB",
    ];
    this.loc = {};
    for (const name of names) this.loc[name] = gl.getUniformLocation(program, name);
  }

  static tryCreate(gl: WebGL2RenderingContext, count: number, scatter: Float32Array): GpuSwarm | null {
    if (typeof gl.createTransformFeedback !== "function") return null;
    const vs = compile(gl, gl.VERTEX_SHADER, SIM_VERTEX);
    const fs = compile(gl, gl.FRAGMENT_SHADER, SIM_FRAGMENT);
    if (!vs || !fs) return null;
    const program = gl.createProgram();
    if (!program) return null;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.bindAttribLocation(program, 0, "aPrev");
    gl.bindAttribLocation(program, 1, "aScatter");
    gl.transformFeedbackVaryings(program, ["vPos", "vCol"], gl.SEPARATE_ATTRIBS);
    gl.linkProgram(program);
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error("[substrate] sim link", gl.getProgramInfoLog(program));
      gl.deleteProgram(program);
      return null;
    }

    const blank = new Float32Array(count * 3);
    const pos0 = bufferWith(gl, scatter, gl.DYNAMIC_COPY);
    const pos1 = bufferWith(gl, scatter, gl.DYNAMIC_COPY);
    const col0 = bufferWith(gl, blank, gl.DYNAMIC_COPY);
    const col1 = bufferWith(gl, blank, gl.DYNAMIC_COPY);
    const scatterBuf = bufferWith(gl, scatter, gl.STATIC_DRAW);
    const tf = gl.createTransformFeedback();
    const vao = gl.createVertexArray();
    if (!pos0 || !pos1 || !col0 || !col1 || !scatterBuf || !tf || !vao) return null;

    gl.bindVertexArray(vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, pos0);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, scatterBuf);
    gl.enableVertexAttribArray(1);
    gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);

    return new GpuSwarm(gl, count, program, tf, vao, scatterBuf, [pos0, pos1], [col0, col1]);
  }

  /** Run one ease step and copy the result into the draw buffers. */
  simulate(frame: GpuFrame, drawPos: WebGLBuffer, drawCol: WebGLBuffer) {
    const gl = this.gl;
    const read = this.read;
    const write = 1 - read;

    gl.bindVertexArray(this.vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.pos[read]);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);

    gl.useProgram(this.program);
    gl.uniform1f(this.loc.uCount!, this.count);
    gl.uniform1f(this.loc.uBlend!, frame.blend);
    gl.uniform1f(this.loc.uGather!, frame.gather);
    gl.uniform1f(this.loc.uEaseK!, frame.easeK);
    gl.uniform1f(this.loc.uReduced!, frame.reduced ? 1 : 0);
    this.side("A", frame.a);
    this.side("B", frame.b);

    gl.enable(gl.RASTERIZER_DISCARD);
    gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK, this.tf);
    gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 0, this.pos[write]);
    gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 1, this.col[write]);
    gl.beginTransformFeedback(gl.POINTS);
    gl.drawArrays(gl.POINTS, 0, this.count);
    gl.endTransformFeedback();
    gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 0, null);
    gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 1, null);
    gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK, null);
    gl.disable(gl.RASTERIZER_DISCARD);
    gl.bindVertexArray(null);

    const bytes = this.count * 3 * 4;
    gl.bindBuffer(gl.COPY_READ_BUFFER, this.pos[write]);
    gl.bindBuffer(gl.COPY_WRITE_BUFFER, drawPos);
    gl.copyBufferSubData(gl.COPY_READ_BUFFER, gl.COPY_WRITE_BUFFER, 0, 0, bytes);
    gl.bindBuffer(gl.COPY_READ_BUFFER, this.col[write]);
    gl.bindBuffer(gl.COPY_WRITE_BUFFER, drawCol);
    gl.copyBufferSubData(gl.COPY_READ_BUFFER, gl.COPY_WRITE_BUFFER, 0, 0, bytes);
    gl.bindBuffer(gl.COPY_READ_BUFFER, null);
    gl.bindBuffer(gl.COPY_WRITE_BUFFER, null);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    gl.bindVertexArray(null);
    // ogl skips rebinding its VAO when it still thinks that VAO is current.
    const renderer = (gl as WebGL2RenderingContext & { renderer?: { currentGeometry: string | null } }).renderer;
    if (renderer) renderer.currentGeometry = null;
    if (!this.checked) {
      this.checked = true;
      const err = gl.getError();
      if (err !== gl.NO_ERROR) console.error("[substrate] particle sim failed", err);
    }

    this.read = write;
  }

  private side(suffix: "A" | "B", state: GpuFormulaState) {
    const gl = this.gl;
    gl.uniform1i(this.loc[`uId${suffix}`]!, state.slot);
    gl.uniform1f(this.loc[`uClock${suffix}`]!, state.clock);
    gl.uniform2f(this.loc[`uFit${suffix}`]!, state.fitCy, state.fitInvH);
    pack(gl, this.loc[`uCortex${suffix}`]!, state, true);
    gl.uniform1f(this.loc[`uPulse${suffix}`]!, state.pulseSpeed);
    pack(gl, this.loc[`uAsci${suffix}`]!, state, false);
  }

  dispose() {
    const gl = this.gl;
    gl.deleteTransformFeedback(this.tf);
    gl.deleteVertexArray(this.vao);
    gl.deleteProgram(this.program);
    gl.deleteBuffer(this.scatter);
    gl.deleteBuffer(this.pos[0]);
    gl.deleteBuffer(this.pos[1]);
    gl.deleteBuffer(this.col[0]);
    gl.deleteBuffer(this.col[1]);
  }
}
