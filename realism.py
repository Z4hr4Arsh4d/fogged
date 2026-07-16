"""Prototype: does noise + refraction actually look like glass? (dev scratch file)"""
import numpy as np, cv2

def fractal_noise(h, w, octaves=5, seed=7):
    """Multi-octave value noise — condensation is patchy at several scales, not uniform."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32); amp = 1.0; total = 0.0
    for o in range(octaves):
        step = 2 ** (octaves - o)                       # coarse -> fine
        gh, gw = max(2, h // step), max(2, w // step)
        g = rng.random((gh, gw)).astype(np.float32)
        out += cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC) * amp
        total += amp; amp *= 0.5
    out /= total
    return np.clip((out - out.min()) / (out.max() - out.min() + 1e-9), 0, 1)

def refract(frame, density, strength=9.0):
    """Fog doesn't just blur — it bends light. Displace pixels along the density gradient."""
    h, w = density.shape
    gx = cv2.Sobel(density, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(density, cv2.CV_32F, 0, 1, ksize=5)
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    map_x = np.clip(xs + gx * strength, 0, w - 1)
    map_y = np.clip(ys + gy * strength, 0, h - 1)
    return cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

h, w = 360, 640
n = fractal_noise(h, w)
print("noise: mean=%.2f  min=%.2f  max=%.2f  std=%.3f" % (n.mean(), n.min(), n.max(), n.std()))
assert 0.05 < n.std() < 0.35, "noise should be varied but not chaotic"

# is it patchy at multiple scales? compare local variance vs a single-scale grid
coarse = cv2.resize(cv2.resize(n, (10, 6)), (w, h))
detail = n - coarse
print("coarse structure std=%.3f  fine detail std=%.3f  (want BOTH non-zero = multi-scale)" % (coarse.std(), detail.std()))
assert coarse.std() > 0.02 and detail.std() > 0.02

# refraction actually moves pixels
frame = np.zeros((h, w, 3), np.uint8)
cv2.line(frame, (0, 180), (w, 180), (255, 255, 255), 2)     # a sharp horizontal line
mask = np.ones((h, w), np.float32)
mask[150:210, 200:400] = 0.0                                 # a wiped rectangle
dens = mask * (0.7 + 0.3 * n)
r = refract(frame, dens, 9.0)
diff = np.abs(r.astype(int) - frame.astype(int)).sum()
print("refraction displaced pixels (diff=%d, want >0)" % diff)
assert diff > 0, "refraction should bend the image at fog boundaries"
print("\nREALISM PROTOTYPE OK — noise is multi-scale, refraction bends light")
