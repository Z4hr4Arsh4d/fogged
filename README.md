# Fogged 🌫️

Breathe on your screen and it **fogs up like real glass** — then **wipe the fog with your fingertip
to write and draw**, and clear it all with an open palm. A real-time, multimodal toy built with
computer vision (hand tracking) and audio (breath detection).

> Work in progress. Currently at **M2** — fog + fingertip writing both work.
> Breath detection lands at M3. See `ROADMAP.md` for the full plan.

## How it works

Everything runs on a single **fog mask** — a float image where `0` is clear glass and `1` is fully
fogged. Each frame, the app composites the **sharp webcam feed** where the mask is `0` against a
**frosted layer** (blurred, washed toward white, cool blue tint) where it's `1`. That blend *is* the glass.

Three forces push on that mask:

| Force | Effect |
|---|---|
| **Breath** (audio, M3) | pushes the mask **up** — fog forms |
| **Your fingertip** (vision) | pushes it **down** — you wipe it clear |
| **Time** (M4) | slowly pushes wiped areas back **up** — fog reforms |

That's the whole design.

## Stack

- **Python**
- **OpenCV** — webcam capture, blur, compositing, display
- **MediaPipe** — real-time hand / fingertip tracking
- **NumPy** — the fog-mask math
- **sounddevice** *(M3)* — microphone → breath detection

## Setup

Python **3.10 or 3.11** recommended — MediaPipe doesn't support the newest versions yet.

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
python fogged.py
```

Press **F** to fog up the glass, point your **index finger** at the camera, and write your name.
**Open your palm** to wipe it clean.

### Controls

| Key | Action |
|---|---|
| `F` | Toggle fog on/off *(stand-in for breath until M3)* |
| `C` | Clear the glass instantly |
| `[` / `]` | Brush size down / up |
| `D` | Debug view — show the raw fog mask |
| `Q` / `ESC` | Quit |

### Gestures

- **Point** (index up, middle down) → write / wipe the fog under your fingertip
- **Open palm** (all fingers extended) → wipe the whole glass clear

## Tuning

All the feel-constants live at the top of `fogged.py` — brush size and softness, fog build rate,
blur strength, how white the condensation gets. Adjust to taste.

If the webcam doesn't open, change `CAM_INDEX` from `0` to `1` or `2`.

## Roadmap

- [x] **M0** mirrored webcam loop
- [x] **M1** the fog layer — frosted glass rendering over live video
- [x] **M2** fingertip wipe + open-palm clear
- [ ] **M3** breath detection → **MVP** (the full magic loop)
- [ ] **M4** fog dynamics — condensation reforms over time
- [ ] **M5** polish — wet edges, stronger frosted look, vignette
- [ ] **M6** gestures — pinch for brush size, screenshot gesture
- [ ] **M7** stretch — droplets, OCR, themes
- [ ] **M8** package + demo video

