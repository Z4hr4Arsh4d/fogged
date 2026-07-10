# Fogged 🌫️

Breathe on your screen and it **fogs up like real glass** — then **wipe the fog with your fingertip
to write and draw**, and clear it all with an open palm. A real-time, multimodal toy built with
computer vision (hand tracking) and audio (breath detection), opening with a cinematic glass-engraved
title sequence.

> **M3 complete — the full magic loop works:** breathe → glass fogs → write with your finger → wipe clear.
> See `ROADMAP.md` for what's next (M4+).

## How it works

Everything runs on a single **fog mask** — a float image where `0` is clear glass and `1` is fully
fogged. Each frame, the app composites the **sharp webcam feed** where the mask is `0` against a
**frosted layer** (blurred, washed toward white, cool blue tint) where it's `1`. That blend *is* the glass.

Three forces push on that mask:

| Force | Effect |
|---|---|
| **Breath** (audio) | pushes the mask **up** — fog forms |
| **Your fingertip** (vision) | pushes it **down** — you wipe it clear |
| **Time** *(M4, not yet built)* | will slowly push wiped areas back **up** — fog reforms |

That's the whole design.

## Stack

- **Python**
- **OpenCV** — webcam capture, blur, compositing, display
- **MediaPipe** — real-time hand / fingertip tracking
- **NumPy** — the fog-mask math
- **sounddevice** — microphone → breath detection

## Setup

Python **3.9–3.11** all work. Dependency versions are **pinned** deliberately — see the note below.

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Why the versions are pinned

- `opencv-python==4.10.0.84` — newer 5.x builds shipped with broken/missing GUI support on
  Windows, so `cv2.imshow()` silently does nothing. 4.10 has working display.
- `mediapipe==0.10.14` — versions after this removed the legacy `mp.solutions.hands` API that
  hand tracking relies on. Pinning avoids an `AttributeError` on import.

## Run

```bash
python fogged.py
```

A cinematic glass-engraved **"FOGGED"** title fades in over the fogged screen, then hands over to
the live view. **Blow on your microphone** to fog the glass, **point your index finger** (middle
finger down) to write in it, and open your **palm** to wipe it all clear.

### Controls

| Key | Action |
|---|---|
| `F` | Manually add fog *(fallback if your mic isn't picking up breath well)* |
| `C` | Clear the glass instantly |
| `[` / `]` | Brush size down / up |
| `D` | Debug view — show the raw fog mask |
| `R` | Replay the intro |
| `Enter` | Toggle fullscreen |
| `Q` / `ESC` | Quit |

### Gestures

- **Point** (index up, middle down) → write / wipe the fog under your fingertip
- **Open palm** (all fingers extended) → wipe the whole glass clear

## Tuning

Feel-constants live at the top of `fogged.py`:

- `BREATH_RMS_MIN` / `BREATH_LOW_RATIO` — how loud / how "breath-like" audio must be to register.
  Lower `BREATH_RMS_MIN` if your mic isn't sensitive enough.
- `BRUSH_RADIUS`, `BRUSH_FEATHER` — wipe brush size and edge softness.
- `BLUR_KERNEL`, `FOG_WHITE`, `FOG_TINT` — how the frosted glass looks.
- `INTRO_SECONDS`, `INTRO_TITLE` — the opening sequence.

If the webcam doesn't open, change `CAM_INDEX` from `0` to `1` or `2`.

## Roadmap

- [x] **M0** mirrored webcam loop
- [x] **M1** the fog layer — frosted glass rendering over live video
- [x] **M2** fingertip wipe + open-palm clear
- [x] **M3** breath detection (real microphone input) + cinematic glass intro — **full magic loop**
- [ ] **M4** fog dynamics — condensation reforms over time, local breath bloom
- [ ] **M5** polish — wet edges, stronger frosted look, vignette
- [ ] **M6** gestures — pinch for brush size, screenshot gesture
- [ ] **M7** stretch — droplets, OCR, themes
- [ ] **M8** package + demo video

## An honest note on breath detection

A microphone cannot truly distinguish an exhale from other sounds. Fogged detects **sustained,
low-frequency, broadband audio energy** — which is what a breath looks like acoustically — and
treats that as "breath." It feels like magic and is genuinely responsive, but it is **not** a
respiration sensor, and isn't presented as one.
