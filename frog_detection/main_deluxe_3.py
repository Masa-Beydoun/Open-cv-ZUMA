import cv2
import numpy as np
import time
import os
import mss

try:
    from constants import *
    from roi.detect_roi import analyze_game_screen
except ImportError:
    import sys, os

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from roi.detect_roi import analyze_game_screen
    from constants import *
    from frog_detection.ZumaFrogDetector import ZumaFrogDetector

if __name__ == "__main__":

    IS_REALTIME = True

    window_name = "Zuma Frog Detector - Live"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 600, 450)

    with mss.mss() as sct:
        full_monitor = sct.monitors[MONITOR]

        capture_area = None
        last_recheck_time = 0
        RECHECK_INTERVAL = 2

        fps = 0
        frame_count = 0
        start_time = time.time()

        frog_detector = None

        print("Starting Main Loop...")

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

                    
                    if frog_detector is None:
                        h, w = frame.shape[:2]
                        frog_detector = ZumaFrogDetector(w, h)

                    
                    frog_box = frog_detector.detect(frame)

                    
                    if frog_box:
                        x, y, fw, fh = frog_box
                        cv2.rectangle(
                            frame,
                            (x, y),
                            (x + fw, y + fh),
                            (255, 0, 0),
                            2
                        )
                        cv2.putText(
                            frame,
                            "FROG",
                            (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (255, 0, 0),
                            2
                        )

                    
                    frame_count += 1
                    elapsed = time.time() - start_time
                    if elapsed > 1.0:
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
                    print(f"Error: {e}")

            else:
                blank = np.zeros((300, 500, 3), dtype=np.uint8)
                cv2.putText(
                    blank,
                    "Searching...",
                    (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 255),
                    2
                )
                cv2.imshow(window_name, blank)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cv2.destroyAllWindows()
