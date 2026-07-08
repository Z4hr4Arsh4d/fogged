# Fogged — Build Roadmap

A webcam app where your **breath fogs up the screen like real glass**, and you **wipe the fog
with your fingertip to write and draw** — then an open palm clears it. Multimodal: computer vision
(hand tracking) + audio (breath detection), in real time.

The magic is one tight loop: **breathe → fog appears → wipe with your finger → writing shows through.**
Everything else in this plan is polish. Build the loop first.

---

## Tech stack

- **Python** — the whole thing.
- **OpenCV** (`opencv-python`) — webcam capture, image blending, blur, display.
- **MediaPipe** (`mediapipe`) — real-time hand / fingertip tracking (does the hard CV for you).
- **sounddevice** + **numpy** — read the microphone and detect breath.
- (optional, stretch) **Pillow**, **pytesseract** (OCR), a shader lib — only if you get to M7.

Install: `pip install opencv-python mediapipe sounddevice numpy`

---

## How it works (the mental model)

- A **fog mask** — a single-channel float image the same size as the video, values `0`(clear) → `1`(fully fogged).
- Each frame you composite: **sharp webcam where the mask is 0**, and a **blurred, whitened "frosted" version where the mask is 1**. That blend *is* the glass.
- **Breath** (audio) pushes the mask **up** (more fog). **Your fingertip** (vision) pushes it **down** (wipes clear). **Time** slowly pushes wiped areas back up (fog reforms).

Three forces on one mask. That's the entire design.

---

## Scope discipline (read this twice)

**MVP = M0–M3.** That's the complete magic and a killer demo. M4–M5 make it feel alive and look real.
M6–M7 are garnish — pick *one or two*, not all of them. The original idea had a dozen features and six
gestures; building all of that is how this project dies half-finished. **The wow is the loop, not the feature count.**

---

## Milestone 0 — Webcam loop

**Goal:** a mirrored, smooth webcam window.

**Build:** capture from the webcam with OpenCV, flip horizontally (selfie view), show it in a window, print FPS. A clean quit key.

**Deliverable:** live mirrored video at a steady frame rate.

**Gotchas:** pick a working camera index; target **640×480** (you'll blur every frame later — resolution is your performance budget).

---

## Milestone 1 — The fog layer (the *look*)

**Goal:** frosted glass over the video.

**Build:** create the fog **mask** (float array, start it fully fogged = all `1`). Make a **frosted version** of the frame — a heavy Gaussian blur, brightened toward white, low contrast. Composite: `output = sharp*(1-mask) + frosted*mask` (broadcast the mask to 3 channels). Add a subtle cool white tint so it reads as condensation, not just blur.

**Deliverable:** the webcam looks like it's behind a steamed-up window.

**Gotchas:** blurring a full frame every tick is expensive — **blur a downscaled copy and upscale**, or blur at lower res. Keep the mask as `float32` and only convert for display.

---

## Milestone 2 — Wipe with your finger (the *interaction*)

**Goal:** clear the fog where you touch — i.e. write in it.

**Build:** run **MediaPipe Hands**, grab the **index fingertip** (landmark 8), map it to pixel coords. Where the fingertip is, **paint the mask toward 0** with a soft, feathered circular brush. **Interpolate between last and current fingertip** each frame so fast strokes stay connected (no dotted gaps). Detect **open palm** (all fingers extended) → fade the whole mask to 0 (wipe everything).

**Deliverable:** you can already write in the fog with your finger and clear it with your palm. (Fake the fog with a key press for now — breath comes next.)

**Gotchas:** MediaPipe wants **RGB**, OpenCV gives **BGR** — convert. You flipped the frame in M0, so flip the landmark x too or your finger will be mirrored. Open-palm heuristic: each non-thumb fingertip is above (smaller y than) its middle joint.

> After M2 you already have most of the magic. Breath is the signature that makes it unforgettable.

---

## Milestone 3 — Breath detection (the *signature*) → **MVP complete**

**Goal:** breathing on the mic makes fog appear.

**Build:** open the mic with **sounddevice** in a callback (its own thread). Each audio block, compute **RMS (loudness)** and **low-frequency energy** (FFT, sum magnitude in ~50–400 Hz — breath is low, broadband, sustained). When both stay above a threshold for a short sustained window, flag **breath = active** and expose a smoothed `breath_level` to the main loop via a thread-safe variable. In the video loop, while breathing, **raise the mask** (globally, or weighted toward the lower-centre where breath would land) up toward `1`.

**Deliverable:** the full loop — breathe → glass fogs → wipe with your finger → your writing shows through. **This is the demo.**

**Gotchas:** a mic can't truly distinguish an exhale from other low noise — you're **approximating** (sustained low-band energy + amplitude + duration). It'll feel magic, but **frame it honestly** as "sustained-breath audio detection," not medical respiration sensing. Calibrate the threshold to the user's room; add a quick ambient-noise calibration on startup.

---

## Milestone 4 — Fog dynamics (make it feel alive)

**Goal:** fog behaves like real condensation.

**Build:** **reforming** — wiped areas slowly creep back toward fogged over time (a gentle pull of the mask toward an ambient level, faster while breathing). **Local breath** — fog blooms from a region rather than uniformly. **Decay** — with no breath and no touching, fog very slowly thins (evaporates). Tune all rates to taste.

**Deliverable:** write something, stop, and watch it slowly fog back over — that "it's alive" moment.

**Gotchas:** balance the rates so writing doesn't vanish before you finish, but does eventually fade. Expose them as constants at the top of the file.

---

## Milestone 5 — Polish the look (make it *beautiful*)

**Goal:** it genuinely looks like glass, not a blur filter.

**Build:** stronger **frosted** treatment (bigger blur + slight desaturation + cool tint), **feathered wipe edges** (soft brush falloff so strokes look wet, not cut), a faint **wet-edge highlight** along fresh wipes, and a subtle **vignette**. Optionally a moisture "smear" where you dragged.

**Deliverable:** screenshot-worthy frames — the difference between "cool demo" and "how did you make that."

**Gotchas:** every effect costs frame time; keep it smooth (30 fps beats a pretty 12 fps). Profile before piling on.

---

## Milestone 6 — Gestures & extras (stretch — pick a couple)

**Goal:** a few delightful controls, not a gesture zoo.

**Build (choose 1–2):** **pinch** (thumb–index distance, landmarks 4 & 8) = change brush size · **peace sign** = clear all · **"OK" sign** = save a screenshot (`cv2.imwrite`) · a colour/tint toggle.

**Deliverable:** the app feels intentional and controllable.

**Gotchas:** more gestures = more misfires. Keep the set tiny and reliable.

---

## Milestone 7 — Wow stretch (optional — do *at most one*)

Only if you have time and momentum. Each is a rabbit hole:
- **Moisture droplets** that form and trickle down, distorting what's behind them.
- **OCR** the wiped writing into real text (`pytesseract`) — "write on the glass, it types it out."
- **Secret-message mode** — a hidden message that only appears when you fog the glass and wipe over it.
- **Themes** — rain-on-window at night, a bathroom mirror, a car windscreen.

**Reminder:** these are garnish. A polished M0–M5 with none of these beats a buggy build with all of them.

---

## Milestone 8 — Package & demo

**Goal:** ship it and capture it.

**Build:** `requirements.txt`, tunable constants at the top, a `README` (what it is, install, run, the honest "sustained-breath detection" note, a demo GIF), and a **clean 20–30s screen recording** — the deliverable, since the magic is motion: breathe → glass fogs → finger-write your name → palm-wipe → it reforms.

**Deliverable:** a repo + a demo video that makes people say "wait, how?"

---

## Suggested structure
```
fogged/
├── fogged.py          # main loop (or split: video.py / audio.py / fog.py)
├── requirements.txt
├── README.md
└── media/             # demo gif/screens
```

## Build order & pacing
`M0 → M1 → M2 → M3` is the whole magic — ship-worthy on its own. `M4 → M5` make it alive and gorgeous.
`M6`/`M7` only if you're enjoying it. Get to the working loop **fast**, then polish — don't polish fog physics before the loop exists.
