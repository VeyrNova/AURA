"""GPU procedural Visual Core V23 Volumetric Neural Shell Optimization

Compatibility lineage: Visual Core V11 Material & Typography Match for AURA v0.7.0.15.6.11.

Patch 22 activates UI Focus Mode: the neural orb/cortex/particles/base are temporarily paused so UI development can move forward. The validated AURA logo/boot sequence and reactive cyan-violet waveform remain active. The full neural shader is intentionally retained in this file for later reactivation.

This module deliberately uses Qt's own OpenGL wrappers only: no browser,
Three.js or PyOpenGL dependency.  The surface renders a procedural energy core
with a GLSL fragment shader and exposes the same high-level state controls as
the legacy QPainter orb.
"""
from __future__ import annotations

import array
from collections import deque
import logging
import math

from PySide6.QtCore import QElapsedTimer, QTimer, Qt, Signal
from PySide6.QtGui import QSurfaceFormat, QVector2D, QVector3D
from PySide6.QtOpenGL import QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram

try:
    from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
except ImportError:  # pragma: no cover - depends on Qt build
    QOpenGLFramebufferObject = None
    QOpenGLFramebufferObjectFormat = None
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from config.settings import settings
from runtime.hardware_runtime import hardware_runtime
from ui.aura_mood import MOOD_STRENGTH, mood_palette, normalize_mood

logger = logging.getLogger("aura.ui.opengl_orb")

_GL_FLOAT = 0x1406
_GL_TRIANGLE_STRIP = 0x0005
_GL_COLOR_BUFFER_BIT = 0x00004000
_GL_BLEND = 0x0BE2
_GL_SRC_ALPHA = 0x0302
_GL_ONE_MINUS_SRC_ALPHA = 0x0303
_GL_FRAMEBUFFER = 0x8D40
_GL_TEXTURE0 = 0x84C0
_GL_TEXTURE_2D = 0x0DE1
_GL_LINEAR = 0x2601
_GL_TEXTURE_MIN_FILTER = 0x2801
_GL_TEXTURE_MAG_FILTER = 0x2800
_GL_VENDOR = 0x1F00
_GL_RENDERER = 0x1F01
_GL_VERSION = 0x1F02

STATE_TARGETS = {
    "STARTUP": ((0.00, 0.82, 1.00), (0.78, 0.24, 1.00), 1.04, 1.95),
    "IDLE": ((0.00, 0.74, 1.00), (0.60, 0.25, 1.00), 0.42, 0.78),
    "THINKING": ((0.18, 0.55, 1.00), (0.66, 0.30, 1.00), 0.78, 1.00),
    "PROCESSING": ((0.16, 0.62, 1.00), (0.58, 0.32, 1.00), 0.86, 1.20),
    "PRELOAD": ((0.00, 0.88, 1.00), (0.70, 0.30, 1.00), 1.08, 1.72),
    "SPEAKING": ((0.10, 0.82, 1.00), (0.74, 0.28, 1.00), 1.00, 1.50),
    "LISTENING": ((0.00, 0.94, 1.00), (0.35, 0.50, 1.00), 0.92, 1.25),
    "EXECUTING": ((0.05, 0.82, 1.00), (0.55, 0.28, 1.00), 0.96, 1.35),
    "ERROR": ((1.00, 0.18, 0.32), (1.00, 0.18, 0.62), 0.72, 0.75),
}

VERTEX_SHADER = r"""
#version 120
attribute vec2 a_position;
varying vec2 v_uv;
void main() {
    v_uv = a_position * 0.5 + 0.5;
    gl_Position = vec4(a_position, 0.0, 1.0);
}
"""

# Patch 22 — reversible UI focus switch. Keep the full neural shader below,
# but compile the lightweight logo+waveform stage while other UI work proceeds.
UI_FOCUS_MODE = True

FOCUS_FRAGMENT_SHADER = r"""
#version 120
varying vec2 v_uv;
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_energy;
uniform float u_voice;
uniform float u_speed;
uniform vec3 u_primary;
uniform vec3 u_secondary;
uniform float u_state;
uniform float u_boot_progress;

void main() {
    vec2 p = v_uv * 2.0 - 1.0;
    p.x *= u_resolution.x / max(u_resolution.y, 1.0);
    // Patch 22.4: keep u_speed live in Focus Mode. Intel GLSL optimizes truly
    // unused uniforms away; the runtime resolves this one for every scene.
    float t = u_time * (0.94 + 0.06 * clamp(u_speed, 0.0, 2.0));
    float voice = clamp(u_voice, 0.0, 1.0);
    float voiceGain = pow(voice, 0.68);
    float speaking = 1.0 - smoothstep(0.30, 0.72, abs(u_state - 3.0));
    float listening = 1.0 - smoothstep(0.30, 0.72, abs(u_state - 4.0));
    float thinking = max(
        1.0 - smoothstep(0.30, 0.72, abs(u_state - 1.0)),
        1.0 - smoothstep(0.30, 0.72, abs(u_state - 2.0))
    );

    // Deep shell background only — deliberately no circular orb silhouette.
    vec3 col = vec3(0.0012, 0.0050, 0.0155);
    float horizontalAtmosphere = exp(-pow(p.y / 0.42, 2.0)) * exp(-pow(p.x / 1.70, 4.0));
    col += mix(u_primary, u_secondary, 0.50) * horizontalAtmosphere * (0.0025 + 0.0055*u_energy);

    // Keep the signal understated in idle and strongly voice-reactive in SPEAKING.
    float stateActivity = clamp(0.10 + 0.78*speaking + 0.20*listening + 0.16*thinking, 0.0, 1.15);
    // Patch 22.2 target: near-flat idle, ~20-30 px normal speech and
    // ~35-45 px accented syllables at the reference viewport height.
    float amp = 0.0035 + 0.012*thinking + 0.014*listening + speaking*(0.004 + 0.115*voiceGain);
    float wave =
        sin(p.x*8.2  - t*(1.60 + 0.52*speaking)) * 0.43 +
        sin(p.x*17.5 + t*(2.05 + 0.82*voiceGain) + 0.8) * 0.25 +
        sin(p.x*34.0 - t*(2.90 + 1.35*voiceGain) + 1.7) * 0.13 +
        sin(p.x*61.0 + t*(4.30 + 1.80*voiceGain) + 2.4) * 0.07;
    float envelope = 0.55 + 0.45*exp(-pow(p.x/1.25, 4.0));
    float spikeGate = pow(abs(sin(p.x*19.0 - t*3.2)), 7.0);
    float transientWave = sin(p.x*92.0 + t*(10.0 + 5.0*voiceGain)) * spikeGate;
    float y = (wave * amp + speaking*voiceGain*0.021*transientWave) * envelope;
    float d = abs(p.y - y);
    float core = exp(-pow(d / (0.0038 + 0.0018*speaking), 2.0));
    float halo = exp(-pow(d / (0.016 + 0.012*speaking + 0.012*voiceGain), 2.0));
    float wide = exp(-pow(d / 0.050, 2.0));
    float xfade = smoothstep(1.72, 1.42, abs(p.x));
    float bootReveal = smoothstep(0.70, 0.90, u_boot_progress);
    float finalReveal = (u_state > 7.5) ? bootReveal : 1.0;

    float mixPos = clamp(v_uv.x, 0.0, 1.0);
    vec3 waveColor = mix(u_primary, u_secondary, smoothstep(0.42, 0.80, mixPos));
    vec3 coldWhite = vec3(0.92, 0.985, 1.0);
    col += waveColor * wide * xfade * finalReveal * (0.008 + 0.018*stateActivity);
    col += waveColor * halo * xfade * finalReveal * (0.052 + 0.118*stateActivity + 0.190*voiceGain);
    col += mix(waveColor, coldWhite, 0.52) * core * xfade * finalReveal * (0.24 + 0.24*stateActivity + 0.52*voiceGain);

    // A few local speech spikes enrich the waveform without any orb geometry.
    float spikeMask = speaking * voiceGain * xfade;
    float spikes = pow(0.5 + 0.5*sin(p.x*43.0 - t*9.0), 16.0)
                 + 0.65*pow(0.5 + 0.5*sin(p.x*71.0 + t*12.5 + 1.1), 22.0);
    col += mix(waveColor, coldWhite, 0.68) * halo * spikes * spikeMask * 0.10;

    // Mild vignette, no hidden sphere/ring/base.
    float vignette = 1.0 - 0.12*smoothstep(0.65, 1.55, length(p*vec2(0.52,0.84)));
    col *= vignette;
    col = col / (1.0 + col*0.35);
    gl_FragColor = vec4(col, 1.0);
}
"""

FRAGMENT_SHADER = r"""
#version 120
varying vec2 v_uv;
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_energy;
uniform float u_voice;
uniform float u_speed;
uniform vec3 u_primary;
uniform vec3 u_secondary;
uniform float u_state;
uniform float u_boot_progress;

const float PI = 3.14159265359;

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float auraNoise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float value = 0.0;
    float amp = 0.52;
    for (int i = 0; i < 4; ++i) {
        value += amp * auraNoise2D(p);
        p = mat2(1.63, 1.17, -1.17, 1.63) * p + 0.17;
        amp *= 0.50;
    }
    return value;
}

float ridgeContour(float value, float center, float width) {
    float d = abs(value - center) / max(width, 0.0001);
    return exp(-d * d);
}

float ringBand(float r, float radius, float width) {
    float d = (r - radius) / max(width, 0.0001);
    return exp(-d * d);
}

float arcMask(float ang, float segments, float phase, float duty) {
    float s = 0.5 + 0.5 * sin(ang * segments + phase);
    return smoothstep(duty, 1.0, s);
}

float lineGlow(float d, float width) {
    return exp(-pow(d / max(width, 0.0001), 2.0));
}

// PATCH 16 — compact dendritic primitives. They are deliberately local, so
// the cortex cannot read as large orbital curves crossing the whole sphere.
vec2 rotate2(vec2 v, float a) {
    float c = cos(a), s = sin(a);
    return vec2(c*v.x - s*v.y, s*v.x + c*v.y);
}

float shortTrunk(vec2 q, float halfLen, float bend, float width) {
    float env = 1.0 - smoothstep(halfLen*0.72, halfLen, abs(q.x));
    float curve = bend * (q.x*q.x - halfLen*halfLen*0.18);
    float d = abs(q.y - curve);
    return exp(-pow(d / max(width, 0.0001), 2.0)) * env;
}

float shortArm(vec2 q, float len, float bend, float width) {
    float begin = smoothstep(-0.018, 0.030, q.x);
    float end = 1.0 - smoothstep(len*0.72, len, q.x);
    float curve = bend * q.x*q.x;
    float d = abs(q.y - curve);
    return exp(-pow(d / max(width, 0.0001), 2.0)) * begin * end;
}

float dendriteCluster(vec2 q, float grid, float seed, float width) {
    vec2 g = q * grid;
    vec2 cell = floor(g);
    vec2 local = fract(g) - 0.5;
    float h0 = hash21(cell + vec2(seed*17.3, seed*7.1));
    float h1 = hash21(cell + vec2(seed*5.7 + 4.1, seed*13.9 + 1.7));
    float h2 = hash21(cell + vec2(seed*9.3 + 8.7, seed*3.1 + 5.3));
    local = rotate2(local, h0*6.28318530718);
    float halfLen = 0.26 + 0.08*h1;
    float bend = mix(-1.15, 1.15, h2);
    float trunk = shortTrunk(local, halfLen, bend, width);

    float x1 = -0.08 + 0.09*h1;
    float y1 = bend * (x1*x1 - halfLen*halfLen*0.18);
    vec2 b1 = rotate2(local - vec2(x1,y1), 0.72 + 0.32*h0);
    float arm1 = shortArm(b1, halfLen*(0.62 + 0.10*h2), bend*0.45, width*0.78);

    float x2 = 0.06 + 0.08*h2;
    float y2 = bend * (x2*x2 - halfLen*halfLen*0.18);
    vec2 b2 = rotate2(local - vec2(x2,y2), -(0.68 + 0.34*h1));
    float arm2 = shortArm(b2, halfLen*(0.54 + 0.14*h0), -bend*0.38, width*0.72);

    // A tiny tertiary twig makes each cell read like a branched neuron rather
    // than a simple Y symbol.
    vec2 b3 = rotate2(b1 - vec2(halfLen*0.20, 0.0), 0.58 + 0.20*h2);
    float arm3 = shortArm(b3, halfLen*0.34, -bend*0.26, width*0.58);
    return clamp(trunk + 0.90*arm1 + 0.82*arm2 + 0.58*arm3, 0.0, 1.65);
}

// PATCH 17 — connected medium-length curved bundles. These are continuous
// within local regions and are deliberately broken by a soft gate so they read
// as linked neural highways rather than orbital rings crossing the full sphere.
float connectedBundle(vec2 q, float angle, float spacing, float seed, float width) {
    vec2 r = rotate2(q, angle);
    float warp = 0.105*sin(r.x*3.7 + seed*6.1)
               + 0.045*sin(r.x*8.9 - seed*4.7)
               + 0.020*sin(r.x*15.3 + seed*2.9);
    float band = abs(mod((r.y - warp) + spacing*0.5, spacing) - spacing*0.5);
    float fibre = exp(-pow(band / max(width, 0.0001), 2.0));
    float region = 0.50 + 0.50*sin(r.x*4.2 + r.y*2.4 + seed*9.0);
    region += 0.34*sin(r.x*7.6 - r.y*3.1 - seed*5.4);
    float gate = smoothstep(-0.26, 0.22, region);
    return fibre * gate;
}

float bundleTwig(vec2 q, float angle, float seed, float width) {
    vec2 r = rotate2(q, angle);
    float y = 0.105*sin(r.x*6.2 + seed*7.7) + 0.030*sin(r.x*13.1 - seed*3.2);
    float d = abs(r.y - y);
    float local = smoothstep(-0.20, 0.18, sin(r.x*8.4 + seed*11.0));
    return exp(-pow(d / max(width, 0.0001), 2.0)) * local;
}

// PATCH 18 — dominant neural highways. Unlike the tiled connectedBundle, each
// master axon is a single curved path with a finite envelope. A handful of
// these creates the visual hierarchy visible in the target reference.
float masterAxon(vec2 q, float angle, float offset, float seed, float halfLen, float width) {
    vec2 r = rotate2(q, angle);
    float curve = offset
                + 0.090*sin(r.x*3.1 + seed*5.7)
                + 0.032*sin(r.x*7.4 - seed*3.3)
                + 0.014*sin(r.x*13.0 + seed*2.2);
    float d = abs(r.y - curve);
    float env = 1.0 - smoothstep(halfLen*0.78, halfLen, abs(r.x));
    float organic = 0.82 + 0.18*(0.5 + 0.5*sin(r.x*11.0 + r.y*4.0 + seed*8.0));
    return exp(-pow(d / max(width, 0.0001), 2.0)) * env * organic;
}

float masterBranch(vec2 q, float angle, float offset, float seed, float halfLen, float width) {
    vec2 r = rotate2(q, angle);
    float x0 = -0.18 + 0.36*fract(seed*4.17);
    vec2 local = r - vec2(x0, offset);
    local = rotate2(local, 0.62 + 0.34*sin(seed*6.4));
    float curve = 0.050*sin(local.x*6.4 + seed*3.1);
    float d = abs(local.y - curve);
    float env = smoothstep(-0.035, 0.035, local.x) * (1.0-smoothstep(halfLen*0.72, halfLen, local.x));
    return exp(-pow(d / max(width, 0.0001), 2.0)) * env;
}


// PATCH 19 — explicit hub network. Curved links are approximated with short
// quadratic segments, but the visible result is a continuous curved fibre —
// never a straight point-to-point wireframe.
float sdSegment2(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p-a, ba = b-a;
    float h = clamp(dot(pa,ba)/max(dot(ba,ba),1e-5),0.0,1.0);
    return length(pa-ba*h);
}

vec2 quadBezier(vec2 a, vec2 c, vec2 b, float u) {
    float om = 1.0-u;
    return om*om*a + 2.0*om*u*c + u*u*b;
}

float hubLink(vec2 q, vec2 a, vec2 c, vec2 b, float width) {
    float d = 10.0;
    vec2 prev = a;
    for (int i=1; i<=5; ++i) {
        float u = float(i)/5.0;
        vec2 cur = quadBezier(a,c,b,u);
        d = min(d, sdSegment2(q,prev,cur));
        prev = cur;
    }
    return exp(-pow(d/max(width,0.0001),2.0));
}

float neuralHub(vec2 q, vec2 center, float radius) {
    float d = length(q-center);
    return exp(-pow(d/max(radius,0.0001),2.0));
}

float hubBranches(vec2 q, vec2 center, float seed, float width) {
    vec2 l = q-center;
    float a0 = seed*6.28318530718;
    vec2 r0 = rotate2(l,a0);
    vec2 r1 = rotate2(l,a0+1.05);
    vec2 r2 = rotate2(l,a0+2.10);
    vec2 r3 = rotate2(l,a0+3.14);
    vec2 r4 = rotate2(l,a0+4.20);
    vec2 r5 = rotate2(l,a0+5.25);
    float b0 = shortArm(r0,0.30, 0.55*sin(seed*7.1),width);
    float b1 = shortArm(r1,0.25,-0.48*cos(seed*5.7),width*0.88);
    float b2 = shortArm(r2,0.23, 0.44*sin(seed*9.3),width*0.78);
    float b3 = shortArm(r3,0.21,-0.38*cos(seed*8.1),width*0.72);
    float b4 = shortArm(r4,0.18, 0.34*sin(seed*11.7),width*0.64);
    float b5 = shortArm(r5,0.16,-0.30*cos(seed*10.4),width*0.58);
    return clamp(b0 + 0.88*b1 + 0.78*b2 + 0.68*b3 + 0.56*b4 + 0.48*b5,0.0,2.25);
}

// PATCH 20 — inexpensive micro-dendritic tissue. This is local and high-frequency,
// so it increases perceived cortical density without creating long orbital lines.
float microDendriteField(vec2 q, float grid, float seed, float width) {
    vec2 g = q * grid;
    vec2 cell = floor(g);
    vec2 l = fract(g) - 0.5;
    float h0 = hash21(cell + vec2(seed*13.7, seed*5.3));
    float h1 = hash21(cell + vec2(seed*7.1 + 2.4, seed*11.9 + 4.7));
    float h2 = hash21(cell + vec2(seed*3.9 + 8.1, seed*17.3 + 1.6));
    l = rotate2(l, h0*6.28318530718);
    float halfLen = 0.18 + 0.055*h1;
    float bend = mix(-0.82,0.82,h2);
    float trunk = shortTrunk(l,halfLen,bend,width);
    vec2 a = rotate2(l-vec2(-0.015,0.0), 0.82 + 0.30*h1);
    vec2 b = rotate2(l-vec2( 0.030,0.0),-(0.76 + 0.28*h2));
    vec2 c = rotate2(l-vec2( 0.065,0.0), 1.52 + 0.24*h0);
    float armA = shortArm(a,halfLen*0.66,bend*0.36,width*0.68);
    float armB = shortArm(b,halfLen*0.58,-bend*0.32,width*0.60);
    float armC = shortArm(c,halfLen*0.42,bend*0.22,width*0.52);
    return clamp(trunk + 0.82*armA + 0.70*armB + 0.50*armC,0.0,1.75);
}

// PATCH 21 — cheap layered cortex. Each call creates a broken family of thin
// organic filaments using only trigonometric warps; no cell hashes, loops or
// FBM. Three calls replace five expensive microDendriteField evaluations.
float volumetricFilamentLayer(vec2 q, float angle, float freq, float seed, float width) {
    vec2 r = rotate2(q, angle);
    float warp = 0.050*sin(r.x*5.3 + seed*5.7)
               + 0.020*sin(r.x*12.7 - seed*3.1)
               + 0.009*sin(r.x*23.0 + seed*1.9);
    float phase = (r.y - warp) * freq + seed*6.28318530718;
    float fibre = exp(-pow(abs(sin(phase)) / max(width,0.0001), 2.0));
    float crossPhase = (r.x*0.72 + r.y*0.38) * (freq*0.58) + seed*9.4;
    float branch = exp(-pow(abs(sin(crossPhase)) / max(width*1.22,0.0001), 2.0));
    float breakup = smoothstep(-0.55,0.24,
        sin(r.x*7.1 + seed*11.0) + 0.42*sin(r.y*9.2 - seed*6.7));
    return clamp((fibre + 0.36*branch) * (0.42 + 0.58*breakup),0.0,1.25);
}

vec3 neuralNode(float idx, float timeValue, float orbRadius, float motionScaleValue) {
    float h1 = hash21(vec2(idx * 1.173 + 0.17, 12.731));
    float h2 = hash21(vec2(idx * 2.417 + 4.31, 91.173));
    float z = clamp(h2 * 2.0 - 1.0, -0.985, 0.985);
    float lat = asin(z);
    float lon = 6.28318530718 * h1 + timeValue * (0.0060 + 0.0010 * mod(idx, 7.0)) * motionScaleValue;
    float cl = cos(lat);
    vec3 pos3 = vec3(cl * cos(lon), sin(lat), cl * sin(lon));
    float yaw = timeValue * (0.016 + 0.005 * motionScaleValue);
    float pitch = 0.40 + 0.045 * sin(timeValue * 0.045 + idx * 0.033);
    float cy = cos(yaw), sy = sin(yaw);
    float cp = cos(pitch), sp = sin(pitch);
    pos3 = vec3(cy * pos3.x + sy * pos3.z, pos3.y, -sy * pos3.x + cy * pos3.z);
    pos3 = vec3(pos3.x, cp * pos3.y - sp * pos3.z, sp * pos3.y + cp * pos3.z);
    float depth = clamp(pos3.z, -1.0, 1.0);
    float perspective = 0.91 + 0.16 * (depth * 0.5 + 0.5);
    vec2 q = pos3.xy * orbRadius * perspective;
    float drift = 0.0048 * sin(timeValue * 0.070 + idx * 1.913);
    q += drift * vec2(cos(idx * 2.173), sin(idx * 1.731));
    return vec3(q, depth);
}

void main() {
    vec2 p = v_uv * 2.0 - 1.0;
    float aspect = max(0.001, u_resolution.x / max(1.0, u_resolution.y));
    p.x *= aspect;

    // PATCH 13 — reference framing: larger true filament sphere, no clipping.
    p *= 0.640;
    p.y -= 0.004;

    float t = u_time;
    float r = length(p);
    float ang = atan(p.y, p.x);
    float e = clamp(u_energy, 0.0, 1.25);
    float v = clamp(u_voice, 0.0, 1.0);

    float startup = 1.0 - smoothstep(0.30, 0.70, abs(u_state - 7.0));
    float preload = 1.0 - smoothstep(0.30, 0.70, abs(u_state - 8.0));
    float bootMode = clamp(startup + preload, 0.0, 1.0);
    float boot = mix(1.0, clamp(u_boot_progress, 0.0, 1.0), bootMode);
    float sceneReveal = smoothstep(0.035, 0.100, boot);
    float particleReveal = smoothstep(0.055, 0.500, boot);
    float cortexReveal = smoothstep(0.300, 0.790, boot);
    float coreReveal = smoothstep(0.600, 0.900, boot);
    float peripheralReveal = smoothstep(0.790, 0.970, boot);
    float stableReveal = smoothstep(0.900, 0.995, boot);

    float stateDrive = clamp((u_speed - 0.45) / 1.60, 0.0, 1.0);
    float motionScale = mix(0.62, 1.05, stateDrive);
    float speakingGate = 1.0 - smoothstep(0.28, 0.72, abs(u_state - 3.0));
    float thinkingGate = max(
        1.0 - smoothstep(0.28, 0.72, abs(u_state - 1.0)),
        1.0 - smoothstep(0.28, 0.72, abs(u_state - 2.0))
    );
    float executingGate = 1.0 - smoothstep(0.28, 0.72, abs(u_state - 5.0));
    float listeningGate = 1.0 - smoothstep(0.28, 0.72, abs(u_state - 4.0));
    float speechRhythm = 0.56 + 0.44 * (
        0.50 * (0.5 + 0.5*sin(t*4.9)) +
        0.31 * (0.5 + 0.5*sin(t*8.4 + 1.2)) +
        0.19 * (0.5 + 0.5*sin(t*13.1 + 2.1))
    );
    float synapticActivity = clamp(
        speakingGate * (0.58 + 0.42*v) * speechRhythm +
        thinkingGate * 0.50 + executingGate * 0.42 + listeningGate * 0.16,
        0.0, 1.35
    );

    float rot = t * (0.024 + 0.018*e + 0.016*speakingGate) * motionScale;
    float cs = cos(rot), sn = sin(rot);
    vec2 rp = mat2(cs, -sn, sn, cs) * p;

    // ---------------------------------------------------------- dark chamber
    vec3 finalCol = vec3(0.0010, 0.0045, 0.0135);
    float chamber = exp(-dot(p * vec2(0.60, 0.78), p * vec2(0.60, 0.78)) * 0.90);
    finalCol += vec3(0.002, 0.025, 0.068) * chamber * (0.16 + 0.22*sceneReveal);
    float farGlow = exp(-pow(max(0.0, r - 0.40) / 0.70, 2.0));
    finalCol += mix(u_primary, u_secondary, 0.46) * farGlow * (0.005 + 0.010*e) * sceneReveal;

    // Sparse room particles — not part of the sphere itself.
    vec2 dustGrid = (p + vec2(1.8)) * 38.0;
    vec2 dustCell = floor(dustGrid);
    vec2 dustLocal = fract(dustGrid) - 0.5;
    float dustSeed = hash21(dustCell + vec2(3.7, 17.1));
    float dust = step(0.985, dustSeed) * exp(-dot(dustLocal, dustLocal)*220.0);
    dust *= 0.42 + 0.58*(0.5 + 0.5*sin(t*(0.22+dustSeed*0.17)+dustSeed*9.0));
    finalCol += mix(u_primary, u_secondary, dustSeed) * dust * 0.11 * particleReveal;

    // ------------------------------------------------------- neural geometry
    float neuralRadius = 0.510 * (1.0 + 0.012*sin(t*0.28)*(0.28 + 0.72*e));
    float sphereNorm = r / max(neuralRadius, 0.001);
    float inside = 1.0 - smoothstep(0.985, 1.005, sphereNorm);
    // Patch 15: hard visual containment for neural matter. The voice waveform
    // and soft halo may extend outside, but dendrites/synapses never do.
    float filamentContain = 1.0 - smoothstep(0.945, 0.982, sphereNorm);
    float interior = 1.0 - smoothstep(0.12, 0.990, sphereNorm);
    float cortexBand = exp(-pow((sphereNorm - 0.82) / 0.31, 2.0));
    float rimBand = exp(-pow((sphereNorm - 0.965) / 0.145, 2.0));
    float pseudoDepth = sqrt(max(0.0, 1.0 - min(1.0, sphereNorm*sphereNorm)));
    float centerBreathing = smoothstep(0.18, 0.37, sphereNorm);
    vec2 s = rp / max(neuralRadius, 0.001);

    // PATCH 13 — three depth layers. The sphere stays readable through its
    // centre instead of concentrating all visible matter into a peripheral ring.
    float warpX = fbm(s*2.45 + vec2(t*0.0036, -t*0.0028)) - 0.5;
    float warpY = fbm(s*2.85 - vec2(t*0.0028,  t*0.0034)) - 0.5;
    vec2 warp = vec2(warpX, warpY);

    vec2 frontP = mat2(0.94, -0.34, 0.34, 0.94) * s * (1.01 + 0.055*pseudoDepth)
                + warp*(0.078 + 0.016*synapticActivity);
    vec2 midP   = mat2(0.28, -0.96, 0.96, 0.28) * s * 0.96
                + vec2(-warp.y, warp.x)*0.058 + vec2(0.035,-0.020);
    vec2 backP  = mat2(0.78, 0.63, -0.63, 0.78) * s * (0.90 - 0.025*pseudoDepth)
                - warp*0.055 + vec2(0.10, -0.07);

    // PATCH 16 — three populations of compact dendritic clusters. The grids
    // deliberately use incommensurate scales/rotations so the result is organic
    // and volumetric instead of tiled or orbital.
    float frontA = dendriteCluster(frontP + 0.05*warp, 5.4, 0.17, 0.040);
    float frontB = dendriteCluster(rotate2(frontP, 0.74) - vec2(0.035,0.020), 7.1, 0.61, 0.034);
    float frontC = dendriteCluster(rotate2(frontP, -0.43) + vec2(0.020,-0.030), 9.3, 0.89, 0.029);

    float midA = dendriteCluster(midP - 0.04*warp, 5.9, 0.33, 0.037);
    float midB = dendriteCluster(rotate2(midP, -0.66) + vec2(0.025,0.010), 8.0, 0.72, 0.031);
    float midC = dendriteCluster(rotate2(midP, 0.39) - vec2(0.018,0.035), 10.2, 0.48, 0.026);

    float backA = dendriteCluster(backP, 5.1, 0.24, 0.043);
    float backB = dendriteCluster(rotate2(backP, 0.81) + vec2(0.030,-0.020), 7.3, 0.57, 0.035);

    // PATCH 21 — three visible depth layers replace the five expensive tiled
    // micro-dendrite fields. The rear layer is broad/subtle, the middle layer
    // carries most perceived density, and the front layer stays crisp.
    float shellBias = smoothstep(0.22,0.74,sphereNorm) * (1.0-smoothstep(0.985,1.0,sphereNorm));
    float frontLayer = volumetricFilamentLayer(frontP + 0.012*warp, -0.22, 23.0, 0.18, 0.115) * shellBias;
    float midLayer   = volumetricFilamentLayer(midP   - 0.008*warp,  0.48, 20.0, 0.47, 0.135) * shellBias;
    float backLayer  = volumetricFilamentLayer(backP,               0.91, 17.0, 0.72, 0.155) * shellBias;

    // PATCH 19 — six explicit hubs arranged across the projected neural volume.
    // The master routes are medium length and curved; smaller dendrites are
    // visually attracted to those routes instead of filling the sphere uniformly.
    vec2 h1 = vec2(-0.48,  0.30);
    vec2 h2 = vec2(-0.10,  0.43);
    vec2 h3 = vec2( 0.34,  0.24);
    vec2 h4 = vec2( 0.46, -0.20);
    vec2 h5 = vec2( 0.06, -0.43);
    vec2 h6 = vec2(-0.42, -0.22);

    float link12 = hubLink(frontP,h1,vec2(-0.31,0.48),h2,0.0130);
    float link23 = hubLink(frontP,h2,vec2( 0.12,0.54),h3,0.0120);
    float link34 = hubLink(frontP,h3,vec2( 0.54,0.05),h4,0.0112);
    float link45 = hubLink(frontP,h4,vec2( 0.30,-0.47),h5,0.0108);
    float link56 = hubLink(frontP,h5,vec2(-0.22,-0.51),h6,0.0104);
    float link61 = hubLink(midP,  h6,vec2(-0.58,0.02),h1,0.0098);
    float link25 = hubLink(midP,  h2,vec2( 0.00,-0.04),h5,0.0085);
    float link36 = hubLink(backP, h3,vec2(-0.02,-0.02),h6,0.0074);

    float frontRoutes = 0.98*link12 + 0.92*link23 + 0.84*link34 + 0.80*link45 + 0.76*link56;
    float midRoutes   = 0.58*link61 + 0.44*link25;
    float backRoutes  = 0.34*link36;

    float hub1 = neuralHub(frontP,h1,0.035);
    float hub2 = neuralHub(frontP,h2,0.037);
    float hub3 = neuralHub(frontP,h3,0.036);
    float hub4 = neuralHub(frontP,h4,0.033);
    float hub5 = neuralHub(frontP,h5,0.035);
    float hub6 = neuralHub(frontP,h6,0.034);
    float frontHubs = max(max(max(hub1,hub2),max(hub3,hub4)),max(hub5,hub6));

    float hubBranchField = 0.66*hubBranches(frontP,h1,0.17,0.0088)
                         + 0.62*hubBranches(frontP,h2,0.31,0.0082)
                         + 0.61*hubBranches(frontP,h3,0.47,0.0084)
                         + 0.58*hubBranches(frontP,h4,0.63,0.0078)
                         + 0.60*hubBranches(frontP,h5,0.79,0.0080)
                         + 0.56*hubBranches(frontP,h6,0.91,0.0076);

    // Patch 21: visible density is carried by three cheap filament layers, while
    // a reduced set of clustered dendrites adds local branching near routes.
    float routeAffinity = smoothstep(0.020,0.30,frontRoutes + 0.72*midRoutes + 0.28*frontHubs + 0.22*hubBranchField);
    float frontLocal = (0.28*frontA + 0.22*frontB + 0.14*frontC + 0.62*frontLayer)
                       * (0.60 + 0.40*routeAffinity);
    float midLocal   = (0.22*midA + 0.18*midB + 0.10*midC + 0.82*midLayer)
                       * (0.64 + 0.28*smoothstep(0.01,0.24,midRoutes+0.18*hubBranchField));
    float backLocal  = (0.14*backA + 0.10*backB + 0.72*backLayer)
                       * (0.68 + 0.20*smoothstep(0.01,0.20,backRoutes+0.14*midRoutes));

    // Keep only a hint of the old connective web for continuity.
    float webFrontA = connectedBundle(frontP + 0.020*warp, 0.18,0.40,0.21,0.0064);
    float webMidA   = connectedBundle(midP,0.66,0.43,0.34,0.0058);
    float webBackA  = connectedBundle(backP,-0.24,0.48,0.16,0.0052);
    float frontWeb = 0.13*webFrontA;
    float midWeb   = 0.11*webMidA;
    float backWeb  = 0.08*webBackA;

    float centerPresence = 0.90 + 0.10*smoothstep(0.04,0.38,sphereNorm);
    float cortexGate = cortexReveal * filamentContain * centerPresence;
    float frontFibres = (0.74*frontRoutes + 0.58*hubBranchField + 1.04*frontLocal + frontWeb) * cortexGate * (0.72 + 0.28*pseudoDepth);
    float midFibres   = (0.62*midRoutes + 0.16*hubBranchField + 1.18*midLocal + midWeb) * cortexGate * (0.58 + 0.30*pseudoDepth);
    float backFibres  = (0.54*backRoutes + 0.08*hubBranchField + 1.08*backLocal + backWeb) * cortexGate * (0.36 + 0.24*(1.0-pseudoDepth));

    // Travelling neural activation. During speech the pulse reaches a master
    // route, lights a hub, then appears in the short branches around that hub.
    float flowSeedF = hash21(floor(frontP*5.4) + vec2(3.7,9.1));
    float flowSeedM = hash21(floor(midP*5.9) + vec2(7.1,2.3));
    float flowSeedB = hash21(floor(backP*5.1) + vec2(5.9,6.7));
    float flowF = pow(0.5 + 0.5*sin(t*(1.40+2.8*speakingGate) + flowSeedF*22.0 + frontP.x*8.0),18.0);
    float flowM = pow(0.5 + 0.5*sin(t*(1.05+2.0*thinkingGate) + flowSeedM*19.0 - midP.y*7.0),19.0);
    float flowB = pow(0.5 + 0.5*sin(t*(0.82+1.6*speakingGate) + flowSeedB*17.0 + backP.x*5.0),20.0);

    float routePulseA = pow(0.5+0.5*sin(t*(1.90+4.6*speakingGate)+frontP.x*17.0-frontP.y*4.0),22.0);
    float routePulseB = pow(0.5+0.5*sin(t*(1.68+4.0*speakingGate)-frontP.x*13.0+frontP.y*7.0+1.2),22.0);
    float routePulseM = pow(0.5+0.5*sin(t*(1.30+3.0*speakingGate)+midP.y*11.0+2.2),23.0);
    float routeFlow = max(frontRoutes*max(routePulseA,routePulseB),midRoutes*routePulseM);
    routeFlow = max(routeFlow,backRoutes*flowB);

    float hubAct1 = pow(0.5+0.5*sin(t*(1.15+3.1*speakingGate)+0.0),14.0);
    float hubAct2 = pow(0.5+0.5*sin(t*(1.15+3.1*speakingGate)+1.0),14.0);
    float hubAct3 = pow(0.5+0.5*sin(t*(1.15+3.1*speakingGate)+2.0),14.0);
    float hubAct4 = pow(0.5+0.5*sin(t*(1.15+3.1*speakingGate)+3.0),14.0);
    float hubAct5 = pow(0.5+0.5*sin(t*(1.15+3.1*speakingGate)+4.0),14.0);
    float hubAct6 = pow(0.5+0.5*sin(t*(1.15+3.1*speakingGate)+5.0),14.0);
    float hubFlow = max(max(max(hub1*hubAct1,hub2*hubAct2),max(hub3*hubAct3,hub4*hubAct4)),max(hub5*hubAct5,hub6*hubAct6));
    float branchFlow = hubBranchField * max(max(hubAct1,hubAct2),max(max(hubAct3,hubAct4),max(hubAct5,hubAct6)));

    float localFlow = max(frontLayer*flowF,max(midLayer*flowM,backLayer*flowB));
    float hotFlow = synapticActivity * filamentContain * max(max(routeFlow*1.42,hubFlow*1.28),max(branchFlow*0.96,localFlow*0.18));

    vec3 coldWhite = vec3(0.94, 0.985, 1.0);
    vec3 frontCol = mix(u_primary, u_secondary, clamp(0.48 + frontP.x*0.30 - frontP.y*0.08, 0.0, 1.0));
    vec3 midCol = mix(u_primary, u_secondary, clamp(0.36 + midP.x*0.20 + midP.y*0.10, 0.0, 1.0));
    vec3 backCol = mix(u_secondary, u_primary, 0.58);
    finalCol += backCol * backFibres * (0.028 + 0.014*e);
    finalCol += midCol * midFibres * (0.092 + 0.050*e);
    finalCol += frontCol * frontFibres * (0.128 + 0.072*e);
    finalCol += mix(frontCol, coldWhite, 0.78) * hotFlow
              * (0.19 + 0.54*speakingGate + 0.18*thinkingGate);

    // ------------------------------------------------------ synaptic junctions
    // Particle cells light preferentially where curved branches overlap.
    vec2 nodeGrid = (s + vec2(1.15)) * 31.0;
    vec2 nodeCell = floor(nodeGrid);
    vec2 nodePoint = vec2(hash21(nodeCell + vec2(13.7, 2.1)), hash21(nodeCell + vec2(4.3, 19.9)));
    vec2 nodeDelta = fract(nodeGrid) - nodePoint;
    float nodeSeed = hash21(nodeCell + vec2(31.1, 8.7));
    float densityThreshold = mix(0.995, 0.40, particleReveal);
    float cellNode = step(densityThreshold, nodeSeed) * exp(-dot(nodeDelta,nodeDelta)*245.0) * filamentContain;
    float localJunctions = 0.60*frontA*frontB + 0.44*frontB*frontC + 0.40*midA*midB;
    float routeJunctions = 1.30*frontHubs + 0.88*frontRoutes*hubBranchField + 0.42*midRoutes*midLocal;
    float junctionAffinity = smoothstep(0.06, 0.52, localJunctions + routeJunctions);
    float synapseNode = cellNode * (0.18 + 0.82*junctionAffinity) * particleReveal;
    float nodePulse = 0.52 + 0.48*(0.5 + 0.5*sin(t*(0.50+nodeSeed*0.65)+nodeSeed*19.0));
    finalCol += mix(frontCol, coldWhite, 0.56) * synapseNode * nodePulse * (0.28 + 0.26*e + 0.28*synapticActivity);

    // Explicit bright hubs at route bifurcations. They are larger than ordinary
    // particle nodes and carry the speaking pulse before branches ignite.
    float hubCore = max(max(max(hub1,hub2),max(hub3,hub4)),max(hub5,hub6)) * filamentContain * cortexReveal;
    float hubHalo = max(max(max(neuralHub(frontP,h1,0.052),neuralHub(frontP,h2,0.055)),
                           max(neuralHub(frontP,h3,0.054),neuralHub(frontP,h4,0.051))),
                       max(neuralHub(frontP,h5,0.053),neuralHub(frontP,h6,0.052))) * filamentContain * cortexReveal;
    float hubActive = max(max(max(hub1*hubAct1,hub2*hubAct2),max(hub3*hubAct3,hub4*hubAct4)),max(hub5*hubAct5,hub6*hubAct6));
    finalCol += mix(frontCol,coldWhite,0.34) * hubHalo * (0.010 + 0.014*e + 0.024*synapticActivity);
    finalCol += mix(frontCol,coldWhite,0.56) * hubCore * (0.070 + 0.060*e + 0.110*synapticActivity);
    finalCol += coldWhite * hubActive * synapticActivity * (0.20 + 0.28*speakingGate);

    // Larger anchor synapses, depth-aware but with NO straight connecting lines.
    for (int i = 0; i < 40; ++i) {
        float fi = float(i);
        float nodeReveal = smoothstep(fi/40.0 - 0.070, fi/40.0 + 0.018, particleReveal);
        vec3 n0 = neuralNode(fi, t, neuralRadius*0.94, motionScale);
        float frontDepth = 0.45 + 0.55*(n0.z*0.5 + 0.5);
        float nd = length(p - n0.xy);
        float size = mix(0.0078, 0.0044, frontDepth);
        float coreNode = exp(-pow(nd/size, 2.0)) * nodeReveal * frontDepth;
        float nodeHalo = exp(-pow(nd/(size*3.0), 2.0)) * nodeReveal;
        vec3 nc = mix(u_primary, u_secondary, clamp(0.50 + n0.x/max(neuralRadius,0.001)*0.43, 0.0, 1.0));
        if (mod(fi, 7.0) < 0.5) nc = mix(nc, coldWhite, 0.66);
        finalCol += nc * nodeHalo * (0.024 + 0.022*e);
        finalCol += nc * coreNode * (0.34 + 0.28*e + 0.24*synapticActivity);
    }

    // ----------------------------------------------------- irregular membrane
    float shellNoise = fbm(s*5.0 + vec2(t*0.0030, -t*0.0025));
    float shellFine = fbm(s*11.5 - vec2(t*0.0025, t*0.0030));
    float shellCenter = 0.958 + 0.050*(shellNoise-0.5) + 0.025*(shellFine-0.5);
    float membrane = exp(-pow((sphereNorm-shellCenter)/0.090, 2.0)) * cortexReveal;
    float membraneEdge = exp(-pow((sphereNorm-(shellCenter+0.015))/0.032, 2.0)) * cortexReveal;
    float surfaceFibres = clamp(frontFibres*0.82 + midFibres*0.52 + backFibres*0.32, 0.0, 1.6) * rimBand;
    float membraneHot = clamp(surfaceFibres*0.46 + hotFlow*0.96 + junctionAffinity*synapseNode*0.78, 0.0, 1.8);
    vec3 shellCol = mix(u_primary, u_secondary, clamp(0.50 + s.x*0.36, 0.0, 1.0));
    finalCol += shellCol * membrane * (0.020 + 0.026*e);
    finalCol += mix(shellCol, coldWhite, 0.62) * membraneEdge * (0.030 + 0.048*e + 0.038*synapticActivity);
    finalCol += mix(shellCol, coldWhite, 0.74) * membraneHot * (0.030 + 0.075*speakingGate + 0.025*thinkingGate);

    // Patch 14 containment: dendritic corona stays inside the orb boundary.
    float coronaMask = smoothstep(0.80, 0.93, sphereNorm) * (1.0 - smoothstep(0.985, 1.00, sphereNorm));
    float coronaF = clamp(0.18*frontFibres + 0.12*midFibres + 0.08*backFibres, 0.0, 0.58) * coronaMask * peripheralReveal;
    finalCol += shellCol * coronaF * (0.060 + 0.048*e);
    finalCol += coldWhite * coronaF * hotFlow * (0.040 + 0.120*speakingGate);

    // Detached motes remain inside the living membrane.
    vec2 moteGrid = (p + vec2(1.7)) * 48.0;
    vec2 moteCell = floor(moteGrid);
    vec2 moteLocal = fract(moteGrid) - 0.5;
    float moteSeed = hash21(moteCell + vec2(43.1,7.7));
    float moteEnvelope = smoothstep(neuralRadius*0.76, neuralRadius*0.90, r)
                       * (1.0-smoothstep(neuralRadius*0.945, neuralRadius*0.985, r));
    float mote = step(0.940, moteSeed) * exp(-dot(moteLocal,moteLocal)*250.0) * moteEnvelope * peripheralReveal;
    finalCol += mix(u_primary,u_secondary,hash21(moteCell+9.1)) * mote * (0.24 + 0.27*e + 0.14*synapticActivity);

    // ------------------------------------------------------ volumetric center
    // Dark cognitive cavity plus a controlled luminous core behind the SVG A.
    float innerNoise = fbm(s*4.5 + vec2(t*0.0020,-t*0.0015));
    float innerCloud = interior * pseudoDepth * (0.32 + 0.68*innerNoise) * coreReveal;
    float coreAura = exp(-pow(sphereNorm/0.46, 2.0)) * coreReveal;
    float coreHalo = exp(-pow((sphereNorm-0.34)/0.24,2.0)) * coreReveal;
    finalCol += mix(vec3(0.015,0.075,0.18), u_primary, 0.52) * innerCloud * (0.024 + 0.030*e);
    finalCol += mix(u_primary,u_secondary,0.46) * coreAura * (0.020 + 0.026*e + 0.020*synapticActivity);
    finalCol += mix(u_primary,coldWhite,0.36) * coreHalo * (0.012 + 0.018*e);

    // ---------------------------------------------------- neural voice signal
    // Reference waveform sits behind the orb instead of cutting it in half.
    float signalAmp = 0.012 + 0.030*speakingGate*(0.42+0.58*v) + 0.010*thinkingGate;
    float signalY = signalAmp * (
        0.52*sin(p.x*23.0 + t*(0.34+0.34*speakingGate)) +
        0.29*sin(p.x*51.0 - t*(0.24+0.24*speakingGate)+0.7) +
        0.14*sin(p.x*91.0 + t*0.16) +
        0.08*sin(p.x*147.0 - t*(0.30+0.55*speakingGate))
    );
    float signalCore = lineGlow(p.y-signalY, 0.00155);
    float signalHalo = lineGlow(p.y-signalY, 0.0068 + 0.004*speakingGate);
    float outsideOrb = smoothstep(neuralRadius*0.70, neuralRadius*1.05, abs(p.x));
    float waveformOcclusion = mix(0.24, 1.0, outsideOrb);
    float waveStrength = (signalCore*(0.36+0.50*speakingGate) + signalHalo*(0.060+0.115*speakingGate)) * waveformOcclusion * peripheralReveal;
    vec3 waveCol = mix(vec3(0.10,0.78,1.0), vec3(0.87,0.23,1.0), clamp(0.50+p.x*0.38,0.0,1.0));
    finalCol += waveCol * waveStrength;

    // ------------------------------------------------ holographic neural pool
    // PATCH 19 — raised multi-plane pedestal. Ring centers are vertically
    // separated so the base reads as stacked holographic geometry rather than
    // one thin line hidden near the input bar.
    float baseY = p.y + neuralRadius*1.10;
    float er1 = sqrt(pow(p.x/(neuralRadius*1.46),2.0) + pow(baseY/(neuralRadius*0.145),2.0));
    float er2 = sqrt(pow(p.x/(neuralRadius*1.22),2.0) + pow((baseY+neuralRadius*0.040)/(neuralRadius*0.120),2.0));
    float er3 = sqrt(pow(p.x/(neuralRadius*0.99),2.0) + pow((baseY+neuralRadius*0.078)/(neuralRadius*0.098),2.0));
    float er4 = sqrt(pow(p.x/(neuralRadius*0.77),2.0) + pow((baseY+neuralRadius*0.112)/(neuralRadius*0.078),2.0));
    float er5 = sqrt(pow(p.x/(neuralRadius*0.56),2.0) + pow((baseY+neuralRadius*0.142)/(neuralRadius*0.060),2.0));
    float er6 = sqrt(pow(p.x/(neuralRadius*0.36),2.0) + pow((baseY+neuralRadius*0.166)/(neuralRadius*0.045),2.0));
    float poolRings = ringBand(er1,1.0,0.020) + 0.90*ringBand(er2,1.0,0.022)
                    + 0.76*ringBand(er3,1.0,0.025) + 0.62*ringBand(er4,1.0,0.029)
                    + 0.48*ringBand(er5,1.0,0.034) + 0.34*ringBand(er6,1.0,0.040);
    float poolGlow = exp(-pow((baseY+neuralRadius*0.065)/(neuralRadius*0.24),2.0))
                   * (1.0-smoothstep(neuralRadius*0.25,neuralRadius*1.76,abs(p.x)));
    vec3 poolCol = mix(vec3(0.08,0.66,1.0),vec3(0.76,0.20,1.0),clamp(0.50+p.x/(neuralRadius*2.2),0.0,1.0));
    finalCol += poolCol * poolRings * (0.40 + 0.25*e) * peripheralReveal;
    finalCol += poolCol * poolGlow * (0.13 + 0.13*e) * peripheralReveal;
    float poolCore = exp(-pow(p.x/(neuralRadius*0.46),2.0)) * exp(-pow((baseY+neuralRadius*0.13)/(neuralRadius*0.060),2.0));
    float verticalReflect = exp(-pow(p.x/(neuralRadius*0.25),2.0))
                          * exp(-pow((baseY-neuralRadius*0.12)/(neuralRadius*0.42),2.0));
    finalCol += mix(poolCol,coldWhite,0.58) * poolCore * (0.26 + 0.20*e) * peripheralReveal;
    finalCol += poolCol * verticalReflect * (0.042 + 0.060*e) * peripheralReveal;

    vec2 baseDustGrid = vec2((p.x+1.6)*42.0, (baseY+0.18)*70.0);
    vec2 baseDustCell = floor(baseDustGrid);
    vec2 baseDustLocal = fract(baseDustGrid)-0.5;
    float baseSeed = hash21(baseDustCell+vec2(11.0,39.0));
    float baseDust = step(0.968,baseSeed)*exp(-dot(baseDustLocal,baseDustLocal)*190.0)
                   * exp(-pow(baseY/(neuralRadius*0.25),2.0))
                   * (1.0-smoothstep(neuralRadius*0.35,neuralRadius*1.70,abs(p.x)));
    finalCol += poolCol * baseDust * (0.20+0.21*e) * peripheralReveal;

    // Subtle curved orbital traces from the reference; never straight geometry.
    float orbit1 = ringBand(sphereNorm,0.89,0.010) * arcMask(ang,7.0,t*0.025,0.76);
    float orbit2 = ringBand(sphereNorm,0.955,0.007) * arcMask(ang,11.0,-t*0.020+1.4,0.82);
    finalCol += mix(u_primary,u_secondary,0.55) * (orbit1*0.030 + orbit2*0.020) * stableReveal * filamentContain;

    float matureHalo = exp(-pow((r-neuralRadius*0.99)/(neuralRadius*0.22),2.0));
    finalCol += mix(u_primary,u_secondary,0.52) * matureHalo * (0.020+0.024*e) * stableReveal;

    gl_FragColor = vec4(finalCol, 1.0);
}
"""


# V9 cinematic post-processing. The reactor is first rendered to an off-screen
# framebuffer, bright energy is extracted/blurred at half resolution, then the
# original scene and bloom are composited back into QOpenGLWidget's framebuffer.
BLOOM_HORIZONTAL_SHADER = r"""
#version 120
varying vec2 v_uv;
uniform sampler2D u_source;
uniform vec2 u_texel;
uniform float u_threshold;
void main() {
    vec3 sum = vec3(0.0);
    float weights[5];
    weights[0]=0.227027; weights[1]=0.1945946; weights[2]=0.1216216; weights[3]=0.054054; weights[4]=0.016216;
    for (int i=-4; i<=4; ++i) {
        int ai = i < 0 ? -i : i;
        vec3 c = texture2D(u_source, v_uv + vec2(float(i) * u_texel.x * 2.05, 0.0)).rgb;
        float lum = max(c.r, max(c.g, c.b));
        vec3 bright = c * smoothstep(u_threshold, u_threshold + 0.34, lum);
        sum += bright * weights[ai];
    }
    gl_FragColor = vec4(sum, 1.0);
}
"""

BLOOM_VERTICAL_SHADER = r"""
#version 120
varying vec2 v_uv;
uniform sampler2D u_source;
uniform vec2 u_texel;
void main() {
    vec3 sum = vec3(0.0);
    float weights[5];
    weights[0]=0.227027; weights[1]=0.1945946; weights[2]=0.1216216; weights[3]=0.054054; weights[4]=0.016216;
    for (int i=-4; i<=4; ++i) {
        int ai = i < 0 ? -i : i;
        sum += texture2D(u_source, v_uv + vec2(0.0, float(i) * u_texel.y * 2.05)).rgb * weights[ai];
    }
    gl_FragColor = vec4(sum, 1.0);
}
"""

COMPOSITE_SHADER = r"""
#version 120
varying vec2 v_uv;
uniform sampler2D u_scene;
uniform sampler2D u_bloom;
uniform float u_bloom_strength;
uniform float u_exposure;
void main() {
    vec3 scene = texture2D(u_scene, v_uv).rgb;
    vec3 bloom = texture2D(u_bloom, v_uv).rgb;
    // Layered glow gives the reference's cinematic energy without washing out
    // the dark nucleus or the fine telemetry lines.
    vec3 hdr = scene + bloom * u_bloom_strength;
    hdr += bloom * bloom * 0.22;
    vec3 mapped = vec3(1.0) - exp(-hdr * u_exposure);
    mapped = pow(max(mapped, vec3(0.0)), vec3(0.94));
    gl_FragColor = vec4(mapped, 1.0);
}
"""


class OpenGLOrbSurface(QOpenGLWidget):
    initialized = Signal()
    initialization_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
        fmt.setVersion(2, 1)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
        fmt.setSwapInterval(1)
        self.setFormat(fmt)
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        self.setAutoFillBackground(False)

        self._program: QOpenGLShaderProgram | None = None
        self._bloom_h_program: QOpenGLShaderProgram | None = None
        self._bloom_v_program: QOpenGLShaderProgram | None = None
        self._composite_program: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._scene_fbo = None
        self._bloom_a_fbo = None
        self._bloom_b_fbo = None
        self._fbo_size = (0, 0)
        self._multipass_ready = False
        self._post_uniforms: dict[str, dict[str, int]] = {}
        self._post_positions: dict[str, int] = {}
        self._bloom_scale = 0.50
        self._state = "IDLE"
        self._state_code = 0.0
        self._target_state_code = 0.0
        self._energy = STATE_TARGETS["IDLE"][2]
        self._target_energy = self._energy
        self._voice = 0.0
        self._target_voice = 0.0
        self._speed = STATE_TARGETS["IDLE"][3]
        self._target_speed = self._speed
        self._primary = STATE_TARGETS["IDLE"][0]
        self._secondary = STATE_TARGETS["IDLE"][1]
        self._target_primary = self._primary
        self._target_secondary = self._secondary
        self._mood = "neutral"
        self._started = False
        self._failed = False
        # Visual time is intentionally decoupled from wall time. If CUDA/XTTS
        # briefly stalls the GUI/GPU, the animation resumes from the next small
        # simulation step instead of jumping hundreds of milliseconds forward.
        self._elapsed = 0.0
        self._uniform_locations: dict[str, int] = {}
        self._position_location = -1

        # v0.7.0.15.6.1: drive shader time from a monotonic clock instead of
        # accumulating nominal timer intervals.  This avoids a visually frozen
        # reactor when Windows coalesces or delays Qt timer callbacks.
        self._clock = QElapsedTimer()
        self._clock.start()
        self._last_tick_ms = 0
        self._timer_ticks = 0
        self._paint_frames = 0
        self._last_diag_ms = 0
        self._last_diag_frames = 0
        self._motion_baseline: list[tuple[int, int, int]] | None = None
        self._dynamic_self_test_scheduled = False
        self._dynamic_motion_score = -1.0
        self._dynamic_low_motion_confirmations = 0
        # v0.7.1.3.6.8: the cinematic OpenGL orb is AURA's protected visual
        # baseline. A low framebuffer motion score is a performance signal,
        # never proof that the shader/context is unusable. Only hard OpenGL
        # failures may trigger the QPainter survival fallback.
        self._visual_quality_tier = "cinematic-high"
        self._visual_quality_recovery_samples = 0
        self._preload_visual_safety = False
        self._preload_progress = 1.0
        self._preload_previous_tier = "cinematic-high"
        self._gl_error_checks_remaining = 8
        self._last_paint_clock_ms = -1
        self._frame_gaps_ms = deque(maxlen=360)
        self._max_frame_gap_ms = 0.0

        # V4: start close to 60 Hz, then align to a divisor of the real display
        # refresh rate in showEvent(). 45 FPS on a 60/120/144 Hz panel creates
        # visible cadence judder even when the shader itself is fast.
        fps = max(30, min(90, int(settings.OPENGL_ORB_FPS)))
        self._target_fps = float(fps)
        self._display_refresh_hz = 0.0
        self._frame_interval_ms = max(8, int(1000.0 / self._target_fps))
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(self._frame_interval_ms)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    @staticmethod
    def _mix_color(a, b, amount: float):
        amount = max(0.0, min(1.0, float(amount)))
        return tuple(float(x) + (float(y) - float(x)) * amount for x, y in zip(a, b))

    def _refresh_state_palette(self) -> None:
        primary, secondary, _energy, _speed = STATE_TARGETS[self._state]
        mood = "alert" if self._state == "ERROR" else self._mood
        mood_primary, mood_secondary = mood_palette(mood)
        strength = 0.88 if self._state == "ERROR" else MOOD_STRENGTH.get(mood, 0.0)
        self._target_primary = self._mix_color(primary, mood_primary, strength)
        self._target_secondary = self._mix_color(secondary, mood_secondary, strength)

    def set_mood(self, mood: str) -> None:
        self._mood = normalize_mood(mood)
        self._refresh_state_palette()
        logger.info("AURA neural mood=%s", self._mood)
        self.update()

    def set_state(self, state: str) -> None:
        state = state if state in STATE_TARGETS else "IDLE"
        self._state = state
        _primary, _secondary, energy, speed = STATE_TARGETS[state]
        self._refresh_state_palette()
        self._target_energy = float(energy)
        self._target_speed = float(speed)
        # Patch 22.2: SPEAKING no longer fakes a full-scale voice envelope.
        # Actual PCM callbacks drive the target; leaving SPEAKING clears it.
        if state != "SPEAKING":
            self._target_voice = 0.0
        self._target_state_code = float({
            "IDLE": 0, "THINKING": 1, "PROCESSING": 2, "SPEAKING": 3,
            "LISTENING": 4, "EXECUTING": 5, "ERROR": 6, "STARTUP": 7, "PRELOAD": 8,
        }.get(state, 0))
        self.update()


    def set_preload_progress(self, percent: int) -> None:
        self._preload_progress = max(0.0, min(1.0, float(percent) / 100.0))
        self.update()

    def set_preload_visual_safety(self, active: bool) -> None:
        """Reduce OpenGL pressure during XTTS cold-load without changing AURA's orb.

        The same cinematic shader/baseline stays active. We only reduce cadence
        and suspend framebuffer readback diagnostics while the CUDA model is
        loading, because grabFramebuffer() can force a synchronous GPU/driver
        readback at the worst possible moment on hybrid-GPU laptops.
        """
        active = bool(active)
        if active == self._preload_visual_safety:
            return
        self._preload_visual_safety = active
        if active:
            self._preload_previous_tier = self._visual_quality_tier
            self._motion_baseline = None
            self._dynamic_low_motion_confirmations = 0
            target = min(18.0, max(12.0, float(self._target_fps)))
            interval = max(40, int(1000.0 / max(1.0, target)))
            self._target_fps = target
            self._frame_interval_ms = interval
            self._timer.setInterval(interval)
            logger.info(
                "OpenGL safe preload visual lock active target_fps=%.1f interval=%dms baseline=cinematic-opengl-v1 framebuffer_selftest=suspended",
                target, interval,
            )
        else:
            tier = self._preload_previous_tier if self._preload_previous_tier in {"cinematic-high", "cinematic-balanced", "cinematic-eco"} else "cinematic-high"
            self._set_adaptive_visual_quality(tier, reason="xtts-preload-finished")
            self._motion_baseline = None
            logger.info(
                "OpenGL safe preload visual lock released quality=%s baseline=cinematic-opengl-v1",
                self._visual_quality_tier,
            )

    def restore_post_preload_cinematic(self) -> None:
        """Restore AURA's full cinematic cadence after a successful XTTS preload.

        Boot-time motion diagnostics are intentionally conservative and may have
        selected balanced/eco just before the preload safety lock engages.  That
        tier is transient startup telemetry, not a post-boot quality decision.
        A successful XTTS warm-up therefore returns to the protected cinematic
        baseline and re-synchronises the cadence with the actual display refresh.
        """
        self._preload_previous_tier = "cinematic-high"
        self._dynamic_low_motion_confirmations = 0
        self._visual_quality_recovery_samples = 0
        self._motion_baseline = None
        self._set_adaptive_visual_quality("cinematic-high", reason="xtts-post-preload-restore")
        logger.info(
            "OpenGL Orb post-preload restore quality=%s target_fps=%.2f interval=%dms preload_visual_mode=%s baseline=cinematic-opengl-v1",
            self._visual_quality_tier, self._target_fps, self._frame_interval_ms, self._preload_visual_safety,
        )

    def set_voice_amplitude(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        # PCM is already compressed in xtts_tts; this final perceptual curve
        # makes normal syllables visible while preserving headroom for accents.
        self._target_voice = value ** 0.74 if value > 0.0 else 0.0

    def animation_snapshot(self) -> dict[str, float | int | bool | str]:
        gaps = sorted(self._frame_gaps_ms)
        p95_gap = gaps[int(0.95 * (len(gaps) - 1))] if gaps else 0.0
        return {
            "state": self._state,
            "shader_time": float(self._elapsed),
            "timer_ticks": int(self._timer_ticks),
            "paint_frames": int(self._paint_frames),
            "timer_active": bool(self._timer.isActive()),
            "visible": bool(self.isVisible()),
            "started": bool(self._started and not self._failed),
            "target_fps": float(self._target_fps),
            "visual_quality": self._visual_quality_tier,
            "visual_baseline": "cinematic-opengl-v1",
            "preload_visual_safety": bool(self._preload_visual_safety),
            "preload_progress": float(self._preload_progress),
            "display_refresh_hz": float(self._display_refresh_hz),
            "frame_gap_p95_ms": float(p95_gap),
            "max_frame_gap_ms": float(self._max_frame_gap_ms),
        }

    def _tick(self) -> None:
        now_ms = int(self._clock.elapsed())
        if self._last_tick_ms <= 0:
            dt = self._frame_interval_ms / 1000.0
        else:
            dt = max(0.001, min(0.250, (now_ms - self._last_tick_ms) / 1000.0))
        self._last_tick_ms = now_ms
        # Clamp simulation catch-up. Long model-load stalls must not make the
        # plasma teleport forward when the UI thread becomes available again.
        sim_dt = min(dt, 1.0 / 30.0)
        self._elapsed += sim_dt
        self._timer_ticks += 1

        # V4 cinematic easing. State changes no longer snap colors/state-code on
        # a single frame; every visual parameter crosses over continuously.
        def smooth_alpha(rate: float) -> float:
            return 1.0 - math.exp(-max(0.0, rate) * sim_dt)

        energy_alpha = smooth_alpha(3.1)
        voice_alpha = smooth_alpha(30.0 if self._target_voice > self._voice else 5.2)
        speed_alpha = smooth_alpha(2.5)
        color_alpha = smooth_alpha(2.8)
        state_alpha = smooth_alpha(3.2)
        self._energy += (self._target_energy - self._energy) * energy_alpha
        self._voice += (self._target_voice - self._voice) * voice_alpha
        self._speed += (self._target_speed - self._speed) * speed_alpha
        self._state_code += (self._target_state_code - self._state_code) * state_alpha
        self._primary = tuple(a + (b - a) * color_alpha for a, b in zip(self._primary, self._target_primary))
        self._secondary = tuple(a + (b - a) * color_alpha for a, b in zip(self._secondary, self._target_secondary))

        # Do not gate update() on isVisible(): on some Windows/QOpenGLWidget
        # compositions the child can report a transient false visibility state
        # even though its framebuffer is currently on screen. Qt will cheaply
        # discard updates for genuinely hidden widgets.
        self.update()

        if now_ms - self._last_diag_ms >= 15000:
            elapsed_diag = max(1, now_ms - self._last_diag_ms)
            rendered = self._paint_frames - self._last_diag_frames
            fps = rendered * 1000.0 / elapsed_diag
            gaps = sorted(self._frame_gaps_ms)
            p95_gap = gaps[int(0.95 * (len(gaps) - 1))] if gaps else 0.0
            logger.info(
                "OpenGL Orb animation state=%s shader_time=%.2fs timer_ticks=%d paint_frames=%d fps=%.1f frame_gap_p95=%.1fms max_gap=%.1fms visible=%s",
                self._state, self._elapsed, self._timer_ticks, self._paint_frames, fps,
                p95_gap, self._max_frame_gap_ms, self.isVisible(),
            )
            self._max_frame_gap_ms = 0.0
            if self._started and self.isVisible() and rendered < 2:
                logger.warning(
                    "OpenGL Orb animation watchdog: timer actif mais rendu quasi figé ticks=%d frames=%d",
                    self._timer_ticks, rendered,
                )
            self._last_diag_ms = now_ms
            self._last_diag_frames = self._paint_frames

    def _compile_program(self, fragment_shader: str, uniform_names: tuple[str, ...]) -> tuple[QOpenGLShaderProgram, dict[str, int], int]:
        program = QOpenGLShaderProgram(self)
        if not program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, VERTEX_SHADER):
            raise RuntimeError(f"vertex shader: {program.log()}")
        if not program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, fragment_shader):
            raise RuntimeError(f"fragment shader: {program.log()}")
        if not program.link():
            raise RuntimeError(f"shader link: {program.log()}")
        uniforms: dict[str, int] = {}
        for name in uniform_names:
            location = int(program.uniformLocation(name.encode("ascii")))
            if location < 0:
                raise RuntimeError(f"uniform OpenGL introuvable: {name}")
            uniforms[name] = location
        position = int(program.attributeLocation(b"a_position"))
        if position < 0:
            raise RuntimeError("attribut OpenGL introuvable: a_position")
        return program, uniforms, position

    def _configure_texture(self, funcs, texture_id: int) -> None:
        if texture_id <= 0 or not hasattr(funcs, "glBindTexture"):
            return
        funcs.glBindTexture(_GL_TEXTURE_2D, int(texture_id))
        if hasattr(funcs, "glTexParameteri"):
            funcs.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_MIN_FILTER, _GL_LINEAR)
            funcs.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_MAG_FILTER, _GL_LINEAR)
        funcs.glBindTexture(_GL_TEXTURE_2D, 0)

    def _ensure_framebuffers(self) -> bool:
        if QOpenGLFramebufferObject is None:
            self._multipass_ready = False
            return False
        w = max(2, int(self.width()))
        h = max(2, int(self.height()))
        if self._multipass_ready and self._fbo_size == (w, h):
            return True
        try:
            fmt = QOpenGLFramebufferObjectFormat() if QOpenGLFramebufferObjectFormat is not None else None
            if fmt is not None and hasattr(fmt, "setTextureTarget"):
                fmt.setTextureTarget(_GL_TEXTURE_2D)
            bw = max(2, int(w * self._bloom_scale))
            bh = max(2, int(h * self._bloom_scale))
            self._scene_fbo = QOpenGLFramebufferObject(w, h, fmt) if fmt is not None else QOpenGLFramebufferObject(w, h)
            self._bloom_a_fbo = QOpenGLFramebufferObject(bw, bh, fmt) if fmt is not None else QOpenGLFramebufferObject(bw, bh)
            self._bloom_b_fbo = QOpenGLFramebufferObject(bw, bh, fmt) if fmt is not None else QOpenGLFramebufferObject(bw, bh)
            valid = all(
                fbo is not None and bool(fbo.isValid())
                for fbo in (self._scene_fbo, self._bloom_a_fbo, self._bloom_b_fbo)
            )
            if not valid:
                raise RuntimeError("framebuffer OpenGL cinematic invalide")
            ctx = self.context()
            funcs = ctx.functions() if ctx is not None else None
            if funcs is not None:
                for fbo in (self._scene_fbo, self._bloom_a_fbo, self._bloom_b_fbo):
                    self._configure_texture(funcs, int(fbo.texture()))
            self._fbo_size = (w, h)
            self._multipass_ready = True
            logger.info("OpenGL cinematic multipass ready scene=%dx%d bloom=%dx%d", w, h, bw, bh)
            return True
        except Exception as exc:
            self._scene_fbo = None
            self._bloom_a_fbo = None
            self._bloom_b_fbo = None
            self._fbo_size = (0, 0)
            self._multipass_ready = False
            logger.warning("OpenGL cinematic multipass indisponible; rendu direct conservé: %s", exc)
            return False

    def _bind_default_framebuffer(self, funcs) -> None:
        target = int(self.defaultFramebufferObject())
        if hasattr(funcs, "glBindFramebuffer"):
            funcs.glBindFramebuffer(_GL_FRAMEBUFFER, target)
            return
        ctx = self.context()
        extra = ctx.extraFunctions() if ctx is not None and hasattr(ctx, "extraFunctions") else None
        if extra is not None and hasattr(extra, "glBindFramebuffer"):
            extra.glBindFramebuffer(_GL_FRAMEBUFFER, target)

    def _draw_geometry(self, program: QOpenGLShaderProgram, position_location: int) -> None:
        if self._vbo is None:
            return
        program.bind()
        self._vbo.bind()
        program.enableAttributeArray(position_location)
        program.setAttributeBuffer(position_location, _GL_FLOAT, 0, 2, 0)

    def _finish_geometry(self, program: QOpenGLShaderProgram, position_location: int) -> None:
        program.disableAttributeArray(position_location)
        if self._vbo is not None:
            self._vbo.release()
        program.release()

    def _render_scene(self, funcs, width: int, height: int) -> None:
        program = self._program
        if program is None:
            return
        self._draw_geometry(program, self._position_location)
        uniforms = self._uniform_locations
        if all(hasattr(funcs, name) for name in ("glUniform1f", "glUniform2f", "glUniform3f")):
            funcs.glUniform2f(uniforms["u_resolution"], float(width), float(height))
            funcs.glUniform1f(uniforms["u_time"], float(self._elapsed))
            funcs.glUniform1f(uniforms["u_energy"], float(self._energy))
            voice = max(0.0, min(1.0, self._voice))
            funcs.glUniform1f(uniforms["u_voice"], float(voice))
            funcs.glUniform1f(uniforms["u_speed"], float(self._speed))
            funcs.glUniform3f(uniforms["u_primary"], *[float(v) for v in self._primary])
            funcs.glUniform3f(uniforms["u_secondary"], *[float(v) for v in self._secondary])
            funcs.glUniform1f(uniforms["u_state"], float(self._state_code))
            funcs.glUniform1f(uniforms["u_boot_progress"], float(self._preload_progress))
        else:
            program.setUniformValue(uniforms["u_resolution"], QVector2D(float(width), float(height)))
            program.setUniformValue(uniforms["u_time"], float(self._elapsed))
            program.setUniformValue(uniforms["u_energy"], float(self._energy))
            voice = max(0.0, min(1.0, self._voice))
            program.setUniformValue(uniforms["u_voice"], float(voice))
            program.setUniformValue(uniforms["u_speed"], float(self._speed))
            program.setUniformValue(uniforms["u_primary"], QVector3D(*[float(v) for v in self._primary]))
            program.setUniformValue(uniforms["u_secondary"], QVector3D(*[float(v) for v in self._secondary]))
            program.setUniformValue(uniforms["u_state"], float(self._state_code))
            program.setUniformValue(uniforms["u_boot_progress"], float(self._preload_progress))
        funcs.glDrawArrays(_GL_TRIANGLE_STRIP, 0, 4)
        self._finish_geometry(program, self._position_location)

    def _bind_texture_unit(self, funcs, texture_id: int, unit: int) -> None:
        if hasattr(funcs, "glActiveTexture"):
            funcs.glActiveTexture(_GL_TEXTURE0 + int(unit))
        funcs.glBindTexture(_GL_TEXTURE_2D, int(texture_id))

    def _render_bloom_pass(self, funcs, program: QOpenGLShaderProgram, key: str, texture_id: int, texel_x: float, texel_y: float, threshold: float | None = None) -> None:
        uniforms = self._post_uniforms[key]
        position = self._post_positions[key]
        self._draw_geometry(program, position)
        self._bind_texture_unit(funcs, texture_id, 0)
        funcs.glUniform1i(uniforms["u_source"], 0)
        funcs.glUniform2f(uniforms["u_texel"], float(texel_x), float(texel_y))
        if threshold is not None and "u_threshold" in uniforms:
            funcs.glUniform1f(uniforms["u_threshold"], float(threshold))
        funcs.glDrawArrays(_GL_TRIANGLE_STRIP, 0, 4)
        funcs.glBindTexture(_GL_TEXTURE_2D, 0)
        self._finish_geometry(program, position)

    def _render_composite(self, funcs, scene_texture: int, bloom_texture: int) -> None:
        program = self._composite_program
        if program is None:
            return
        uniforms = self._post_uniforms["composite"]
        position = self._post_positions["composite"]
        self._draw_geometry(program, position)
        self._bind_texture_unit(funcs, scene_texture, 0)
        funcs.glUniform1i(uniforms["u_scene"], 0)
        self._bind_texture_unit(funcs, bloom_texture, 1)
        funcs.glUniform1i(uniforms["u_bloom"], 1)
        # Slightly stronger glow in active states, restrained in IDLE.
        bloom_strength = 0.88 + 0.34 * min(1.0, self._energy) + 0.18 * self._voice
        exposure = 1.06 + 0.08 * min(1.0, self._energy)
        funcs.glUniform1f(uniforms["u_bloom_strength"], float(bloom_strength))
        funcs.glUniform1f(uniforms["u_exposure"], float(exposure))
        funcs.glDrawArrays(_GL_TRIANGLE_STRIP, 0, 4)
        if hasattr(funcs, "glActiveTexture"):
            funcs.glActiveTexture(_GL_TEXTURE0 + 1)
        funcs.glBindTexture(_GL_TEXTURE_2D, 0)
        if hasattr(funcs, "glActiveTexture"):
            funcs.glActiveTexture(_GL_TEXTURE0)
        funcs.glBindTexture(_GL_TEXTURE_2D, 0)
        self._finish_geometry(program, position)

    @staticmethod
    def _decode_gl_string(value) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace").strip()
        try:
            raw = bytes(value)
            return raw.decode("utf-8", errors="replace").strip()
        except Exception:
            return str(value).strip()

    def _register_gl_hardware_probe(self, funcs) -> None:
        getter = getattr(funcs, "glGetString", None)
        if not callable(getter):
            logger.info("OpenGL renderer probe unavailable: glGetString absent")
            return
        try:
            vendor = self._decode_gl_string(getter(_GL_VENDOR))
            renderer = self._decode_gl_string(getter(_GL_RENDERER))
            version = self._decode_gl_string(getter(_GL_VERSION))
            hardware_runtime.register_gl(vendor=vendor, renderer=renderer, version=version)
        except Exception as exc:
            logger.info("OpenGL renderer probe unavailable: %s", exc)

    def initializeGL(self) -> None:
        try:
            ctx = self.context()
            if ctx is None or not ctx.isValid():
                raise RuntimeError("contexte OpenGL Qt invalide")
            funcs = ctx.functions()
            funcs.initializeOpenGLFunctions()
            self._register_gl_hardware_probe(funcs)
            funcs.glClearColor(0.0025, 0.0105, 0.0260, 1.0)

            scene_shader = FOCUS_FRAGMENT_SHADER if UI_FOCUS_MODE else FRAGMENT_SHADER
            scene_program, uniform_locations, position_location = self._compile_program(
                scene_shader,
                ("u_resolution", "u_time", "u_energy", "u_voice", "u_speed", "u_primary", "u_secondary", "u_state", "u_boot_progress"),
            )

            vertices = array.array("f", (-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0))
            vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            if not vbo.create():
                raise RuntimeError("création VBO impossible")
            vbo.bind()
            vbo.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw)
            vbo.allocate(vertices.tobytes(), len(vertices) * vertices.itemsize)
            vbo.release()

            self._program = scene_program
            self._vbo = vbo
            self._uniform_locations = uniform_locations
            self._position_location = position_location

            # Patch 22 UI Focus Mode: no cinematic FBO/bloom stack is needed for
            # logo + waveform. The full post stack remains available when the orb
            # is re-enabled by switching UI_FOCUS_MODE back to False.
            if UI_FOCUS_MODE:
                self._bloom_h_program = None
                self._bloom_v_program = None
                self._composite_program = None
                self._multipass_ready = False
                logger.info("AURA UI Focus Mode active: orb/cortex/particles/base disabled; logo+waveform only")
            else:
                try:
                    self._bloom_h_program, self._post_uniforms["bloom_h"], self._post_positions["bloom_h"] = self._compile_program(
                        BLOOM_HORIZONTAL_SHADER, ("u_source", "u_texel", "u_threshold")
                    )
                    self._bloom_v_program, self._post_uniforms["bloom_v"], self._post_positions["bloom_v"] = self._compile_program(
                        BLOOM_VERTICAL_SHADER, ("u_source", "u_texel")
                    )
                    self._composite_program, self._post_uniforms["composite"], self._post_positions["composite"] = self._compile_program(
                        COMPOSITE_SHADER, ("u_scene", "u_bloom", "u_bloom_strength", "u_exposure")
                    )
                    self._ensure_framebuffers()
                except Exception as post_exc:
                    self._bloom_h_program = None
                    self._bloom_v_program = None
                    self._composite_program = None
                    self._multipass_ready = False
                    logger.warning("OpenGL cinematic post-processing désactivé; rendu direct conservé: %s", post_exc)

            self._started = True
            actual = ctx.format()
            logger.info(
                "OpenGL Visual Stage initialized version=%d.%d profile=%s configured_fps=%d cinematic=%s",
                actual.majorVersion(), actual.minorVersion(), getattr(actual.profile(), "name", str(actual.profile())),
                max(30, min(90, int(settings.OPENGL_ORB_FPS))), self._multipass_ready,
            )
            self.initialized.emit()
            if not self._dynamic_self_test_scheduled:
                self._dynamic_self_test_scheduled = True
                QTimer.singleShot(850, self._capture_motion_baseline)
                QTimer.singleShot(3350, self._validate_dynamic_output)
        except Exception as exc:
            self._failed = True
            logger.warning("OpenGL Orb initialization failed; QPainter fallback: %s", exc, exc_info=True)
            self.initialization_failed.emit(str(exc))

    def resizeGL(self, width: int, height: int) -> None:
        if self._started or self._program is not None:
            self._ensure_framebuffers()

    def paintGL(self) -> None:
        if self._failed or not self._started or self._program is None or self._vbo is None:
            return
        self._paint_frames += 1
        paint_clock_ms = int(self._clock.elapsed())
        if self._last_paint_clock_ms >= 0:
            gap = max(0.0, float(paint_clock_ms - self._last_paint_clock_ms))
            self._frame_gaps_ms.append(gap)
            self._max_frame_gap_ms = max(self._max_frame_gap_ms, gap)
        self._last_paint_clock_ms = paint_clock_ms

        ctx = self.context()
        if ctx is None or not ctx.isValid():
            return
        funcs = ctx.functions()
        width = max(1, int(self.width()))
        height = max(1, int(self.height()))
        multipass = (
            (not UI_FOCUS_MODE)
            and self._ensure_framebuffers()
            and self._scene_fbo is not None
            and self._bloom_a_fbo is not None
            and self._bloom_b_fbo is not None
            and self._bloom_h_program is not None
            and self._bloom_v_program is not None
            and self._composite_program is not None
        )

        if multipass:
            # PASS 1: clean procedural reactor scene.
            self._scene_fbo.bind()
            funcs.glViewport(0, 0, width, height)
            funcs.glClear(_GL_COLOR_BUFFER_BIT)
            self._render_scene(funcs, width, height)

            # PASS 2A: bright extraction + horizontal Gaussian blur at half res.
            bw = max(2, int(width * self._bloom_scale))
            bh = max(2, int(height * self._bloom_scale))
            self._bloom_a_fbo.bind()
            funcs.glViewport(0, 0, bw, bh)
            funcs.glClear(_GL_COLOR_BUFFER_BIT)
            self._render_bloom_pass(
                funcs, self._bloom_h_program, "bloom_h", int(self._scene_fbo.texture()),
                1.0 / float(width), 1.0 / float(height), threshold=0.34,
            )

            # PASS 2B: vertical blur completes the cinematic bloom kernel.
            self._bloom_b_fbo.bind()
            funcs.glViewport(0, 0, bw, bh)
            funcs.glClear(_GL_COLOR_BUFFER_BIT)
            self._render_bloom_pass(
                funcs, self._bloom_v_program, "bloom_v", int(self._bloom_a_fbo.texture()),
                1.0 / float(bw), 1.0 / float(bh),
            )

            # PASS 3: tone-map scene + blurred energy into the widget framebuffer.
            self._bind_default_framebuffer(funcs)
            funcs.glViewport(0, 0, width, height)
            funcs.glClear(_GL_COLOR_BUFFER_BIT)
            self._render_composite(funcs, int(self._scene_fbo.texture()), int(self._bloom_b_fbo.texture()))
        else:
            self._bind_default_framebuffer(funcs)
            funcs.glViewport(0, 0, width, height)
            funcs.glClear(_GL_COLOR_BUFFER_BIT)
            self._render_scene(funcs, width, height)

        if hasattr(funcs, "glFlush"):
            funcs.glFlush()
        if self._gl_error_checks_remaining > 0 and hasattr(funcs, "glGetError"):
            self._gl_error_checks_remaining -= 1
            gl_error = int(funcs.glGetError())
            if gl_error != 0:
                logger.warning(
                    "OpenGL dynamic frame GL error=0x%04X state=%s shader_time=%.3f cinematic=%s",
                    gl_error, self._state, self._elapsed, multipass,
                )

    @staticmethod
    def _sample_image_pixels(image) -> list[tuple[int, int, int]]:
        if image is None or image.isNull():
            return []
        w = max(1, image.width())
        h = max(1, image.height())
        values: list[tuple[int, int, int]] = []
        for gy in range(3, 30):
            y = min(h - 1, int(h * gy / 32.0))
            for gx in range(3, 30):
                x = min(w - 1, int(w * gx / 32.0))
                c = image.pixelColor(x, y)
                values.append((c.red(), c.green(), c.blue()))
        return values

    @staticmethod
    def _pixel_motion_score(before: list[tuple[int, int, int]], after: list[tuple[int, int, int]]) -> float:
        count = min(len(before), len(after))
        if count <= 0:
            return -1.0
        delta = 0.0
        for a, b in zip(before[:count], after[:count]):
            delta += abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
        return delta / (count * 3.0)

    def _capture_motion_baseline(self) -> None:
        if self._preload_visual_safety:
            return
        if self._failed or not self._started or not self.isVisible():
            return
        try:
            self._motion_baseline = self._sample_image_pixels(self.grabFramebuffer())
        except Exception:
            logger.info("OpenGL dynamic self-test baseline unavailable", exc_info=True)

    def _validate_dynamic_output(self) -> None:
        if self._preload_visual_safety:
            return
        if self._failed or not self._started or not self.isVisible() or not self._motion_baseline:
            return
        try:
            current = self._sample_image_pixels(self.grabFramebuffer())
            score = self._pixel_motion_score(self._motion_baseline, current)
            self._dynamic_motion_score = score
            logger.info(
                "OpenGL dynamic output self-test state=%s shader_time=%.2fs motion_score=%.2f",
                self._state, self._elapsed, score,
            )
            if score >= 0.0 and score < 0.35:
                self._dynamic_low_motion_confirmations += 1
                self._visual_quality_recovery_samples = 0
                # Low motion during XTTS/CUDA warm-up is treated as transient
                # GPU/UI pressure. Keep the exact same cinematic shader and
                # lower only its cadence. Do NOT emit initialization_failed.
                if self._dynamic_low_motion_confirmations >= 2:
                    self._set_adaptive_visual_quality("cinematic-eco", reason=f"low-motion:{score:.2f}")
                else:
                    self._set_adaptive_visual_quality("cinematic-balanced", reason=f"low-motion:{score:.2f}")
                logger.info(
                    "OpenGL cinematic lock retained motion_score=%.2f quality=%s confirmations=%d",
                    score, self._visual_quality_tier, self._dynamic_low_motion_confirmations,
                )
                self._motion_baseline = current
                QTimer.singleShot(1800, self._validate_dynamic_output)
                return
            else:
                self._dynamic_low_motion_confirmations = 0
                if score >= 0.75:
                    self._visual_quality_recovery_samples += 1
                    if self._visual_quality_recovery_samples >= 2:
                        self._set_adaptive_visual_quality("cinematic-high", reason=f"motion-recovered:{score:.2f}")
                else:
                    self._visual_quality_recovery_samples = 0
        except Exception:
            # Diagnostic failure must never take the UI down.
            logger.info("OpenGL dynamic self-test unavailable", exc_info=True)


    def _set_adaptive_visual_quality(self, tier: str, *, reason: str = "") -> None:
        """Keep AURA's cinematic orb while adapting only render cadence.

        QPainter is a survival fallback for hard OpenGL failures only. Motion
        diagnostics may select balanced/eco cadence but never replace the orb.
        """
        tier = tier if tier in {"cinematic-high", "cinematic-balanced", "cinematic-eco"} else "cinematic-high"
        preferred = max(30.0, min(90.0, float(settings.OPENGL_ORB_FPS)))
        if tier == "cinematic-balanced":
            budget = min(preferred, 36.0)
        elif tier == "cinematic-eco":
            budget = min(preferred, 30.0)
        else:
            budget = preferred
        target = self._sync_fps_for_refresh(self._display_refresh_hz, budget)
        interval = max(8, int(1000.0 / max(1.0, target)))
        changed = tier != self._visual_quality_tier or interval != self._frame_interval_ms
        self._visual_quality_tier = tier
        self._target_fps = target
        self._frame_interval_ms = interval
        self._timer.setInterval(interval)
        if changed:
            logger.info(
                "OpenGL adaptive visual quality tier=%s target_fps=%.2f interval=%dms reason=%s baseline=cinematic-opengl-v1",
                tier, target, interval, reason or "runtime",
            )

    @staticmethod
    def _sync_fps_for_refresh(refresh_hz: float, preferred_fps: float = 60.0) -> float:
        """Choose a cadence that divides the display refresh cleanly.

        Examples: 60->60, 120->60, 144->48, 165->55, 240->60.
        Never exceed the configured FPS budget: on a shared display/CUDA GPU,
        silently raising 60 FPS to 72 FPS wastes headroom exactly when XTTS or
        Ollama may need it. Prefer the nearest clean divisor at or below budget.
        """
        try:
            refresh = float(refresh_hz)
            preferred = max(30.0, min(90.0, float(preferred_fps)))
        except (TypeError, ValueError):
            return 60.0
        if refresh < 40.0 or refresh > 500.0:
            return preferred
        divisor = max(1, int(math.ceil(refresh / preferred)))
        synced = refresh / divisor
        if 30.0 <= synced <= preferred + 0.01:
            return synced
        return preferred

    def _align_timer_to_display(self) -> None:
        try:
            screen = self.screen()
            refresh = float(screen.refreshRate()) if screen is not None else 0.0
        except Exception:
            refresh = 0.0
        preferred = max(30.0, min(90.0, float(settings.OPENGL_ORB_FPS)))
        target = self._sync_fps_for_refresh(refresh, preferred)
        interval = max(8, int(1000.0 / max(1.0, target)))
        changed = interval != self._frame_interval_ms
        self._display_refresh_hz = refresh
        self._target_fps = target
        self._frame_interval_ms = interval
        self._timer.setInterval(interval)
        if changed:
            logger.info(
                "OpenGL Orb cadence display_refresh=%.2fHz target_fps=%.2f interval=%dms",
                refresh, target, interval,
            )

    def showEvent(self, event) -> None:
        self._align_timer_to_display()
        if not self._clock.isValid():
            self._clock.start()
        if not self._timer.isActive():
            self._timer.start(self._frame_interval_ms)
        self.update()
        super().showEvent(event)

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)
