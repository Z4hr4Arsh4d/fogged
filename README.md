# Fogged 🌫️

<<<<<<< HEAD
Breathe on your screen and it **fogs up like real glass** — then **wipe the fog with your fingertip
to write and draw**, and clear it all with an open palm. A real-time, multimodal toy built with
computer vision (hand tracking) and audio (breath detection), opening with a cinematic glass-engraved
title sequence.

> **M3 complete — the full magic loop works:** breathe → glass fogs → write with your finger → wipe clear.
> See `ROADMAP.md` for what's next (M4+).
=======
**Breathe on your screen and it fogs up like real glass — then wipe the fog with your fingertip to write in it.**

A real-time, multimodal toy: computer vision reads your hand, audio reads your breath, and the
two meet on a pane of virtual glass. Opens with a cinematic glass-engraved title, condensation
beads up and trickles down, and your writing slowly fogs back over if you leave it.

> **Complete — M0 through M8.**
>>>>>>> 184a4ae (M4-M8)

## How it works

Everything runs on **two float fields** the size of the video:

| Field | Meaning |
|---|---|
<<<<<<< HEAD
| **Breath** (audio) | pushes the mask **up** — fog forms |
| **Your fingertip** (vision) | pushes it **down** — you wipe it clear |
| **Time** *(M4, not yet built)* | will slowly push wiped areas back **up** — fog reforms |
=======
| `ambient` | how fogged the glass *wants* to be |
| `mask` | how fogged it *actually is* — `0` = clear, `1` = fully fogged |
>>>>>>> 184a4ae (M4-M8)

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

<<<<<<< HEAD
- **Python**
- **OpenCV** — webcam capture, blur, compositing, display
- **MediaPipe** — real-time hand / fingertip tracking
- **NumPy** — the fog-mask math
- **sounddevice** — microphone → breath detection

## Setup

Python **3.9–3.11** all work. Dependency versions are **pinned** deliberately — see the note below.
=======
**Python** · **OpenCV** (capture, blur, compositing) · **MediaPipe** (hand tracking) ·
**NumPy** (the fog fields) · **sounddevice** (breath detection)

## Setup

Python **3.9–3.11**. Versions are pinned deliberately — see below.
>>>>>>> 184a4ae (M4-M8)

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Why the versions are pinned

<<<<<<< HEAD
- `opencv-python==4.10.0.84` — newer 5.x builds shipped with broken/missing GUI support on
  Windows, so `cv2.imshow()` silently does nothing. 4.10 has working display.
- `mediapipe==0.10.14` — versions after this removed the legacy `mp.solutions.hands` API that
  hand tracking relies on. Pinning avoids an `AttributeError` on import.
=======
Two real bugs, both worth knowing about:

- `opencv-python==4.10.0.84` — some 5.x builds ship with broken GUI support on Windows, so
  `cv2.imshow()` **silently does nothing**. No window, no error.
- `mediapipe==0.10.14` — versions after this **removed** the legacy `mp.solutions.hands` API that
  hand tracking uses, giving `AttributeError: module 'mediapipe' has no attribute 'solutions'`.
>>>>>>> 184a4ae (M4-M8)

## Run

```bash
python fogged.py
```

<<<<<<< HEAD
A cinematic glass-engraved **"FOGGED"** title fades in over the fogged screen, then hands over to
the live view. **Blow on your microphone** to fog the glass, **point your index finger** (middle
finger down) to write in it, and open your **palm** to wipe it all clear.
=======
**Blow on your microphone** to fog the glass → **point your index finger** (middle finger down) to
write → **open your palm** to wipe it clean.
>>>>>>> 184a4ae (M4-M8)

### Controls

| Input | Action |
|---|---|
<<<<<<< HEAD
| `F` | Manually add fog *(fallback if your mic isn't picking up breath well)* |
| `C` | Clear the glass instantly |
| `[` / `]` | Brush size down / up |
| `D` | Debug view — show the raw fog mask |
| `R` | Replay the intro |
| `Enter` | Toggle fullscreen |
| `Q` / `ESC` | Quit |
=======
| 🌬️ **Blow on the mic** | Fog the glass |
| ☝️ **Point** (index up, middle down) | Write / wipe the fog under your fingertip |
| ✋ **Open palm** | Wipe the whole pane clear |
| 🤏 **Pinch** (thumb + index, while pointing) | Scale the brush live |
| 👌 **OK sign** | Save a screenshot to `media/` |
| `F` | Manual fog *(fallback if your mic is quiet)* |
| `C` | Clear instantly · `D` debug mask · `R` replay intro |
| `[` `]` | Brush size · `Enter` fullscreen · `Q`/`Esc` quit |
>>>>>>> 184a4ae (M4-M8)

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

<<<<<<< HEAD
Feel-constants live at the top of `fogged.py`:

- `BREATH_RMS_MIN` / `BREATH_LOW_RATIO` — how loud / how "breath-like" audio must be to register.
  Lower `BREATH_RMS_MIN` if your mic isn't sensitive enough.
- `BRUSH_RADIUS`, `BRUSH_FEATHER` — wipe brush size and edge softness.
- `BLUR_KERNEL`, `FOG_WHITE`, `FOG_TINT` — how the frosted glass looks.
- `INTRO_SECONDS`, `INTRO_TITLE` — the opening sequence.
=======
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
>>>>>>> 184a4ae (M4-M8)

If the webcam doesn't open, change `CAM_INDEX` from `0` to `1` or `2`.

## Roadmap

- [x] **M0** mirrored webcam loop
- [x] **M1** the fog layer — frosted glass over live video
- [x] **M2** fingertip wipe + open-palm clear
<<<<<<< HEAD
- [x] **M3** breath detection (real microphone input) + cinematic glass intro — **full magic loop**
- [ ] **M4** fog dynamics — condensation reforms over time, local breath bloom
- [ ] **M5** polish — wet edges, stronger frosted look, vignette
- [ ] **M6** gestures — pinch for brush size, screenshot gesture
- [ ] **M7** stretch — droplets, OCR, themes
- [ ] **M8** package + demo video
=======
- [x] **M3** breath detection + cinematic glass intro
- [x] **M4** fog dynamics — breath bloom, reforming, evaporation
- [x] **M5** polish — wet edges, vignette, 720p
- [x] **M6** gestures — pinch-to-size, OK-sign screenshot
- [x] **M7** droplets — condensation beads that trickle and clear trails
- [x] **M8** packaged + documented
>>>>>>> 184a4ae (M4-M8)

## An honest note on breath detection

A microphone cannot truly distinguish an exhale from other sounds. Fogged detects **sustained,
<<<<<<< HEAD
low-frequency, broadband audio energy** — which is what a breath looks like acoustically — and
treats that as "breath." It feels like magic and is genuinely responsive, but it is **not** a
respiration sensor, and isn't presented as one.
=======
low-frequency, broadband audio energy** — what a breath looks like acoustically — and treats that
as breath. It's genuinely responsive (a high whistle won't fool it), but it is **not** a
respiration sensor and isn't presented as one.
>>>>>>> 184a4ae (M4-M8)
