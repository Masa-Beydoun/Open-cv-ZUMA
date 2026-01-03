import cv2
import numpy as np
import time
import os
import mss
from ignored_zone_manager import IgnoredZonesManager
from extract_color_methods import ExtractColorMethod

try:
    from roi.detect_roi import analyze_game_screen
except ImportError:
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from roi.detect_roi import analyze_game_screen


class ZumaBot:
    def __init__(self):      
        self.known_colors = {}
        
        self.extract_color_method = ExtractColorMethod.MEAN
        
        self.asset_map = {
            "ball_0.png": "Purple",
            "ball_1.png": "Blue",
            "ball_2.png": "Yellow",
            "ball_3.png": "Green",
            "ball_4.png": "Red"
        }

        # deluxe3
        self.CONFIGS = {
            # الإعدادات الخاصة بالشاشات الكبيرة (أكبر من 1000 بكسل)
            "LARGE": {
                "REFERENCE_WIDTH": 1000, # العرض الذي عايرت عليه هذه القيم
                "params": {
                    "minDist": 13, 
                    "minRadius": 13, 
                    "maxRadius": 26,
                    "param1": 66, 
                    "param2": 42 # دقة عالية
                }
            },
            
            # الإعدادات الخاصة بالشاشات الصغيرة (أصغر من 1000 بكسل)
            "SMALL": {
                "REFERENCE_WIDTH": 730, # العرض الذي عايرت عليه هذه القيم
                "params": {
                    "minDist": 9, 
                    "minRadius": 5, 
                    "maxRadius": 20,
                    "param1": 42, # حساسية أقل للحواف الحادة
                    "param2": 28  # تساهل أكثر لأن البكسلات قليلة
                }
            }
        }
        
        # space
        # self.CONFIGS = {
        #     # الإعدادات الخاصة بالشاشات الكبيرة (أكبر من 1000 بكسل)
        #     "LARGE": {
        #         "REFERENCE_WIDTH": 1000, # العرض الذي عايرت عليه هذه القيم
        #         "params": {
        #             "minDist": 7, 
        #             "minRadius": 10, 
        #             "maxRadius": 27,
        #             "param1": 71, 
        #             "param2": 33 # دقة عالية
        #         }
        #     },
            
        #     # الإعدادات الخاصة بالشاشات الصغيرة (أصغر من 1000 بكسل)
        #     "SMALL": {
        #         "REFERENCE_WIDTH": 730, # العرض الذي عايرت عليه هذه القيم
        #         "params": {
        #             "minDist": 9, 
        #             "minRadius": 7, 
        #             "maxRadius": 22,
        #             "param1": 57, # حساسية أقل للحواف الحادة
        #             "param2": 26  # تساهل أكثر لأن البكسلات قليلة
        #         }
        #     }
        # }
        
        # xmas
        # self.CONFIGS = {
        #     # الإعدادات الخاصة بالشاشات الكبيرة (أكبر من 1000 بكسل)
        #     "LARGE": {
        #         "REFERENCE_WIDTH": 1000, # العرض الذي عايرت عليه هذه القيم
        #         "params": {
        #             "minDist": 10, 
        #             "minRadius": 12, 
        #             "maxRadius": 29,
        #             "param1": 71, 
        #             "param2": 25 # دقة عالية
        #         }
        #     },
            
        #     # الإعدادات الخاصة بالشاشات الصغيرة (أصغر من 1000 بكسل)
        #     "SMALL": {
        #         "REFERENCE_WIDTH": 730, # العرض الذي عايرت عليه هذه القيم
        #         "params": {
        #             "minDist": 9, 
        #             "minRadius": 7, 
        #             "maxRadius": 22,
        #             "param1": 57, # حساسية أقل للحواف الحادة
        #             "param2": 26  # تساهل أكثر لأن البكسلات قليلة
        #         }
        #     }
        # }
        
        
    def load_assets(self, asset_folder="space"):

        OPT_SAT = 30
        OPT_CROP_Y = 0.20
        OPT_CROP_X = 0.20
        
        for filename, color_name in self.asset_map.items():
            path = os.path.join(asset_folder, filename)
            image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if image is None: continue
            
            h, w = image.shape[:2]
            y_start = int(h * OPT_CROP_Y)
            x_end = int(w * (1 - OPT_CROP_X))
            image = image[y_start:h, 0:x_end]
            
            if image.shape[2] == 4:
                bgr = image[:, :, :3]
                alpha = image[:, :, 3]
                hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
                mask = (alpha > 0) & (hsv[:, :, 1] > OPT_SAT)
            else:
                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                mask = hsv[:, :, 1] > OPT_SAT

            if np.count_nonzero(mask) > 0:
                # ---------------------------------------------------------
                # >>> هنا يتم الفحص الأول <<<
                # ---------------------------------------------------------
                if self.extract_color_method == ExtractColorMethod.DOMINANT:
                    # الطريقة الجديدة: اللون الطاغي
                    hue, sat = self.get_dominant_color_features(hsv, mask)
                    self.known_colors[color_name] = (hue, sat)
                else:
                    # الطريقة القديمة: المتوسط الحسابي
                    mean_color = cv2.mean(hsv, mask=mask.astype(np.uint8))
                    self.known_colors[color_name] = (mean_color[0], mean_color[1])


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
            cv2.circle(mask, (w//2, h//2), int(w/2), 255, -1)
            
            hue, _ = self.get_dominant_color_features(hsv_roi, mask)
        else:
            # الطريقة القديمة
            mean_hsv = cv2.mean(hsv_roi)
            hue = mean_hsv[0]
        
        # مقارنة اللون المكتشف مع الألوان المحفوظة
        best_match = None
        min_diff = 999
        
        for color_name, (known_hue, known_sat) in self.known_colors.items():
            diff = abs(hue - known_hue)
            if diff > 90: diff = 180 - diff
            if diff < min_diff:
                min_diff = diff
                best_match = color_name
                
        if min_diff > 20: return None 
        return best_match
    
    def get_adaptive_params(self, current_width):
        """
        تقوم هذه الدالة باختيار البروفايل المناسب وحساب القياسات
        """
        # 1. تحديد أي بروفايل سنستخدم
        if current_width >= 1000:
            config = self.CONFIGS["LARGE"]
            # print("Using LARGE Profile") # للتجربة
        else:
            config = self.CONFIGS["SMALL"]
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
            "param2": base_params["param2"]
        }
        
        # حماية من القيم الصفرية
        final_params["minRadius"] = max(3, final_params["minRadius"])
        final_params["maxRadius"] = max(final_params["minRadius"] + 2, final_params["maxRadius"])
        
        return final_params
    
    def detect_from_frame(self, frame, ignored_zones=[], path_mask=None):
            output = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 1. تطبيق المناطق المتجاهلة (رسم مربعات سوداء على الصورة الرمادية)
            # هذا يمنع HoughCircles من رؤية أي شيء هنا
            if ignored_zones:
                for (x, y, w, h) in ignored_zones:
                    cv2.rectangle(gray, (x, y), (x+w, y+h), 0, -1)
            
            # 2. (مستقبلاً) تطبيق قناع المسار
            # إذا تم تمرير قناع، نطبق bitwise_and لإخفاء كل شيء خارج المسار
            if path_mask is not None:
                # تأكد أن القناع بنفس حجم الصورة
                # gray = cv2.bitwise_and(gray, gray, mask=path_mask)
                pass 

            # 3. حساب القياس النسبي
            current_w = frame.shape[1]
            params = self.get_adaptive_params(current_w)

            gray = cv2.medianBlur(gray, 5)
            
            circles = cv2.HoughCircles(
                gray, cv2.HOUGH_GRADIENT, dp=1, 
                minDist=params["minDist"],
                param1=params["param1"], 
                param2=params["param2"], 
                minRadius=params["minRadius"], 
                maxRadius=params["maxRadius"]
            )

            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                for (x, y, r) in circles:
                    if y-r < 0 or x-r < 0 or y+r > frame.shape[0] or x+r > frame.shape[1]:
                        continue

                    roi_r = int(r * 0.7)
                    y1, y2 = max(0, y-roi_r), min(frame.shape[0], y+roi_r)
                    x1, x2 = max(0, x-roi_r), min(frame.shape[1], x+roi_r)
                    roi = frame[y1:y2, x1:x2]
                    
                    if roi.size == 0: continue

                    color_name = self.identify_color(roi)
                    
                    if color_name:
                        
                        # رسم الدائرة بلون الكرة
                        cv2.circle(output, (x, y), r, (0,0,0), 2)
                        
                        # رسم مركز صغير
                        cv2.circle(output, (x, y), 2, (255, 255, 255), -1)
                        
                        # النص اختياري الآن، لكن يمكن تركه صغيراً
                        cv2.putText(output, color_name, (x - 10, y - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 1)
            
            return output
        
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    assets_path = os.path.join(project_root, "deluxe3")
    
    # 1. إعداد المناطق المتجاهلة
    zone_manager = IgnoredZonesManager("ignored_zones.json")
    ignored_zones = zone_manager.load_zones()
    
    # 2. إعداد البوت
    bot = ZumaBot()
    print("Loading assets...")
    bot.load_assets(assets_path)

    # إعداد النافذة
    window_name = "Zuma Bot - Live Monitor"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 600, 450)

    with mss.mss() as sct:
        monitor_number = 1 
        full_monitor = sct.monitors[monitor_number]
        
        # إذا لم تكن هناك مناطق، نعرض خيار الرسم في البداية
        if not ignored_zones:
            print("No ignored zones found. Capturing screen for setup...")
            screenshot = np.array(sct.grab(full_monitor))
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
            # محاولة إيجاد منطقة اللعبة لتسهيل الرسم
            region_setup = analyze_game_screen(screenshot)
            if region_setup:
                # نقص صورة اللعبة فقط للرسم عليها
                x, y, w, h = region_setup.x, region_setup.y, region_setup.w, region_setup.h
                game_img = screenshot[y:y+h, x:x+w]
                # استدعاء دالة الرسم
                ignored_zones = zone_manager.select_zones(game_img)
            else:
                print("Could not find game for setup zone selection.")

        # متغيرات الحلقة الرئيسية
        capture_area = None
        last_recheck_time = 0
        RECHECK_INTERVAL = 1.5
        
        # متغيرات قياس الأداء
        fps = 0
        frame_count = 0
        start_time = time.time()
        
        print("Starting Main Loop...")
        
        while True:
            loop_start = time.time()
            
            # --- Check Periodically ---
            if loop_start - last_recheck_time > RECHECK_INTERVAL:
                full_screenshot = np.array(sct.grab(full_monitor))
                full_screenshot_bgr = cv2.cvtColor(full_screenshot, cv2.COLOR_BGRA2BGR)
                new_region_data = analyze_game_screen(full_screenshot_bgr)
                
                if new_region_data:
                    capture_area = new_region_data.to_mss_dict(full_monitor["left"], full_monitor["top"])
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
                    result = bot.detect_from_frame(frame, ignored_zones=ignored_zones, path_mask=None)
                    
                    # حساب الـ FPS
                    frame_count += 1
                    elapsed = time.time() - start_time
                    if elapsed > 1.0: # تحديث كل ثانية
                        fps = frame_count / elapsed
                        frame_count = 0
                        start_time = time.time()
                    
                    # عرض الـ FPS على الشاشة
                    cv2.putText(result, f"FPS: {int(fps)}", (10, 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

                    cv2.imshow(window_name, result)
                    
                except Exception as e:
                    print(f"Error: {e}")
            else:
                blank_screen = np.zeros((300, 500, 3), dtype=np.uint8)
                cv2.putText(blank_screen, "Searching...", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                cv2.imshow(window_name, blank_screen)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cv2.destroyAllWindows()