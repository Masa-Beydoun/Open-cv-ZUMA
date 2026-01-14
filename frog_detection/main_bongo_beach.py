import cv2
import numpy as np
import time
import os
import mss

try:
    from constants import *
    from roi.detect_roi import analyze_game_screen
    from frog_detection.FrogTemplateDetector import FrogTemplateDetector
except ImportError:
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from constants import *
    from roi.detect_roi import analyze_game_screen
    from FrogTemplateDetector import FrogTemplateDetector


if __name__ == "__main__":

    window_name = "Zuma Frog Detector - Template"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 600, 450)

    with mss.mss() as sct:
        full_monitor = sct.monitors[MONITOR]

        capture_area = None
        last_recheck_time = 0
        RECHECK_INTERVAL = 2  # seconds

        fps = 0
        frame_count = 0
        start_time = time.time()

        frog_detector = FrogTemplateDetector(
            templates_dir="frog_detection/templates",
            threshold=0.62
        )

        print("[MAIN] Starting main loop...")

        while True:
            loop_start = time.time()

            if loop_start - last_recheck_time > RECHECK_INTERVAL:
                screenshot = np.array(sct.grab(full_monitor))
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

                region_data = analyze_game_screen(screenshot)
                if region_data:
                    capture_area = region_data.to_mss_dict(
                        full_monitor["left"],
                        full_monitor["top"]
                    )

                last_recheck_time = loop_start

            if capture_area:
                try:
                    sct_img = sct.grab(capture_area)
                    frame = np.array(sct_img)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                    frog_box, score = frog_detector.detect(frame)

                    if frog_box:
                        x, y, w, h = frog_box

                        cv2.rectangle(
                            frame,
                            (x, y),
                            (x + w, y + h),
                            (0, 0, 0),
                            2
                        )

                        cv2.putText(
                            frame,
                            f"FROG {score:.2f}",
                            (x, y - 8),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 0, 0),
                            2
                        )

                    frame_count += 1
                    elapsed = time.time() - start_time
                    if elapsed >= 1.0:
                        fps = frame_count / elapsed
                        frame_count = 0
                        start_time = time.time()

                    cv2.putText(
                        frame,
                        f"FPS: {int(fps)}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2
                    )

                    cv2.imshow(window_name, frame)

                except Exception as e:
                    print(f"[ERROR] {e}")

            else:
                blank = np.zeros((300, 500, 3), dtype=np.uint8)
                cv2.putText(
                    blank,
                    "Searching for game region...",
                    (20, 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 255),
                    2
                )
                cv2.imshow(window_name, blank)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cv2.destroyAllWindows()
