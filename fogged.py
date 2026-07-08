"""
Fogged — breathe on the glass, wipe the fog to write.

M0  mirrored webcam loop
M1  the fog layer  (a float mask: 0 = clear glass, 1 = fully fogged)
M2  wipe with your fingertip; open palm clears everything

Controls
  F        toggle fog on/off        (stand-in for breath until M3)
  C        clear the fog instantly
  [ / ]    brush size down / up
  D        debug view (show the raw mask)
  Q / ESC  quit
"""
import time

import cv2
import numpy as np

print("[1] importing mediapipe ...", flush=True)
mp_hands = None
try:
    # MediaPipe moved things around between versions. Try the paths that actually exist,
    # newest-style first. `import mediapipe as mp; mp.solutions.hands` fails on some 0.10.x builds.
    try:
        from mediapipe.python.solutions import hands as mp_hands       # 0.10.x, explicit
    except Exception:
        import mediapipe as mp
        mp_hands = mp.solutions.hands                                  # older / lazy-attr builds
    HAS_MP = mp_hands is not None
    print(f"[1] mediapipe OK (hands module: {mp_hands.__name__})", flush=True)
except Exception as e:
    HAS_MP = False
    print(f"[1] mediapipe FAILED -> {type(e).__name__}: {e}", flush=True)
    print("    (running M1 only: fog works, no hand tracking)", flush=True)

# ---------------------------------------------------------------- config
CAM_INDEX = 0                 # try 1 or 2 if the webcam doesn't open
WIDTH, HEIGHT = 640, 480      # we blur every frame — resolution is our perf budget

BLUR_KERNEL   = 31            # frosted-glass softness (must be odd)
BLUR_SCALE    = 0.25          # blur a small copy, then upscale (big speedup)
FOG_WHITE     = 0.55          # how much the frosted layer washes toward white
FOG_TINT      = (14, 6, -4)   # cool blue-ish condensation tint (B, G, R)

FOG_IN_RATE   = 1.4           # how fast fog builds while "breathing"
BRUSH_RADIUS  = 26            # fingertip wipe radius, px
BRUSH_FEATHER = 0.55          # 0 = hard edge, 1 = very soft
PALM_FADE     = 3.5           # how fast an open palm clears the glass

FINGERTIPS = (8, 12, 16, 20)  # index, middle, ring, pinky tips
PIPS       = (6, 10, 14, 18)  # the joint below each of those


# ---------------------------------------------------------------- fog mask
def make_brush(radius: int, feather: float) -> np.ndarray:
    """A soft-edged circular stamp in [0,1] — 1 at the centre, 0 at the rim."""
    r = max(1, int(radius))
    ys, xs = np.mgrid[-r:r + 1, -r:r + 1]
    dist = np.sqrt(xs * xs + ys * ys) / r          # 0 at centre, 1 at the rim
    inner = max(0.001, 1.0 - feather)
    stamp = np.clip((1.0 - dist) / (1.0 - inner + 1e-6), 0.0, 1.0)
    return stamp.astype(np.float32)


def wipe(mask: np.ndarray, cx: int, cy: int, brush: np.ndarray) -> None:
    """Subtract the brush from the mask at (cx, cy), clipped to the frame. In-place."""
    r = brush.shape[0] // 2
    h, w = mask.shape
    x0, x1 = cx - r, cx + r + 1
    y0, y1 = cy - r, cy + r + 1
    bx0, by0 = max(0, -x0), max(0, -y0)                  # how much of the brush is off-frame
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x0 >= x1 or y0 >= y1:
        return                                            # entirely off-screen
    sub = brush[by0:by0 + (y1 - y0), bx0:bx0 + (x1 - x0)]
    region = mask[y0:y1, x0:x1]
    np.subtract(region, sub, out=region)
    np.clip(region, 0.0, 1.0, out=region)


def wipe_line(mask, p0, p1, brush) -> None:
    """Stamp along the segment p0->p1 so fast strokes stay connected (no dotted gaps)."""
    (x0, y0), (x1, y1) = p0, p1
    dist = max(abs(x1 - x0), abs(y1 - y0))
    steps = max(1, int(dist / max(1, brush.shape[0] * 0.25)))
    for i in range(steps + 1):
        t = i / steps
        wipe(mask, int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t)), brush)


def frosted(frame: np.ndarray) -> np.ndarray:
    """A blurred, whitened, cool-tinted version of the frame: what the glass looks like fogged."""
    small = cv2.resize(frame, None, fx=BLUR_SCALE, fy=BLUR_SCALE, interpolation=cv2.INTER_LINEAR)
    small = cv2.GaussianBlur(small, (BLUR_KERNEL, BLUR_KERNEL), 0)
    blur = cv2.resize(small, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
    out = blur.astype(np.float32)
    out += np.array(FOG_TINT, dtype=np.float32)                 # cool condensation cast
    out = out * (1.0 - FOG_WHITE) + 255.0 * FOG_WHITE           # wash toward white
    return np.clip(out, 0, 255)


def composite(frame: np.ndarray, fog: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """sharp where mask=0, frosted where mask=1."""
    m = mask[:, :, None]                                        # H,W -> H,W,1 broadcasts over BGR
    out = frame.astype(np.float32) * (1.0 - m) + fog * m
    return out.astype(np.uint8)


# ---------------------------------------------------------------- hand helpers
def finger_extended(lm, tip: int, pip: int) -> bool:
    """A finger is 'up' when its tip sits above its lower joint (smaller y, image coords)."""
    return lm.landmark[tip].y < lm.landmark[pip].y


def is_open_palm(lm) -> bool:
    return sum(finger_extended(lm, t, p) for t, p in zip(FINGERTIPS, PIPS)) >= 4


def is_pointing(lm) -> bool:
    """Index up, middle down — the writing pose."""
    return finger_extended(lm, 8, 6) and not finger_extended(lm, 12, 10)


# ---------------------------------------------------------------- camera
def open_camera(index: int):
    """Open the webcam, trying the Windows-friendly DirectShow backend first.

    Plain cv2.VideoCapture(index) frequently 'opens' on Windows but then delivers
    no frames, so we verify with an actual read() before accepting a backend.
    """
    backends = [("CAP_DSHOW", cv2.CAP_DSHOW), ("CAP_MSMF", cv2.CAP_MSMF), ("default", None)]
    for name, backend in backends:
        print(f"[3] trying backend {name} on index {index} ...", flush=True)
        cap = cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)
        opened = cap.isOpened()
        print(f"[3]   isOpened={opened}", flush=True)
        if opened:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
            ok, fr = cap.read()                     # a real read is the only honest test
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
        print("[4] initialising MediaPipe Hands (first run downloads a model, can take ~30s) ...", flush=True)
        try:
            hands = mp_hands.Hands(
                max_num_hands=1, min_detection_confidence=0.6, min_tracking_confidence=0.5)
            print("[4] MediaPipe Hands ready", flush=True)
        except Exception as e:
            print(f"[4] MediaPipe Hands FAILED -> {type(e).__name__}: {e}", flush=True)
            print("    continuing without hand tracking", flush=True)
            hands = None
    else:
        print("mediapipe not installed — running M1 only (no hand tracking).")
        print("   pip install mediapipe")

    mask = np.ones((HEIGHT, WIDTH), np.float32)   # start fully fogged
    brush_radius = BRUSH_RADIUS
    brush = make_brush(brush_radius, BRUSH_FEATHER)
    fogging = False
    debug = False
    last_tip = None
    prev_t = time.time()
    fps = 0.0

    print("[5] entering main loop — the window should appear now", flush=True)
    print(f"    hand tracking: {'ON' if hands is not None else 'OFF (fog + keyboard only)'}", flush=True)
    print("Fogged — M2.  F fog | C clear | [ ] brush | D debug | Q quit", flush=True)

    frame_no = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Camera stopped returning frames — exiting.")
            break
        frame = cv2.flip(frame, 1)                 # mirror: feels like looking at a window
        h, w = frame.shape[:2]
        if mask.shape != (h, w):                   # camera gave us a different size
            mask = np.ones((h, w), np.float32)

        now = time.time()
        dt = min(0.1, now - prev_t)                # clamp: a stutter shouldn't nuke the fog
        prev_t = now
        if dt > 0:
            fps = 0.9 * fps + 0.1 / dt

        # --- fog builds while "breathing" (keyboard stand-in until M3) ---
        if fogging:
            mask += FOG_IN_RATE * dt
            np.clip(mask, 0.0, 1.0, out=mask)

        # --- hands: point to write, open palm to clear ---
        status = ""
        if hands is not None:
            res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))   # MediaPipe wants RGB
            if res.multi_hand_landmarks:
                lm = res.multi_hand_landmarks[0]
                if is_open_palm(lm):
                    mask -= PALM_FADE * dt                                 # wipe it all away
                    np.clip(mask, 0.0, 1.0, out=mask)
                    last_tip = None
                    status = "PALM - wiping"
                elif is_pointing(lm):
                    tip = lm.landmark[8]
                    cx, cy = int(tip.x * w), int(tip.y * h)                # already mirrored: frame was flipped
                    if last_tip is not None:
                        wipe_line(mask, last_tip, (cx, cy), brush)
                    else:
                        wipe(mask, cx, cy, brush)
                    last_tip = (cx, cy)
                    status = "WRITING"
                    cv2.circle(frame, (cx, cy), brush_radius, (255, 255, 255), 1)
                else:
                    last_tip = None
            else:
                last_tip = None

        fog = frosted(frame)
        out = composite(frame, fog, mask)

        if debug:
            out = cv2.cvtColor((mask * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)

        cv2.putText(out, f"{fps:4.1f} FPS", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        hud = f"[F]og {'ON' if fogging else 'off'}  brush {brush_radius}  {status}"
        cv2.putText(out, hud, (10, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)
        cv2.imshow("Fogged", out)
        frame_no += 1
        if frame_no == 1:
            print("[6] first frame drawn — if you see no window, it is behind other windows "
                  "or HighGUI is broken", flush=True)
            try:
                cv2.setWindowProperty("Fogged", cv2.WND_PROP_TOPMOST, 1)   # force it to the front
            except Exception:
                pass

        # if the user closed the window with the X, stop cleanly
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
        elif k == ord('d'):
            debug = not debug
        elif k in (ord(']'), ord('=')):
            brush_radius = min(90, brush_radius + 4); brush = make_brush(brush_radius, BRUSH_FEATHER)
        elif k in (ord('['), ord('-')):
            brush_radius = max(6, brush_radius - 4); brush = make_brush(brush_radius, BRUSH_FEATHER)

    cap.release()
    if hands is not None:
        hands.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception:
        print("\n=== CRASH ===", flush=True)
        traceback.print_exc()
    finally:
        print("\n[done] script finished. If no window appeared, paste ALL the [n] lines above.", flush=True)
        try:
            input("Press Enter to close...")     # keeps the console open if double-clicked
        except EOFError:
            pass