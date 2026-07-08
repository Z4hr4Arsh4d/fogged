import sys
print("Python:", sys.version)

import cv2
print("OpenCV:", cv2.__version__)

print("Trying camera indexes 0-3 ...")
found = []
for i in range(4):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)   # DirectShow: the Windows-friendly backend
    if cap.isOpened():
        ok, frame = cap.read()
        print(f"  index {i}: opened={cap.isOpened()} read={ok} "
              f"shape={None if frame is None else frame.shape}")
        if ok:
            found.append(i)
        cap.release()
    else:
        print(f"  index {i}: not available")

print("Working camera indexes:", found or "NONE")

if found:
    print("Opening a test window for 5 seconds — look for it!")
    cap = cv2.VideoCapture(found[0], cv2.CAP_DSHOW)
    import time
    t = time.time()
    while time.time() - t < 5:
        ok, frame = cap.read()
        if ok:
            cv2.imshow("TEST - press Q", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()
    print("Test window closed.")