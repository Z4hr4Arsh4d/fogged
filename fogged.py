"""
Fogged — breathe on the glass, wipe the fog to write.

A real-time, multimodal toy: your breath fogs the "glass", your fingertip wipes it clear.

  M0  mirrored webcam loop
  M1  the fog layer      — a float mask: 0 = clear glass, 1 = fully fogged
  M2  fingertip wipe     — point to write, open palm to clear
  M3  breath detection   — sustained low-frequency audio fogs the glass  + cinematic intro
  M4  fog dynamics       — condensation reforms, breath blooms locally, fog evaporates
  M5  polish             — wet edges, vignette, stronger frosted look
  M6  gestures           — pinch to size the brush, OK sign to screenshot
  M7  droplets           — condensation beads up and trickles down, clearing trails

Controls
  BLOW on the mic          fog the glass
  point index finger       write in the fog
  open palm                wipe it all clear
  pinch (thumb+index)      brush size
  OK sign                  save a screenshot
  F  manual fog     C  clear      [ ] brush size    D  debug mask
  R  replay intro   ENTER fullscreen                Q / ESC  quit
"""
import os
import time
from datetime import datetime

import sys

import cv2
import numpy as np

print(f"[0] python {sys.version.split()[0]} | opencv {cv2.__version__} | numpy {np.__version__}", flush=True)
print("[1] importing mediapipe ...", flush=True)
mp_hands = None
try:
    # MediaPipe moved things around between versions. Try the paths that actually exist,
    # newest-style first. `import mediapipe as mp; mp.solutions.hands` fails on some builds,
    # and versions after 0.10.14 removed the legacy solutions API entirely.
    try:
        from mediapipe.python.solutions import hands as mp_hands       # explicit, 0.10.x
    except Exception:
        import mediapipe as mp
        mp_hands = mp.solutions.hands                                  # older / lazy-attr builds
    HAS_MP = mp_hands is not None
    print(f"[1] mediapipe OK (hands module: {mp_hands.__name__})", flush=True)
except Exception as e:
    HAS_MP = False
    print(f"[1] mediapipe FAILED -> {type(e).__name__}: {e}", flush=True)
    print("    (fog still works; press F to fog, no hand tracking)", flush=True)

# ---------------------------------------------------------------- config
CAM_INDEX = 0                 # try 1 or 2 if the webcam doesn't open
WIDTH, HEIGHT = 1280, 720     # camera capture size (720p)
FULLSCREEN = False            # ENTER toggles this at any time

# --- intro (M3) ---
INTRO_SECONDS = 4.2
INTRO_TITLE   = "FOGGED"

# --- breath (M3) ---
BREATH_RMS_MIN   = 0.012      # loudness gate  (lower = more sensitive)
BREATH_LOW_RATIO = 0.55       # share of energy in 50-500Hz that reads as "breath-like"
BREATH_ATTACK    = 3.2        # how fast detected breath ramps the fog up

# --- glass look (M1 / M5) ---
BLUR_KERNEL   = 31            # frosted-glass softness (odd number)
BLUR_SCALE    = 0.25          # blur a small copy then upscale — big speedup
FOG_WHITE     = 0.70          # bright, milky glass — not gray gloom
FOG_TINT      = (8, 4, 0)     # the faintest cool cast (B, G, R)
VIGNETTE      = 0.16          # just a whisper of edge falloff

# --- realism (M9) ---
NOISE_STRENGTH = 0.12         # patchiness of the condensation (0 = uniform fog)
REFRACT_PX     = 6.0          # how far fog bends light at STROKE edges (0 = off)
TIP_SMOOTH     = 0.42         # fingertip smoothing (lower = smoother strokes, a touch more lag)

# --- performance ---
HANDS_SCALE = 0.4             # hand tracking runs on a downscaled frame (landmarks are normalised)
FOG_SCALE   = 0.5             # the frosted/refracted layer is built at this scale, then upscaled

# --- wipe (M2) ---
BRUSH_RADIUS  = 26
BRUSH_FEATHER = 0.55          # 0 = hard edge, 1 = very soft
PALM_FADE     = 3.5           # how fast an open palm clears the glass
WET_EDGE      = 0.55          # brightness of the wet rim along fresh strokes (0 = off)

# --- dynamics (M4) ---
# Two fields, not one. `ambient` is how fogged the glass *wants* to be; `mask` is how fogged
# it actually is. Breath raises ambient; ambient evaporates slowly; the mask you wipe creeps
# back toward ambient. That separation is what lets your writing fog over in seconds while the
# whole pane still clears if you walk away for a few minutes.
REFORM_RATE   = 0.28          # how fast the wiped mask creeps back toward ambient (1/s)
EVAPORATE     = 0.020         # how fast ambient fog fades when you leave it alone (1/s)
BLOOM_SIGMA   = 0.28          # breath bloom size, as a fraction of the frame
BLOOM_CENTER  = (0.5, 0.62)   # where your breath lands on the glass (x, y in 0..1)

# --- droplets & dew (M7) ---
DROPLETS_ON     = True
DROPLET_CHANCE  = 0.10        # chance per frame that a new runnel starts
DROPLET_MAX     = 22          # fewer, bigger, glassier runnels
DEW_COUNT       = 300         # static dew glints that appear wherever the glass is fogged

FINGERTIPS = (8, 12, 16, 20)  # index, middle, ring, pinky tips
PIPS       = (6, 10, 14, 18)  # the joint below each

# Live-tunable settings (press S in the app for sliders). Dict so callbacks can mutate them.
SET = {
    "fog_cap": 1.0,               # how dense the fog is allowed to get (Fog density)
    "dew_opacity": 0.8,           # how visible the static dew glints are
    "breath_min": BREATH_RMS_MIN, # mic loudness gate (Blow sensitivity)
    "drop_chance": DROPLET_CHANCE # how often new runnels start (Streams)
}


_settings_open = [False]


def open_settings():
    """A small slider panel — fog density, dew opacity, blow sensitivity, streams."""
    if _settings_open[0]:
        return
    _settings_open[0] = True
    win = "Fogged Settings"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 420, 160)
    cv2.createTrackbar("Fog density %", win, int(SET["fog_cap"] * 100), 100,
                       lambda v: SET.__setitem__("fog_cap", max(0.2, v / 100.0)))
    cv2.createTrackbar("Dew opacity %", win, int(SET["dew_opacity"] * 100), 100,
                       lambda v: SET.__setitem__("dew_opacity", v / 100.0))
    cv2.createTrackbar("Blow sens %", win, 50, 100,
                       lambda v: SET.__setitem__("breath_min", 0.022 - 0.020 * (v / 100.0)))
    cv2.createTrackbar("Streams %", win, int(SET["drop_chance"] * 333), 100,
                       lambda v: SET.__setitem__("drop_chance", 0.30 * (v / 100.0)))


# ---------------------------------------------------------------- breath (audio)
class BreathDetector:
    """Approximates an exhale: sustained, low-frequency, broadband audio energy.

    Honest caveat: a microphone cannot truly distinguish a breath from other low noise.
    We detect *sustained low-frequency energy*, which feels like magic but is not a
    respiration sensor.
    """

    def __init__(self, samplerate: int = 16000, block: int = 1024):
        self.level = 0.0          # smoothed 0..1 "how much breath right now"
        self.ok = False
        self._sr, self._block = samplerate, block
        self._stream = None

    def start(self) -> bool:
        try:
            import sounddevice as sd
        except Exception as e:
            print(f"[audio] sounddevice unavailable ({e}) — press F to fog instead.", flush=True)
            return False
        try:
            self._stream = sd.InputStream(channels=1, samplerate=self._sr,
                                          blocksize=self._block, callback=self._cb)
            self._stream.start()
            self.ok = True
            print("[audio] microphone open — blow on the mic to fog the glass", flush=True)
        except Exception as e:
            print(f"[audio] could not open microphone ({e}) — press F to fog instead.", flush=True)
        return self.ok

    def _cb(self, indata, frames, time_info, status):
        x = indata[:, 0].astype(np.float32)
        rms = float(np.sqrt(np.mean(x * x)) + 1e-9)
        if rms < SET["breath_min"]:
            self.level *= 0.85                       # decay toward silence
            return
        spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        freqs = np.fft.rfftfreq(len(x), 1.0 / self._sr)
        low = spec[(freqs > 50) & (freqs < 500)].sum()
        total = spec.sum() + 1e-9
        ratio = float(low / total)                   # breath is low-frequency & broadband
        target = 1.0 if ratio > BREATH_LOW_RATIO else 0.0
        self.level += (target - self.level) * 0.35   # smooth so it doesn't flicker

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()


# ---------------------------------------------------------------- fog mask
def make_brush(radius: int, feather: float) -> np.ndarray:
    """A soft-edged circular stamp in [0,1] — 1 at the centre, 0 at the rim."""
    r = max(1, int(radius))
    ys, xs = np.mgrid[-r:r + 1, -r:r + 1]
    dist = np.sqrt(xs * xs + ys * ys) / r
    inner = max(0.001, 1.0 - feather)
    return np.clip((1.0 - dist) / (1.0 - inner + 1e-6), 0.0, 1.0).astype(np.float32)


def make_bloom(h: int, w: int) -> np.ndarray:
    """A soft radial falloff — where your breath lands hardest on the glass."""
    cx, cy = BLOOM_CENTER[0] * w, BLOOM_CENTER[1] * h
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    d2 = ((xs - cx) ** 2 + (ys - cy) ** 2) / (2.0 * (BLOOM_SIGMA * w) ** 2)
    bloom = np.exp(-d2)
    return (0.25 + 0.75 * bloom).astype(np.float32)   # never fully zero — glass mists over


def make_vignette(h: int, w: int) -> np.ndarray:
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = (xs - w / 2) / (w / 2)
    dy = (ys - h / 2) / (h / 2)
    r = np.sqrt(dx * dx + dy * dy) / 1.4142
    return np.clip(1.0 - VIGNETTE * r ** 2.2, 0.0, 1.0).astype(np.float32)


def wipe(mask: np.ndarray, cx: int, cy: int, brush: np.ndarray) -> None:
    """Subtract the brush from the mask at (cx, cy), clipped to the frame. In-place."""
    r = brush.shape[0] // 2
    h, w = mask.shape
    x0, x1, y0, y1 = cx - r, cx + r + 1, cy - r, cy + r + 1
    bx0, by0 = max(0, -x0), max(0, -y0)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x0 >= x1 or y0 >= y1:
        return
    sub = brush[by0:by0 + (y1 - y0), bx0:bx0 + (x1 - x0)]
    region = mask[y0:y1, x0:x1]
    np.subtract(region, sub, out=region)
    np.clip(region, 0.0, 1.0, out=region)


def wipe_line(mask, p0, p1, brush) -> None:
    """Stamp along p0->p1 so fast strokes stay connected (no dotted gaps)."""
    (x0, y0), (x1, y1) = p0, p1
    dist = max(abs(x1 - x0), abs(y1 - y0))
    steps = max(1, int(dist / max(1, brush.shape[0] * 0.25)))
    for i in range(steps + 1):
        t = i / steps
        wipe(mask, int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t)), brush)


_noise_cache = {}
_map_cache = {}


def fractal_noise(h: int, w: int, octaves: int = 5, seed: int = 7) -> np.ndarray:
    """Multi-octave value noise in [0,1] — the patchy, cloudy structure of real condensation."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, total, size = 1.0, 0.0, 6
    for _ in range(octaves):
        layer = rng.random((size, size)).astype(np.float32)
        out += amp * cv2.resize(layer, (w, h), interpolation=cv2.INTER_CUBIC)
        total += amp
        amp *= 0.65                              # slower decay = more fine-scale detail
        size *= 3                                # bigger jumps = wider range of scales
    out /= total
    lo, hi = float(out.min()), float(out.max())
    return (out - lo) / (hi - lo + 1e-6)


def _get_noise(h: int, w: int) -> np.ndarray:
    key = (h, w)
    if key not in _noise_cache:
        _noise_cache[key] = fractal_noise(h, w)
    return _noise_cache[key]


def _get_maps(h: int, w: int):
    key = (h, w)
    if key not in _map_cache:
        xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        _map_cache[key] = (xs, ys)
    return _map_cache[key]


def frosted(frame: np.ndarray) -> np.ndarray:
    """The frosted layer, built at FOG_SCALE in uint8 (composite() upscales it).

    Fog is blurry by nature, so half resolution is visually free — and staying in uint8
    with cv2-native ops keeps this ~5x cheaper than full-res NumPy float math.
    """
    h, w = frame.shape[:2]
    hs, ws = int(h * FOG_SCALE), int(w * FOG_SCALE)
    small = cv2.resize(frame, (ws, hs), interpolation=cv2.INTER_LINEAR)
    k = max(3, int(BLUR_KERNEL * FOG_SCALE) | 1)
    small = cv2.GaussianBlur(small, (k, k), 0)
    fogc = cv2.convertScaleAbs(small, alpha=(1.0 - FOG_WHITE), beta=255.0 * FOG_WHITE)
    b, g, r = FOG_TINT
    fogc = cv2.add(fogc, (max(0, b), max(0, g), max(0, r), 0))
    fogc = cv2.subtract(fogc, (max(0, -b), max(0, -g), max(0, -r), 0))
    return fogc


_vig_cache = {}


def _get_vig3(vignette: np.ndarray):
    key = vignette.shape
    if key not in _vig_cache:
        v = np.clip(vignette * 255.0, 0, 255).astype(np.uint8)
        _vig_cache[key] = cv2.merge([v, v, v])
    return _vig_cache[key]


_noise_small_cache = {}


def _get_noise_small(h: int, w: int) -> np.ndarray:
    key = (h, w)
    if key not in _noise_small_cache:
        full_h, full_w = int(h / FOG_SCALE), int(w / FOG_SCALE)
        _noise_small_cache[key] = cv2.resize(_get_noise(full_h, full_w), (w, h),
                                             interpolation=cv2.INTER_LINEAR)
    return _noise_small_cache[key]


def composite(frame, fog, mask, vignette=None, wet=True):
    """sharp where the glass is clear, frosted where it's fogged.

    Fractal noise makes the fog's *opacity* patchy; refraction and the wet rim come from
    the SMOOTH mask gradient only (stroke edges, bloom, streaks). All heavy per-pixel work
    happens either at FOG_SCALE or inside cv2's SIMD primitives — full-res NumPy float
    math is what murdered the frame rate before.
    """
    h, w = mask.shape
    noise = _get_noise(h, w)
    density = np.clip(mask * (1.0 - NOISE_STRENGTH + 2.0 * NOISE_STRENGTH * noise), 0.0, 1.0)

    hs, ws = fog.shape[0], fog.shape[1]
    m_small = cv2.resize(mask, (ws, hs), interpolation=cv2.INTER_LINEAR)
    d = cv2.GaussianBlur(m_small, (0, 0), 3)
    gx = cv2.Sobel(d, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(d, cv2.CV_32F, 0, 1, ksize=5)

    if REFRACT_PX > 0:
        bx, by = _get_maps(hs, ws)
        k = REFRACT_PX * FOG_SCALE
        fog = cv2.remap(fog, bx + gx * k, by + gy * k,
                        cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    bent = cv2.resize(fog, (w, h), interpolation=cv2.INTER_LINEAR)

    if hasattr(cv2, "blendLinear"):
        out = cv2.blendLinear(frame, bent, 1.0 - density, density)   # SIMD compositing
    else:                                                             # older builds: NumPy fallback
        m = density[:, :, None]
        out = (frame.astype(np.float32) * (1.0 - m) + bent.astype(np.float32) * m).astype(np.uint8)

    if wet and WET_EDGE > 0:
        n_small = _get_noise_small(hs, ws)
        mag = np.clip(np.hypot(gx, gy) * 0.45, 0.0, 1.0) * (0.7 + 0.3 * n_small)
        e = cv2.convertScaleAbs(mag, alpha=255.0 * WET_EDGE)
        e = cv2.resize(e, (w, h), interpolation=cv2.INTER_LINEAR)
        out = cv2.add(out, cv2.merge([e, e, e]))                 # saturating uint8 add

    if vignette is not None:
        out = cv2.multiply(out, _get_vig3(vignette), scale=1.0 / 255.0)
    return out


# ---------------------------------------------------------------- droplets (M7)
_sprite_cache = {}


def _drop_sprite(r: int):
    """A pre-shaded water-bead sprite (color, alpha), built once per radius.

    A real droplet on glass acts like a tiny lens: bright at the lower belly, darker
    at the rim, a hard specular glint up-left. That shading — not the circle — is
    what makes it read as water.
    """
    if r not in _sprite_cache:
        rr = max(1, int(r))
        ys, xs = np.mgrid[-rr:rr + 1, -rr:rr + 1].astype(np.float32) / rr
        d = np.sqrt(xs * xs + ys * ys)
        alpha = np.clip((1.0 - d) * 2.4, 0.0, 1.0)                      # soft round edge
        body = 148.0 + 72.0 * np.clip(ys + 0.35, -1.0, 1.0)            # lens: bright belly
        rim = np.clip((d - 0.55) * 2.2, 0.0, 1.0)
        body *= (1.0 - 0.42 * rim)                                      # darker rim
        spec = np.clip(1.0 - ((xs + 0.38) ** 2 + (ys + 0.38) ** 2) * 9.0, 0.0, 1.0)
        col = np.clip(body + spec * 110.0, 0, 255)
        col3 = np.repeat(col[:, :, None], 3, axis=2)
        col3[:, :, 0] = np.clip(col3[:, :, 0] + 7, 0, 255)              # faint cool cast
        shadow = np.clip((1.0 - d) * 1.4, 0.0, 1.0) * 0.35              # soft under-shadow
        _sprite_cache[r] = (col3.astype(np.float32), alpha.astype(np.float32), shadow.astype(np.float32))
    return _sprite_cache[r]


def _blit(img: np.ndarray, cx: int, cy: int, col3, alpha, alpha_mul: float = 1.0) -> None:
    """Alpha-blend a small sprite onto img at (cx, cy), safely clipped at the edges."""
    r = alpha.shape[0] // 2
    h, w = img.shape[:2]
    x0, x1, y0, y1 = cx - r, cx + r + 1, cy - r, cy + r + 1
    sx0, sy0 = max(0, -x0), max(0, -y0)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x0 >= x1 or y0 >= y1:
        return
    a = (alpha[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)] * alpha_mul)[:, :, None]
    roi = img[y0:y1, x0:x1].astype(np.float32)
    if col3 is None:                                   # shadow pass: darken only
        img[y0:y1, x0:x1] = (roi * (1.0 - a * 0.5)).astype(np.uint8)
    else:
        c = col3[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
        img[y0:y1, x0:x1] = (roi * (1.0 - a) + c * a).astype(np.uint8)


class Droplets:
    """Dew and runnels. Static dew glints wherever the glass is fogged; heavier beads
    gather speed and run down, wiping a thin continuous clear streak — rain tracks
    on a misted window."""

    def __init__(self):
        self.drops = []           # runnels: [x, y, prev_x, prev_y, bead_r, speed, wobble]
        self.dew = None

    def _ensure_dew(self, h, w):
        if self.dew is None:
            rng = np.random.default_rng(11)
            self.dew = [(int(rng.integers(4, w - 4)), int(rng.integers(4, h - 4)),
                         float(rng.uniform(1.0, 2.4))) for _ in range(DEW_COUNT)]

    def update(self, mask: np.ndarray, dt: float, brush_cache: dict) -> None:
        h, w = mask.shape
        self._ensure_dew(h, w)
        if len(self.drops) < DROPLET_MAX and np.random.rand() < SET["drop_chance"]:
            x, y = np.random.randint(8, w - 8), np.random.randint(0, int(h * 0.5))
            if mask[y, x] > 0.75:                     # runnels only form on fogged glass
                self.drops.append([float(x), float(y), float(x), float(y),
                                   float(np.random.uniform(3.0, 6.0)),
                                   float(np.random.uniform(26, 80)),
                                   float(np.random.rand() * 6.3)])
        alive = []
        for d in self.drops:
            d[2], d[3] = d[0], d[1]
            d[6] += dt * 2.2
            d[0] += np.sin(d[6]) * 5.0 * dt           # gentle wobble
            d[5] = min(150.0, d[5] + 32.0 * dt)       # gathers speed as it runs
            d[1] += d[5] * dt
            if d[1] < h - 3 and 3 <= d[0] < w - 3:
                r = max(1, int(d[4] * 0.55))          # streak thinner than the bead
                b = brush_cache.get(r)
                if b is None:
                    b = make_brush(r, 0.8)
                    brush_cache[r] = b
                # continuous line from last position -> no dotted trails, even at low fps
                wipe_line(mask, (int(d[2]), int(d[3])), (int(d[0]), int(d[1])), b)
                alive.append(d)
        self.drops = alive

    def draw(self, img: np.ndarray, mask: np.ndarray) -> None:
        dew_a = SET["dew_opacity"]
        if dew_a > 0.02:
            # static dew: shaded micro-beads, only where the glass is actually fogged
            for x, y, r in self.dew:
                if mask[y, x] > 0.55:
                    col3, alpha, _ = _drop_sprite(max(1, int(r)))
                    _blit(img, x, y, col3, alpha, dew_a)
        # runnels: a glossy bead at the head of each streak, with a soft shadow under it
        for x, y, px, py, r, _, _ in self.drops:
            xi, yi, ri = int(x), int(y), max(2, int(r))
            col3, alpha, shadow = _drop_sprite(ri)
            _blit(img, xi + 1, yi + 2, None, shadow)                    # shadow first
            _blit(img, int(px), int(py), col3, alpha, 0.35)             # faint motion smear
            _blit(img, xi, yi, col3, alpha, 1.0)                        # the bead


# ---------------------------------------------------------------- hand helpers
def finger_extended(lm, tip: int, pip: int) -> bool:
    """A finger is 'up' when its tip sits above its lower joint (smaller y in image coords)."""
    return lm.landmark[tip].y < lm.landmark[pip].y


def is_open_palm(lm) -> bool:
    return sum(finger_extended(lm, t, p) for t, p in zip(FINGERTIPS, PIPS)) >= 4


def is_pointing(lm) -> bool:
    """Index up, middle down — the writing pose."""
    return finger_extended(lm, 8, 6) and not finger_extended(lm, 12, 10)


def pinch_amount(lm, w: int, h: int) -> float:
    """Normalised thumb-tip to index-tip distance, scaled by hand size (so depth doesn't matter)."""
    t, i = lm.landmark[4], lm.landmark[8]
    wrist, mid = lm.landmark[0], lm.landmark[9]
    d = np.hypot((t.x - i.x) * w, (t.y - i.y) * h)
    span = np.hypot((wrist.x - mid.x) * w, (wrist.y - mid.y) * h) + 1e-6
    return float(np.clip(d / span, 0.0, 1.6))


def is_ok_sign(lm, w: int, h: int) -> bool:
    """Thumb and index pinched, other three fingers extended."""
    others = sum(finger_extended(lm, t, p) for t, p in zip((12, 16, 20), (10, 14, 18)))
    return pinch_amount(lm, w, h) < 0.28 and others >= 2


# ---------------------------------------------------------------- intro
_title_cache = {}


def _glass_title(w: int, h: int):
    """Pre-rendered chrome-glass title layers: banded silver fill, bevel light/shadow, outline."""
    key = (w, h)
    if key not in _title_cache:
        scale = w / 300.0
        thick = max(3, int(scale * 2.8))
        font = cv2.FONT_HERSHEY_TRIPLEX
        (tw, th), _ = cv2.getTextSize(INTRO_TITLE, font, scale, thick)
        x, y = (w - tw) // 2, (h + th) // 2
        m8 = np.zeros((h, w), np.uint8)                 # OpenCV 5.x: putText requires 8-bit
        cv2.putText(m8, INTRO_TITLE, (x, y), font, scale, 255, thick, cv2.LINE_AA)
        m = m8.astype(np.float32) / 255.0
        soft = cv2.GaussianBlur(m, (0, 0), 3)
        gx = cv2.Sobel(soft, cv2.CV_32F, 1, 0, ksize=5)
        gy = cv2.Sobel(soft, cv2.CV_32F, 0, 1, ksize=5)
        bevel_light = np.clip(-(gx + gy) * 0.9, 0, 1) * m       # lit from the top-left
        bevel_dark = np.clip((gx + gy) * 0.9, 0, 1) * m         # shadow bottom-right
        ys = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        silver = 150.0 + 85.0 * np.abs(np.sin(ys * np.pi * 2.3 + 0.6))   # banded chrome
        silver = np.repeat(silver, w, axis=1).astype(np.float32)
        outline = np.clip(cv2.dilate(m, np.ones((3, 3), np.uint8)) - m, 0, 1)
        _title_cache[key] = (m, bevel_light, bevel_dark, silver, outline, (y, th))
    return _title_cache[key]


def draw_intro(frame, t: float):
    """Chrome-glass engraved title over the fogged pane, with a shine sweeping across it."""
    h, w = frame.shape[:2]
    p = np.clip(t / INTRO_SECONDS, 0.0, 1.0)

    base = composite(frame, frosted(frame), np.ones((h, w), np.float32), wet=False)
    base = base.astype(np.float32) * 0.6

    m, bl, bd, silver, outline, (ty, th) = _glass_title(w, h)
    if p < 0.4:
        a = p / 0.4
    elif p < 0.78:
        a = 1.0
    else:
        a = max(0.0, 1.0 - (p - 0.78) / 0.22)

    # chrome fill: banded silver with the fogged scene faintly showing through the letters
    fill = silver * 0.72 + base.mean(axis=2) * 0.28
    txt = np.repeat((fill * m)[:, :, None], 3, axis=2)
    txt += (bl * 235.0)[:, :, None]                  # bright bevel edges
    txt -= (bd * 95.0)[:, :, None]                   # shadow edges
    txt -= (outline * 70.0)[:, :, None]              # dark rim so it sits IN the glass

    # a shine sweeps diagonally across the letters over the course of the intro
    xs = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    ys = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    band = np.exp(-((xs * 0.8 + ys * 0.35 - (-0.35 + 1.7 * p)) ** 2) / 0.004) * m
    txt += (band * 150.0)[:, :, None]

    alpha = ((m + outline) * a)[:, :, None]
    out = np.clip(base * (1.0 - alpha) + np.clip(txt, 0, 255) * alpha, 0, 255).astype(np.uint8)

    if p > 0.5:                                       # subtitle is drawn on uint8 (5.x-safe)
        sub = "breathe on the glass"
        ss = (w / 380.0) * 0.28
        (sw, _), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, ss, 1)
        sa = min(1.0, (p - 0.5) / 0.3) * a
        cv2.putText(out, sub, ((w - sw) // 2, ty + int(th * 1.15)),
                    cv2.FONT_HERSHEY_SIMPLEX, ss, (int(200 * sa), int(220 * sa), int(230 * sa)), 1, cv2.LINE_AA)
    return out


# ---------------------------------------------------------------- camera
def open_camera(index: int):
    """Open the webcam, trying the Windows-friendly DirectShow backend first.

    Plain cv2.VideoCapture(index) frequently 'opens' on Windows but then delivers
    no frames, so we verify with an actual read() before accepting a backend.
    """
    for name, backend in [("CAP_DSHOW", cv2.CAP_DSHOW), ("CAP_MSMF", cv2.CAP_MSMF), ("default", None)]:
        print(f"[3] trying backend {name} on index {index} ...", flush=True)
        cap = cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
            ok, fr = cap.read()
            print(f"[3]   read ok={ok} shape={None if fr is None else fr.shape}", flush=True)
            if ok:
                print(f"[3] SUCCESS: camera {index} via {name}", flush=True)
                return cap
        cap.release()
    return None


# ---------------------------------------------------------------- main
def main() -> None:
    print("[2] main() started", flush=True)
    cap = open_camera(CAM_INDEX)
    if cap is None:
        print("Could not open the webcam on any backend. Try a different CAM_INDEX (0, 1, 2...),")
        print("and make sure no other app (Zoom/Teams/Camera) is using it.")
        return

    hands = None
    if HAS_MP:
        print("[4] initialising MediaPipe Hands ...", flush=True)
        try:
            hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.6,
                                   min_tracking_confidence=0.5)
            print("[4] MediaPipe Hands ready", flush=True)
        except Exception as e:
            print(f"[4] MediaPipe Hands FAILED -> {type(e).__name__}: {e}", flush=True)
            hands = None

    breath = BreathDetector()
    breath.start()

    cv2.namedWindow("Fogged", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Fogged", WIDTH, HEIGHT)
    if FULLSCREEN:
        cv2.setWindowProperty("Fogged", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    intro_start = time.time()
    mask = ambient = None
    bloom = vignette = None
    droplets = Droplets()
    drop_brushes: dict = {}
    brush_radius = BRUSH_RADIUS
    brush = make_brush(brush_radius, BRUSH_FEATHER)
    fogging = False
    debug = False
    last_tip = None; tip_s = None
    shot_cooldown = 0.0
    toast = ("", 0.0)
    prev_t = time.time()
    fps = 0.0

    print("[5] entering main loop", flush=True)
    print(f"    hand tracking: {'ON' if hands is not None else 'OFF (fog + keyboard only)'}", flush=True)
    print("Fogged — BLOW to fog | point index = write | pinch tight = fine write | open palm = wipe | OK = screenshot", flush=True)
    print("         S = settings sliders (fog density, dew, blow sensitivity, streams)", flush=True)

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Camera stopped returning frames — exiting.", flush=True)
            break
        frame = cv2.flip(frame, 1)                 # mirror: feels like looking at a window
        h, w = frame.shape[:2]

        if mask is None or mask.shape != (h, w):
            mask = np.ones((h, w), np.float32)     # how fogged the glass *is*
            ambient = np.ones((h, w), np.float32)  # how fogged it *wants* to be
            bloom = make_bloom(h, w)
            vignette = make_vignette(h, w)

        now = time.time()
        dt = min(0.1, now - prev_t)                # clamp: a stutter shouldn't nuke the fog
        prev_t = now
        if dt > 0:
            fps = 0.9 * fps + 0.1 / dt
        shot_cooldown = max(0.0, shot_cooldown - dt)

        # --- INTRO ---
        elapsed = now - intro_start
        if elapsed < INTRO_SECONDS:
            cv2.imshow("Fogged", draw_intro(frame, elapsed))
            if (cv2.waitKey(1) & 0xFF) in (ord('q'), 27):
                break
            continue

        # --- M3/M4: breath raises the ambient fog level, blooming where it lands ---
        blow = breath.level if breath.ok else 0.0
        breathing = fogging or blow > 0.15
        if breathing:
            rate = 1.4 if fogging else (BREATH_ATTACK * blow)
            deposit = (rate * dt) * bloom          # bloom = strongest where you breathe
            ambient += deposit
            mask += deposit                        # breath lands on the glass *now*, no lag
            np.clip(ambient, 0.0, SET["fog_cap"], out=ambient)
            np.clip(mask, 0.0, 1.0, out=mask)
        else:
            ambient -= EVAPORATE * dt              # left alone, the pane slowly clears
            np.clip(ambient, 0.0, 1.0, out=ambient)
            # what you wiped creeps back toward ambient — your writing slowly fogs over
            mask += (ambient - mask) * min(1.0, REFORM_RATE * dt)
            np.clip(mask, 0.0, 1.0, out=mask)

        # --- M7: droplets bead up and trickle down, clearing trails ---
        if DROPLETS_ON:
            droplets.update(mask, dt, drop_brushes)

        # --- M2/M6: hands ---
        status = ""
        if hands is not None:
            hs_small = cv2.resize(frame, None, fx=HANDS_SCALE, fy=HANDS_SCALE,
                                  interpolation=cv2.INTER_LINEAR)
            try:
                res = hands.process(cv2.cvtColor(hs_small, cv2.COLOR_BGR2RGB))  # landmarks are normalised, so downscaling is free
            except Exception as e:
                print(f"[hands] tracking crashed ({type(e).__name__}: {e}) — disabling hand tracking, fog still works", flush=True)
                hands = None
                res = None
            if res is not None and res.multi_hand_landmarks:
                lm = res.multi_hand_landmarks[0]

                if is_ok_sign(lm, w, h) and shot_cooldown <= 0:
                    os.makedirs("media", exist_ok=True)
                    name = f"media/fogged_{datetime.now():%Y%m%d_%H%M%S}.png"
                    cv2.imwrite(name, composite(frame, frosted(frame), mask, vignette))
                    toast = (f"saved {name}", 2.0)
                    shot_cooldown = 1.5
                    status = "SCREENSHOT"
                    last_tip = None; tip_s = None
                elif is_open_palm(lm):
                    mask -= PALM_FADE * dt
                    ambient -= PALM_FADE * 0.5 * dt      # you're drying it, not just smearing
                    np.clip(mask, 0.0, 1.0, out=mask)
                    np.clip(ambient, 0.0, 1.0, out=ambient)
                    last_tip = None; tip_s = None
                    status = "PALM — wiping"
                elif is_pointing(lm):
                    # M6: pinch scales the brush live (thumb-index distance)
                    pa = pinch_amount(lm, w, h)
                    if pa < 0.75:
                        brush_radius = int(np.clip(8 + pa * 90, 6, 90))
                        brush = make_brush(brush_radius, BRUSH_FEATHER)
                    tip = lm.landmark[8]
                    rx, ry = tip.x * w, tip.y * h
                    if tip_s is None:
                        tip_s = [rx, ry]           # first touch: no smoothing lag
                    else:                           # EMA kills MediaPipe jitter -> clean strokes
                        tip_s[0] += (rx - tip_s[0]) * TIP_SMOOTH
                        tip_s[1] += (ry - tip_s[1]) * TIP_SMOOTH
                    cx, cy = int(tip_s[0]), int(tip_s[1])
                    if last_tip is not None:
                        wipe_line(mask, last_tip, (cx, cy), brush)
                    else:
                        wipe(mask, cx, cy, brush)
                    last_tip = (cx, cy)
                    status = "WRITING"
                    cv2.circle(frame, (cx, cy), brush_radius, (255, 255, 255), 1)
                else:
                    last_tip = None; tip_s = None
            else:
                last_tip = None; tip_s = None

        # --- render ---
        out = composite(frame, frosted(frame), mask, vignette)
        if DROPLETS_ON:
            droplets.draw(out, mask)

        if debug:
            out = cv2.cvtColor((mask * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)

        bl = int((breath.level if breath.ok else 0.0) * 20)
        cv2.putText(out, f"{fps:4.1f} FPS", (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        hud = f"breath [{'#' * bl}{'-' * (20 - bl)}]  brush {brush_radius}  {status}"
        cv2.putText(out, hud, (12, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)
        if toast[1] > 0:
            cv2.putText(out, toast[0], (12, h - 44), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (170, 235, 255), 1, cv2.LINE_AA)
            toast = (toast[0], toast[1] - dt)

        cv2.imshow("Fogged", out)

        if cv2.getWindowProperty("Fogged", cv2.WND_PROP_VISIBLE) < 1:
            print("Window closed.", flush=True)
            break

        k = cv2.waitKey(1) & 0xFF
        if k in (ord('q'), 27):
            break
        elif k == ord('f'):
            fogging = not fogging
        elif k == ord('c'):
            mask[:] = 0.0
            ambient[:] = 0.0
        elif k == ord('d'):
            debug = not debug
        elif k == ord('r'):
            intro_start = time.time()
        elif k == ord('s'):
            open_settings()
        elif k == 13:                                    # ENTER -> fullscreen
            full = cv2.getWindowProperty("Fogged", cv2.WND_PROP_FULLSCREEN) == cv2.WINDOW_FULLSCREEN
            cv2.setWindowProperty("Fogged", cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_NORMAL if full else cv2.WINDOW_FULLSCREEN)
        elif k in (ord(']'), ord('=')):
            brush_radius = min(90, brush_radius + 4)
            brush = make_brush(brush_radius, BRUSH_FEATHER)
        elif k in (ord('['), ord('-')):
            brush_radius = max(6, brush_radius - 4)
            brush = make_brush(brush_radius, BRUSH_FEATHER)

    breath.stop()
    cap.release()
    if hands is not None:
        hands.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print("\n=== CRASH ===", flush=True)
        print(tb, flush=True)                      # stdout: MediaPipe's logging can't eat this
        try:
            with open("crash.log", "w", encoding="utf-8") as fh:
                fh.write(tb)
            print("(traceback also saved to crash.log)", flush=True)
        except Exception:
            pass
    finally:
        print("\n[done] script finished.", flush=True)
