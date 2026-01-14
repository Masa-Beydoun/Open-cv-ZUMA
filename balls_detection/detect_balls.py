import cv2
import numpy as np
import time
import os
import mss

try:
    from roi.detect_roi import analyze_game_screen
    from balls_detection.ignored_zone_manager import IgnoredZonesManager
    from balls_detection.extract_color_methods import ExtractColorMethod
    from path_detection.capture_game_path import capture_game_path
    from path_detection.get_ball_position import get_ball_progress
    from path_detection.path_detection import (
        ZUMA_GREEN_JUNGLE_CONFIG,
        ZUMA_SPACE_CONFIG,
        ZUMA_DELUXE_CONFIG,
    )
    from constants import *

except ImportError:
    import sys, os

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from roi.detect_roi import analyze_game_screen
    from balls_detection.ignored_zone_manager import IgnoredZonesManager
    from balls_detection.extract_color_methods import ExtractColorMethod
    from path_detection.capture_game_path import capture_game_path
    from path_detection.get_ball_position import get_ball_progress
    from path_detection.path_detection import (
        ZUMA_GREEN_JUNGLE_CONFIG,
        ZUMA_SPACE_CONFIG,
        ZUMA_DELUXE_CONFIG,
    )
    from constants import *


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

    def calculate_ball_progress(self, ball_center, path_points_np):
        """
        تحسب موقع الكرة على المسار.
        path_points_np: مصفوفة numpy تحتوي على نقاط المسار [(x,y), ...]
        """
        if path_points_np is None or len(path_points_np) == 0:
            return -1

        # حساب المسافة بين مركز الكرة وجميع نقاط المسار دفعة واحدة
        # ball_center shape: (1, 2) | path_points_np shape: (N, 2)
        dist = np.linalg.norm(path_points_np - np.array(ball_center), axis=1)

        # إيجاد أقرب نقطة (index)
        closest_idx = np.argmin(dist)
        min_dist = dist[closest_idx]

        # إذا كانت الكرة بعيدة جداً عن خط المسار (مثلاً كرة طائرة في الهواء)، نعيد -1
        if min_dist > 40:  # هذا الرقم يعتمد على دقة المسار وحجم الكرة
            return -1

        return closest_idx

    def detect_from_frame(
        self, frame, ignored_zones=[], path_mask=None, path_points=None
    ):
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

        total_path_length = 0
        if path_points is not None:
            total_path_length = len(path_points)

        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for x, y, r in circles:
                # أ- فحوصات الحدود للصورة
                if (
                    y - r < 0
                    or x - r < 0
                    or y + r > frame.shape[0]
                    or x + r > frame.shape[1]
                ):
                    continue

                # ب- فحوصات القناع (هل الكرة فوق المسار؟)
                if path_mask is not None:
                    # يجب أن تكون إحداثيات المركز داخل حدود القناع
                    if 0 <= y < path_mask.shape[0] and 0 <= x < path_mask.shape[1]:
                        # إذا كانت النقطة سوداء (0)، فهي خارج المسار
                        if path_mask[y, x] == 0:
                            continue
                    else:
                        continue

                # ج- استخراج اللون
                roi = frame[
                    max(0, y - r) : min(frame.shape[0], y + r),
                    max(0, x - r) : min(frame.shape[1], x + r),
                ]
                if roi.size == 0:
                    continue

                color_name = self.identify_color(roi)

                if color_name:
                    dist_to_hole = 99999  # قيمة افتراضية عالية للكرات البعيدة عن المسار

                    # د- حساب المسافة (الرابط مع المسار)
                    if path_points is not None:
                        # بما أن المسار يبدأ من الحفرة (Index 0)، فالإندكس هو المسافة المتبقية
                        idx = get_ball_progress((x, y), path_points)

                        if idx != -1:
                            dist_to_hole = idx
                        else:
                            # الكرة بعيدة عن الخط الأخضر -> نتجاهلها
                            continue

                    # هـ- بناء كائن الكرة النهائي
                    ball_info = {
                        "color": color_name,  # لون الكرة (RED, BLUE...)
                        "position": (int(x), int(y)),  # الموقع (x, y) بالنسبة للصورة
                        "radius": int(r),  # نصف القطر
                        "distance": int(dist_to_hole),
                    }
                    detected_balls.append(ball_info)

        # 4. الترتيب النهائي (الأهم)
        # نرتب تصاعدياً (reverse=False):
        # المسافة 0 (الحفرة) -> تأتي أولاً في القائمة
        # المسافة 1000 (البداية) -> تأتي أخيراً
        detected_balls.sort(key=lambda b: b["distance"], reverse=False)

        # 5. الرسم (Visualization)
        for rank, ball in enumerate(detected_balls):
            x, y = ball["position"]
            r = ball["radius"]
            dist = ball["distance"]

            cv2.circle(output, (x, y), r, (255, 255, 255), 2)

            # كتابة الترتيب (#1 هو الأخطر)
            rank_text = f"#{rank + 1}"
            cv2.putText(
                output,
                rank_text,
                (x - 10, y + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                4,
            )
            cv2.putText(
                output,
                rank_text,
                (x - 10, y + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )

            # كتابة المسافة
            cv2.putText(
                output,
                f"{dist}",
                (x - 10, y + r + 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (200, 200, 255),
                1,
            )

        # نعيد الصورة + القائمة المرتبة
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
    # تأكد من اختيار الإعدادات المناسبة للمرحلة التي تلعبها
    SELECTED_CONFIG = Deluxe3
    PATH_CONFIG = ZUMA_DELUXE_CONFIG  # أو ZUMA_SPACE_CONFIG حسب الصورة

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

        # متغيرات لتخزين المسار "المحلي" (الثابت بالنسبة للعبة)
        local_path_points = None
        cached_path_mask = None
        # إعداد النافذة
        window_name = "Zuma Bot - Live Monitor"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 600, 450)

        with mss.mss() as sct:
            full_monitor = sct.monitors[MONITOR]
            global_path_points, raw_mask = capture_game_path(PATH_CONFIG)

            # --- ب. تحويل المسار إلى "محلي" فوراً ---
            if global_path_points is not None:
                # نحتاج لمعرفة أين كانت اللعبة لحظة التقاط المسار لنقوم بالطرح
                # سنأخذ لقطة سريعة لمعرفة مكان اللعبة الآن
                temp_screen = np.array(sct.grab(full_monitor))
                temp_frame = cv2.cvtColor(temp_screen, cv2.COLOR_BGRA2BGR)
                region = analyze_game_screen(temp_frame)

                if region:
                    capture_x, capture_y = region.x, region.y

                    # التحويل: النقطة المحلية = النقطة العالمية - بداية النافذة
                    local_path_points = [
                        (gx - capture_x, gy - capture_y)
                        for gx, gy in global_path_points
                    ]
                    cached_path_mask = raw_mask  # الماسك دائماً محلي (صورة مقصوصة)
                    print("Path converted to Local Coordinates successfully.")
                else:
                    print("Error: Could not find game window to randomize local path.")
            else:
                print("Warning: Path not detected! Bot will work without path logic.")

            # متغيرات الحلقة الرئيسية
            capture_area = None
            last_recheck_time = 0
            RECHECK_INTERVAL = 3

            # متغيرات قياس الأداء
            fps = 0
            frame_count = 0
            start_time = time.time()

            game_x, game_y = 0, 0

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
                        game_x = new_region_data.x
                        game_y = new_region_data.y

                        capture_area = new_region_data.to_mss_dict(
                            full_monitor["left"], full_monitor["top"]
                        )

                        # تحديث المسار المحلي (Local Path) إذا كان لدينا مسار عالمي (Global)
                        if global_path_points:
                            # تحويل Global -> Local: (Gx - GameX, Gy - GameY)
                            local_points = [
                                (gx - game_x, gy - game_y)
                                for gx, gy in global_path_points
                            ]
                            cached_path_points = local_points

                            # Mask هو صورة، حجمه ثابت بحجم اللعبة، لا يحتاج إزاحة، فقط تأكد من الحجم
                            cached_path_mask = (
                                raw_mask  # نفترض أن حجمه يطابق حجم اللعبة المكتشفة
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
                            frame,
                            ignored_zones=ignored_zones,
                            # path_mask=cached_path_mask,  # تمرير القناع
                            path_points=cached_path_points,  # تمرير النقاط
                        )

                        if cached_path_points:
                            # رسم خط بسيط يمثل المسار
                            pts = np.array(cached_path_points, np.int32)
                            pts = pts.reshape((-1, 1, 2))
                            cv2.polylines(result, [pts], False, (0, 255, 0), 1)

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

        print(balls)
