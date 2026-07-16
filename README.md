# Fogged 🌫️

**Breathe on your screen and it fogs up like real glass — then wipe the fog with your fingertip to write in it.**

A real-time, multimodal toy: computer vision reads your hand, audio reads your breath, and the
two meet on a pane of virtual glass. Opens with a chrome-glass "FOGGED" title sequence,
condensation beads up and trickles down, and your writing slowly fogs back over if you leave it.

> **Complete — M0 through M8**, plus a realism pass (patchy condensation, refraction, shaded
> droplet sprites) and a live settings panel.

## Demo

*(drop your demo GIF or a link in `media/` and reference it here)*

## How it works

Everything runs on **two float fields** the size of the video:

| Field | Meaning |
|---|---|
| `ambient` | how fogged the glass *wants* to be |
| `mask` | how fogged it *actually is* — `0` = clear, `1` = fully fogged |

Each frame, the app composites the **sharp webcam feed** where `mask` is `0` against a **frosted
layer** (blurred, washed toward white, cool tint) where it's `1`. That blend *is* the glass.

Three forces act on it:

- **Breath** (audio) raises `ambient` *and* deposits straight onto `mask`, blooming strongest where
  your breath lands — so blowing fogs the glass instantly, no lag.
- **Your fingertip** (vision) subtracts from `mask` — you wipe it clear and write. Strokes are
  smoothed (EMA on the fingertip) to cut MediaPipe jitter into clean, precise lines.
- **Time** evaporates `ambient`, while `mask` creeps back toward `ambient` — so your writing fogs
  back over in ~10 seconds, but the whole pane clears itself if you walk away for a few minutes.

Realism on top of that: **fractal noise** makes the fog's opacity patchy rather than a uniform
wash; **refraction** (`cv2.remap` along the mask's gradient) bends the frosted layer at stroke and
droplet edges, so the glass distorts light instead of only blurring it; and every droplet — the
static dew and the falling runnels — is a **pre-shaded sprite** (lens-lit belly, dark rim,
specular glint, soft shadow), not a flat circle.

## Stack

**Python** · **OpenCV** (capture, blur, compositing) · **MediaPipe** (hand tracking) ·
**NumPy** (the fog fields) · **sounddevice** (breath detection)

## Setup

Python **3.9–3.11**. Dependency versions are pinned deliberately — see below.

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Why the versions are pinned

Two real bugs hit this project, both worth knowing about if you're troubleshooting:

- `opencv-python==4.10.0.84` — OpenCV 5.x shipped with **broken GUI support on Windows**
  (`cv2.imshow()` silently does nothing — no window, no error) *and* a **stricter `cv2.putText`**
  that rejects float images outright (`Assertion failed: img.depth() == CV_8U`). Pin 4.10.
- `mediapipe==0.10.14` — versions after this **removed** the legacy `mp.solutions.hands` API that
  hand tracking uses (`AttributeError: module 'mediapipe' has no attribute 'solutions'`).

If either package gets upgraded later (directly, or as a dependency of something else), reinstall
the pins:
```bash
pip install -r requirements.txt --force-reinstall
```

## Run

```bash
python fogged.py
```

**Blow on your microphone** to fog the glass → **point your index finger** (middle finger down) to
write → **open your palm** to wipe it clean.

The console prints diagnostic checkpoints as it starts (camera backend, MediaPipe status, mic
status). If something goes wrong, the app also writes a full **`crash.log`** next to the script —
paste its contents when asking for help; MediaPipe's own logging can otherwise swallow Python's
error output on Windows.

### Controls

| Input | Action |
|---|---|
| 🌬️ **Blow on the mic** | Fog the glass |
| ☝️ **Point** (index up, middle down) | Write / wipe the fog under your fingertip |
| 🤏 **Pinch** (thumb touching index, while pointing) | Fine write — brush shrinks for detail |
| ✋ **Open palm** | Wide wipe — clear the whole pane |
| 👌 **OK sign** | Save a screenshot to `media/` |
| `F` | Manual fog *(fallback if your mic is quiet)* |
| `C` | Clear instantly · `D` debug mask · `R` replay intro |
| `S` | Open the live settings panel |
| `[` `]` | Brush size · `Enter` fullscreen · `Q`/`Esc` quit |

### Settings panel (`S`)

A small slider window you can adjust while the app runs:

- **Fog density** — the maximum the glass is allowed to fog to
- **Dew opacity** — how visible the static dew glints are
- **Blow sensitivity** — how easily your mic's breath registers
- **Streams** — how often new droplet runnels start

## Tuning

Beyond the settings panel, the deeper feel-constants live at the top of `fogged.py`:

| Constant | Effect |
|---|---|
| `BREATH_RMS_MIN` / `BREATH_LOW_RATIO` | Mic sensitivity and how "breath-like" audio must be |
| `REFORM_RATE` / `EVAPORATE` | How fast writing fogs over / the pane clears on its own |
| `BLOOM_CENTER` / `BLOOM_SIGMA` | Where and how wide your breath lands on the glass |
| `BRUSH_RADIUS` / `BRUSH_FEATHER` / `TIP_SMOOTH` | Wipe size, edge softness, stroke smoothing |
| `NOISE_STRENGTH` / `REFRACT_PX` | Condensation patchiness / how much fog bends light |
| `FOG_WHITE` / `BLUR_KERNEL` / `FOG_TINT` / `VIGNETTE` | How the frosted glass looks |
| `DROPLETS_ON` / `DROPLET_CHANCE` / `DEW_COUNT` | Condensation droplets and dew |

If the webcam doesn't open, change `CAM_INDEX` from `0` to `1` or `2`.

## Roadmap

- [x] **M0** mirrored webcam loop
- [x] **M1** the fog layer — frosted glass over live video
- [x] **M2** fingertip wipe + open-palm clear
- [x] **M3** breath detection + cinematic glass intro
- [x] **M4** fog dynamics — breath bloom, reforming, evaporation
- [x] **M5** polish — wet edges, vignette, 720p
- [x] **M6** gestures — pinch-to-size, OK-sign screenshot
- [x] **M7** droplets — shaded runnels and static dew that trickle and clear trails
- [x] **M8** packaged + documented
- [x] **Realism pass** — fractal-noise condensation, refraction, sprite-shaded droplets
- [x] **Live settings panel** — fog density, dew opacity, blow sensitivity, streams

## An honest note on breath detection

A microphone cannot truly distinguish an exhale from other sounds. Fogged detects **sustained,
low-frequency, broadband audio energy** — what a breath looks like acoustically — and treats that
as breath. It's genuinely responsive (a high whistle won't fool it), but it is **not** a
respiration sensor and isn't presented as one.