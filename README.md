# Fogged 🌫️

**Breathe on your screen and it fogs up like real glass — then wipe the fog with your fingertip to write in it.**

A real-time, multimodal toy: computer vision reads your hand, audio reads your breath, and the
two meet on a pane of virtual glass. Opens with a cinematic glass-engraved title, condensation
beads up and trickles down, and your writing slowly fogs back over if you leave it.

> **Complete — M0 through M8.**

## How it works

Everything runs on **two float fields** the size of the video:

| Field | Meaning |
|---|---|
| `ambient` | how fogged the glass *wants* to be |
| `mask` | how fogged it *actually is* — `0` = clear, `1` = fully fogged |

Each frame, the app composites the **sharp webcam feed** where `mask` is `0` against a **frosted
layer** (blurred, washed toward white, cool blue tint) where it's `1`. That blend *is* the glass.

Three forces act on it:

- **Breath** (audio) raises `ambient` *and* deposits straight onto `mask`, blooming strongest where
  your breath lands — so blowing fogs the glass instantly.
- **Your fingertip** (vision) subtracts from `mask` — you wipe it clear and write.
- **Time** evaporates `ambient`, while `mask` creeps back toward `ambient`.

That two-field split is what makes it feel real: your **writing fogs back over in ~10 seconds**,
but walk away for a few minutes and the **whole pane clears itself**. One field couldn't do both.

## Stack

**Python** · **OpenCV** (capture, blur, compositing) · **MediaPipe** (hand tracking) ·
**NumPy** (the fog fields) · **sounddevice** (breath detection)

## Setup

Python **3.9–3.11**. Versions are pinned deliberately — see below.

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Why the versions are pinned

Two real bugs, both worth knowing about:

- `opencv-python==4.10.0.84` — some 5.x builds ship with broken GUI support on Windows, so
  `cv2.imshow()` **silently does nothing**. No window, no error.
- `mediapipe==0.10.14` — versions after this **removed** the legacy `mp.solutions.hands` API that
  hand tracking uses, giving `AttributeError: module 'mediapipe' has no attribute 'solutions'`.

## Run

```bash
python fogged.py
```

**Blow on your microphone** to fog the glass → **point your index finger** (middle finger down) to
write → **open your palm** to wipe it clean.

### Controls

| Input | Action |
|---|---|
| 🌬️ **Blow on the mic** | Fog the glass |
| ☝️ **Point** (index up, middle down) | Write / wipe the fog under your fingertip |
| ✋ **Open palm** | Wipe the whole pane clear |
| 🤏 **Pinch** (thumb + index, while pointing) | Scale the brush live |
| 👌 **OK sign** | Save a screenshot to `media/` |
| `F` | Manual fog *(fallback if your mic is quiet)* |
| `C` | Clear instantly · `D` debug mask · `R` replay intro |
| `[` `]` | Brush size · `Enter` fullscreen · `Q`/`Esc` quit |

## Features

- **Cinematic intro** — an engraved glass "FOGGED" title condenses in, glows, and dissolves
- **Real breath detection** — sustained low-frequency audio, with a live meter in the HUD
- **Breath bloom** — fog forms strongest where your breath actually lands, not uniformly
- **Condensation dynamics** — writing fogs back over; the pane evaporates if left alone
- **Droplets** — beads form on fogged glass and trickle down, clearing trails behind them
- **Wet edges** — fresh strokes catch a noise-broken bright rim, like real condensation
- **Patchy condensation** — fractal-noise density, not a uniform wash
- **Refraction** — the fog bends light along its edges instead of only blurring
- **Smoothed strokes** — fingertip jitter is filtered, so writing feels precise
- **Gestures** — pinch-to-size, palm-to-wipe, OK-sign screenshots

## Tuning

The feel-constants are all at the top of `fogged.py`:

| Constant | Effect |
|---|---|
| `BREATH_RMS_MIN` | Mic sensitivity — **lower this if breath isn't registering** |
| `BREATH_LOW_RATIO` | How "breath-like" audio must be (share of energy under 500 Hz) |
| `REFORM_RATE` / `EVAPORATE` | How fast writing fogs over / the pane clears |
| `BLOOM_CENTER` / `BLOOM_SIGMA` | Where and how wide your breath lands |
| `BRUSH_RADIUS` / `BRUSH_FEATHER` | Wipe size and edge softness |
| `FOG_WHITE` / `BLUR_KERNEL` / `FOG_TINT` | How the frosted glass looks |
| `NOISE_STRENGTH` | How patchy the condensation is (0 = uniform) |
| `REFRACT_PX` | How far fog bends light at its edges (0 = off, cheapest) |
| `TIP_SMOOTH` | Stroke smoothing — lower = smoother lines, slightly more lag |
| `DROPLETS_ON` / `DROPLET_CHANCE` | Condensation droplets |

If the webcam doesn't open, change `CAM_INDEX` from `0` to `1` or `2`.

## Roadmap

- [x] **M0** mirrored webcam loop
- [x] **M1** the fog layer — frosted glass over live video
- [x] **M2** fingertip wipe + open-palm clear
- [x] **M3** breath detection + cinematic glass intro
- [x] **M4** fog dynamics — breath bloom, reforming, evaporation
- [x] **M5** polish — wet edges, vignette, 720p
- [x] **M6** gestures — pinch-to-size, OK-sign screenshot
- [x] **M7** droplets — condensation beads that trickle and clear trails
- [x] **M8** packaged + documented

## An honest note on breath detection

A microphone cannot truly distinguish an exhale from other sounds. Fogged detects **sustained,
low-frequency, broadband audio energy** — what a breath looks like acoustically — and treats that
as breath. It's genuinely responsive (a high whistle won't fool it), but it is **not** a
respiration sensor and isn't presented as one.
