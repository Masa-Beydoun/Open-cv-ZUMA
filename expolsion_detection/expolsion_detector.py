import glob
import time
import cv2
import mss
import numpy as np

try:
    from balls_detection.detect_balls import ZumaBot
    from constants import *
    from roi.detect_roi import analyze_game_screen
except ImportError:
    import sys, os

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from balls_detection.detect_balls import ZumaBot
    from constants import *
    from roi.detect_roi import analyze_game_screen


class ExplosionDetector:
    def __init__(self, game_version=GAME_VERSION):
        """
        explosion_assets_paths: قائمة بمسارات الصور (فريم البداية، الوسط، النهاية)
        كما طلب زميلك في Constants.
        """
        self.templates = []

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), game_version)
        if not os.path.exists(path):
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                game_version,
            )

        if not os.path.exists(path):
            print(f"Error: Folder '{game_version}' not found.")
            return [], []

        files = sorted(glob.glob(os.path.join(path, "explosion*.png")))

        if not files:
            print(f"No ball images found in {path}")
            return [], []

        for f in files:
            # 1. Load with Alpha (4 Channels)
            img = cv2.imread(f, cv2.IMREAD_UNCHANGED)

            if img is not None:
                # Check if image actually has transparency (4 channels)
                if img.shape[2] == 4:
                    # Split into Color (BGR) and Mask (Alpha)
                    base_img = img[:, :, 0:3]  # The BGR colors
                    alpha_mask = img[:, :, 3]  # The Transparency map
                    self.templates.append((base_img, alpha_mask))
                else:
                    # Fallback for images without transparency
                    self.templates.append((img, None))

                print(f"Loaded: {os.path.basename(f)}")

        # حدود HSV للانفجار (من شغلك القديم)
        self.lower_explosion = np.array([15, 80, 120])
        self.upper_explosion = np.array([40, 255, 255])

    def detect(self, frame):
        """
        تأخذ فريم وتعيد الفريم مرسوماً عليه + قائمة بمناطق الانفجارات
        """
        output_frame = frame.copy()
        detected_explosions = []

        # --- الطريقة الأولى: البحث عن الألوان والأشكال (شغلك القديم) ---
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_explosion, self.upper_explosion)
        kernel = np.ones((7, 7), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 1000:
                continue  # تجاهل الشرارات الصغيرة جداً

            peri = cv2.arcLength(cnt, True)
            circularity = 4 * np.pi * area / (peri * peri) if peri > 0 else 0

            # الانفجار غالباً غير منتظم (شغلك القديم)
            # في نسخة البيتش قد يكون دائرياً لذا سنعتمد على الحجم واللون
            if circularity < 0.6 or area > 3000:
                x, y, w, h = cv2.boundingRect(cnt)
                detected_explosions.append((x, y, w, h))

        # --- الطريقة الثانية: المقارنة بالنماذج (Template Matching) إذا وجدت ---
        for temp_img, temp_mask in self.templates:

            # Use CCORR_NORMED which supports masking
            if temp_mask is not None:
                res = cv2.matchTemplate(
                    frame, temp_img, cv2.TM_CCORR_NORMED, mask=temp_mask
                )
            else:
                res = cv2.matchTemplate(frame, temp_img, cv2.TM_CCORR_NORMED)

            # Note: CCORR_NORMED usually needs a slightly higher threshold (0.8 - 0.9)
            threshold = 0.85
            loc = np.where(res >= threshold)

            for pt in zip(*loc[::-1]):
                h, w = temp_img.shape[:2]
                detected_explosions.append((pt[0], pt[1], w, h))

        # دمج النتائج ورسمها لتجنب التكرار
        final_zones = []
        for x, y, w, h in detected_explosions:
            cv2.rectangle(output_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.putText(
                output_frame,
                "X",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1,
            )
            final_zones.append({"x": x, "y": y, "w": w, "h": h})

        return output_frame, final_zones


if __name__ == "__main__":
    SELECTED_CONFIG = Deluxe3  # مثال

    # 1. إعداد بوت الكرات (شغل زميلك)
    bot = ZumaBot(SELECTED_CONFIG)

    window_name = "Zuma Bot - Live Monitor"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 600, 450)

    # 2. إعداد كاشف الانفجارات (شغلك)
    # نمرر المسارات من Constants كما اقترح رفيقك
    explosion_paths = Deluxe3["explosion_assets"]
    print(explosion_paths)
    exp_detector = ExplosionDetector(GAME_VERSION)
    time.sleep(6)
    with mss.mss() as sct:
        full_monitor = sct.monitors[MONITOR]
        # متغيرات الحلقة الرئيسية
        capture_area = None
        last_recheck_time = 0
        RECHECK_INTERVAL = 4

        print("Starting Main Loop...")

        balls = []

        while True:

            loop_start = time.time()

            # --- Check Periodically ---
            if loop_start - last_recheck_time > RECHECK_INTERVAL:
                full_screenshot = np.array(sct.grab(full_monitor))
                full_screenshot_bgr = cv2.cvtColor(full_screenshot, cv2.COLOR_BGRA2BGR)
                new_region_data = analyze_game_screen(full_screenshot_bgr)

                if new_region_data:
                    capture_area = new_region_data.to_mss_dict(
                        full_monitor["left"], full_monitor["top"]
                    )
                last_recheck_time = loop_start

            if capture_area:
                try:

                    # التقاط الفريم
                    sct_img = sct.grab(capture_area)
                    frame = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)

                    # أولاً: كشف الانفجارات (شغلك)
                    # تعيد الفريم مرسوماً عليه وقائمة بالمناطق
                    frame_with_exp, explosion_zones = exp_detector.detect(frame)

                    # ثانياً: تحديث المناطق المتجاهلة (Ignored Zones)
                    # نحول إحداثيات انفجاراتك إلى تنسيق يفهمه بوت زميلك (x, y, w, h)
                    dynamic_ignored = []
                    for ez in explosion_zones:
                        dynamic_ignored.append((ez["x"], ez["y"], ez["w"], ez["h"]))

                    # # ثالثاً: كشف الكرات (شغل زميلك)
                    # # نمرر له الفريم ونضيف الانفجارات للمناطق المتجاهلة حتى لا يخطئ
                    # result, balls = bot.detect_from_frame(
                    #     frame_with_exp, ignored_zones=dynamic_ignored
                    # )

                    cv2.imshow(window_name, frame_with_exp)

                except Exception as e:
                    print(f"Error: {e}")

            else:
                blank_screen = np.zeros((300, 500, 3), dtype=np.uint8)
                cv2.putText(
                    blank_screen,
                    "Searching...",
                    (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 255),
                    2,
                )
                cv2.imshow(window_name, blank_screen)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cv2.destroyAllWindows()
