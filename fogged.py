"""
Fogged — breathe on the glass, wipe the fog to write.
M0: mirrored webcam loop at a steady frame rate. (The canvas everything else builds on.)
Controls: Q or ESC to quit.
"""
import time
import cv2

CAM_INDEX = 0            # change to 1/2 if your webcam isn't the default
WIDTH, HEIGHT = 840, 680 # keep modest — we'll blur every frame later


def main():
    cap = cv2.VideoCapture(CAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    if not cap.isOpened():
        print("Could not open the webcam. Try changing CAM_INDEX (0, 1, 2...).")
        return

    print("Fogged — M0 running. Press Q or ESC to quit.")
    prev = time.time()
    fps = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Failed to read a frame from the camera.")
            break

        frame = cv2.flip(frame, 1)          # mirror, so it feels like a selfie / a real window

        now = time.time()
        dt = now - prev
        prev = now
        if dt > 0:
            fps = 0.9 * fps + 0.1 * (1.0 / dt)   # smoothed FPS

        cv2.putText(frame, f"{fps:4.1f} FPS", (10, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow("Fogged", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):            # Q or ESC
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
