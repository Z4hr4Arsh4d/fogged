# Fogged 🌫️

Breathe on your screen and it **fogs up like real glass** — then **wipe the fog with your fingertip
to write and draw**, and clear it all with an open palm. A real-time, multimodal toy built with
computer vision (hand tracking) and audio (breath detection).

> Work in progress — see `ROADMAP.md` for the full milestone plan. Currently at **M0**.

## Setup
Python 3.10 or 3.11 recommended (best MediaPipe support).
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
A mirrored webcam window opens. **Q or ESC** to quit.

## Note
Breath detection (added at M3) is an approximation — it senses **sustained low-frequency audio**,
not true respiration. It feels magic; it isn't a medical sensor.
