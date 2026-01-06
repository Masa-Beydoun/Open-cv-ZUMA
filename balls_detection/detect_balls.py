import cv2
import numpy as np
import time
import os
import mss
from ignored_zone_manager import IgnoredZonesManager
from extract_color_methods import ExtractColorMethod

try:
    from constants import *
    from roi.detect_roi import analyze_game_screen
except ImportError:
    import sys, os

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from roi.detect_roi import analyze_game_screen
    from constants import *

    from frog_detection.ZumaFrogDetector import ZumaFrogDetector


class ZumaBot:

    def __init__(self, game_config):
        self.hue_sat = game_config["hue_sat"]
        self.extract_color_method = game_config["extract_color_method"]
        self.hc_config = game_config["hc_config"]

    # def load_assets(self, asset_folder):

    #     OPT_SAT = 30
    #     OPT_CROP_Y = 0.20
    #     OPT_CROP_X = 0.20

    #     for filename, color_name in self.asset_map.items():
    #         path = os.path.join(asset_folder, filename)
    #         image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    #         if image is None:
    #             continue

    #         h, w = image.shape[:2]
    #         y_start = int(h * OPT_CROP_Y)
    #         x_end = int(w * (1 - OPT_CROP_X))
    #         image = image[y_start:h, 0:x_end]

    #         if image.shape[2] == 4:
    #             bgr = image[:, :, :3]
    #             alpha = image[:, :, 3]
    #             hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    #             mask = (alpha > 0) & (hsv[:, :, 1] > OPT_SAT)
    #         else:
    #             hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    #             mask = hsv[:, :, 1] > OPT_SAT

    #         if np.count_nonzero(mask) > 0:
    #             # ---------------------------------------------------------
    #             # >>> هنا يتم الفحص الأول <<<
    #             # ---------------------------------------------------------
    #             if self.extract_color_method == ExtractColorMethod.DOMINANT:
    #                 # الطريقة الجديدة: اللون الطاغي
    #                 hue, sat = self.get_dominant_color_features(hsv, mask)
    #                 self.hue_sat[color_name] = (hue, sat)
    #             else:
    #                 # الطريقة القديمة: المتوسط الحسابي
    #                 mean_color = cv2.mean(hsv, mask=mask.astype(np.uint8))
    #                 self.hue_sat[color_name] = (mean_color[0], mean_color[1])

    def get_dominant_color_features(self, hsv_img, mask=None):
        """
        تعيد (Hue, Saturation) للون الطاغي في الصورة
        """
        # إذا لم يتم تمرير قناع، نعتبر الصورة كاملة هي القناع
        if mask is None:
            mask = np.ones(hsv_img.shape[:2], dtype=np.uint8) * 255

        if np.count_nonzero(mask) == 0:
            return 0, 0

        # 1. حساب الهيستوجرام لقناة Hue فقط
        hist = cv2.calcHist([hsv_img], [0], mask.astype(np.uint8), [180], [0, 180])

        # 2. الدرجة الأكثر تكراراً (Dominant Hue)
        dominant_hue = int(np.argmax(hist))

        # 3. حساب متوسط التشبع (Saturation) لنفس هذا اللون فقط
        hue_mask = (hsv_img[..., 0] == dominant_hue) & (mask > 0)

        if np.count_nonzero(hue_mask) == 0:
            # حالة احتياطية نادرة
            return dominant_hue, 0

        mean_sat = cv2.mean(hsv_img[..., 1], mask=hue_mask.astype(np.uint8))[0]

        return dominant_hue, mean_sat

    def identify_color(self, roi):
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # ---------------------------------------------------------
        # >>> هنا يتم الفحص الثاني <<<
        # ---------------------------------------------------------
        if self.extract_color_method == ExtractColorMethod.DOMINANT:
            # في حالة الطاغي، نفضل إنشاء قناع دائري بسيط لإهمال زوايا المربع
            h, w = roi.shape[:2]
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(mask, (w // 2, h // 2), int(w / 2), 255, -1)

            hue, _ = self.get_dominant_color_features(hsv_roi, mask)
        else:
            # الطريقة القديمة
            mean_hsv = cv2.mean(hsv_roi)
            hue = mean_hsv[0]

        # مقارنة اللون المكتشف مع الألوان المحفوظة
        best_match = None
        min_diff = 999

        for color_name, (known_hue, known_sat) in self.hue_sat.items():
            diff = abs(hue - known_hue)
            if diff > 90:
                diff = 180 - diff
            if diff < min_diff:
                min_diff = diff
                best_match = color_name

        if min_diff > 20:
            return None
        return best_match

    def get_adaptive_params(self, current_width):
        """
        تقوم هذه الدالة باختيار البروفايل المناسب وحساب القياسات
        """
        # 1. تحديد أي بروفايل سنستخدم
        if current_width >= 1000:
            config = self.hc_config["LARGE"]
            # print("Using LARGE Profile") # للتجربة
        else:
            config = self.hc_config["SMALL"]
            # print("Using SMALL Profile") # للتجربة

        ref_width = config["REFERENCE_WIDTH"]
        base_params = config["params"]

        # 2. حساب معامل التكبير النسبي داخل هذا البروفايل
        scale_factor = current_width / ref_width

        # 3. حساب القيم النهائية
        final_params = {
            "minDist": int(base_params["minDist"] * scale_factor),
            "minRadius": int(base_params["minRadius"] * scale_factor),
            "maxRadius": int(base_params["maxRadius"] * scale_factor),
            "param1": base_params["param1"],
            "param2": base_params["param2"],
        }

        # حماية من القيم الصفرية
        final_params["minRadius"] = max(3, final_params["minRadius"])
        final_params["maxRadius"] = max(
            final_params["minRadius"] + 2, final_params["maxRadius"]
        )

        return final_params

    def detect_from_frame(self, frame, ignored_zones=[], path_mask=None):
        output = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Initialize the list to store results
        detected_balls = []

        if ignored_zones:
            for x, y, w, h in ignored_zones:
                cv2.rectangle(gray, (x, y), (x + w, y + h), 0, -1)

        current_w = frame.shape[1]
        params = self.get_adaptive_params(current_w)

        gray = cv2.medianBlur(gray, 5)

        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=params["minDist"],
            param1=params["param1"],
            param2=params["param2"],
            minRadius=params["minRadius"],
            maxRadius=params["maxRadius"],
        )

        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for x, y, r in circles:
                if (
                    y - r < 0
                    or x - r < 0
                    or y + r > frame.shape[0]
                    or x + r > frame.shape[1]
                ):
                    continue

                roi_r = int(r * 0.7)
                y1, y2 = max(0, y - roi_r), min(frame.shape[0], y + roi_r)
                x1, x2 = max(0, x - roi_r), min(frame.shape[1], x + roi_r)
                roi = frame[y1:y2, x1:x2]

                if roi.size == 0:
                    continue

                color_name = self.identify_color(roi)

                if color_name:
                    # --- ADD TO LIST ---
                    ball_data = {
                        "color": color_name,
                        "x": int(x),
                        "y": int(y),
                        "radius": int(r),  # Optional, but often useful
                    }
                    detected_balls.append(ball_data)

                    # --- VISUALIZATION (Keep existing drawing code) ---
                    cv2.circle(output, (x, y), r, (0, 0, 0), 2)
                    cv2.circle(output, (x, y), 3, (0, 0, 255), -1)
                    cv2.putText(
                        output,
                        color_name,
                        (x - 10, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.3,
                        (0, 0, 0),
                        1,
                    )

        # Return BOTH the image and the data list
        return output, detected_balls


def sort_balls_by_path(balls, path_points):
    """
    Sorts the detected balls based on their progress along the path.

    Args:
        balls: List of dicts [{'x': 100, 'y': 200, 'color': 'RED'}, ...]
        path_points: List of (x, y) tuples representing the path from START to SKULL.
                     Example: [(0,0), (1,0), ... (500, 500)]

    Returns:
        List of balls sorted by who is closest to the end of the path.
    """
    if not balls or not path_points:
        return balls

    # Convert path to numpy array for fast calculation (if it isn't already)
    path_arr = np.array(path_points)

    for ball in balls:
        ball_pos = np.array([ball["x"], ball["y"]])

        # 1. Calculate distance from this ball to EVERY point on the path
        # (Using Euclidean distance: sqrt((x2-x1)^2 + (y2-y1)^2))
        distances = np.linalg.norm(path_arr - ball_pos, axis=1)

        # 2. Find the index of the minimum distance
        # This index represents "how far along" the track the ball is.
        # Index 0 = Start, Index MAX = The Skull
        closest_path_index = np.argmin(distances)

        # Store this index in the ball's data so we can use it later if needed
        ball["path_index"] = closest_path_index

    # 3. Sort the list based on 'path_index'
    # reverse=True means Descending Order (Highest Index first)
    # This puts the ball closest to the Skull at the top of the list.
    sorted_balls = sorted(balls, key=lambda b: b["path_index"], reverse=True)

    return sorted_balls


def run_single_image_debug(image_path, game_config):
    """
    تقوم بتحميل صورة واحدة، وتطبيق الكشف عليها، وعرض النتيجة.
    """
    print(f"\n--- Starting Debug on: {image_path} ---")

    # 1. تحميل الصورة
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Error: Could not load image from '{image_path}'")
        return

    # 2. إعداد البوت مع الكونفيج المطلوب
    print("Initializing bot with selected configuration...")
    bot = ZumaBot(game_config)

    # 3. تشغيل الكشف
    print("Running detection...")
    # يمكنك تمرير مناطق التجاهل هنا إذا أردت اختبارها أيضاً
    # ignored_zones = [(x,y,w,h), ...]
    result_frame, balls = bot.detect_from_frame(frame, ignored_zones=[])
    print(balls)
    # 4. عرض النتائج
    window_name = "Debug Result (Press any key to close)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.imshow(window_name, result_frame)

    print("Result displayed. Press any key in the window to finish.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    print("--- Debug Finished ---\n")


if __name__ == "__main__":

    IS_REALTIME = True
    SELECTED_CONFIG = Deluxe3

    if not IS_REALTIME:

        SCREENSHOT_PATH = "balls_detection/testing_samples/delux_1.png"

        run_single_image_debug(SCREENSHOT_PATH, SELECTED_CONFIG)

    else:
        # 1. إعداد المناطق المتجاهلة
        zone_manager = IgnoredZonesManager("ignored_zones.json")
        # ignored_zones = zone_manager.load_zones()
        ignored_zones = None

        # 2. إعداد البوت
        bot = ZumaBot(SELECTED_CONFIG)

        # إعداد النافذة
        window_name = "Zuma Bot - Live Monitor"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 600, 450)

        with mss.mss() as sct:
            full_monitor = sct.monitors[MONITOR]

            # إذا لم تكن هناك مناطق، نعرض خيار الرسم في البداية
            if not ignored_zones:
                print("No ignored zones found. Capturing screen for setup...")
                screenshot = np.array(sct.grab(full_monitor))
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

                # محاولة إيجاد منطقة اللعبة لتسهيل الرسم
                region_setup = analyze_game_screen(screenshot)
                if region_setup:
                    # نقص صورة اللعبة فقط للرسم عليها
                    x, y, w, h = (
                        region_setup.x,
                        region_setup.y,
                        region_setup.w,
                        region_setup.h,
                    )
                    game_img = screenshot[y : y + h, x : x + w]
                    # استدعاء دالة الرسم
                    # ignored_zones = zone_manager.select_zones(game_img)
                else:
                    print("Could not find game for setup zone selection.")

            # متغيرات الحلقة الرئيسية
            capture_area = None
            last_recheck_time = 0
            RECHECK_INTERVAL = 20

            # متغيرات قياس الأداء
            fps = 0
            frame_count = 0
            start_time = time.time()

            print("Starting Main Loop...")

            balls = []

            while True:
                loop_start = time.time()

                # --- Check Periodically ---
                if loop_start - last_recheck_time > RECHECK_INTERVAL:
                    full_screenshot = np.array(sct.grab(full_monitor))
                    full_screenshot_bgr = cv2.cvtColor(
                        full_screenshot, cv2.COLOR_BGRA2BGR
                    )
                    new_region_data = analyze_game_screen(full_screenshot_bgr)

                    if new_region_data:
                        capture_area = new_region_data.to_mss_dict(
                            full_monitor["left"], full_monitor["top"]
                        )
                    last_recheck_time = loop_start

                # --- Tracking ---
                if capture_area:
                    try:
                        sct_img = sct.grab(capture_area)
                        frame = np.array(sct_img)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                        # ---------------------------------------------------------
                        # استدعاء التتبع مع تمرير المناطق المتجاهلة
                        # (يمكنك تمرير path_mask مستقبلاً هنا)
                        # ---------------------------------------------------------
                        result, balls = bot.detect_from_frame(
                            frame, ignored_zones=ignored_zones, path_mask=None
                        )

                        # حساب الـ FPS
                        frame_count += 1
                        elapsed = time.time() - start_time
                        if elapsed > 1.0:  # تحديث كل ثانية
                            fps = frame_count / elapsed
                            frame_count = 0
                            start_time = time.time()

                        # عرض الـ FPS على الشاشة
                        cv2.putText(
                            result,
                            f"FPS: {int(fps)}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (255, 255, 255),
                            2,
                        )

                        cv2.imshow(window_name, result)

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
