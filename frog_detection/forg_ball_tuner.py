import cv2
import numpy as np
import mss
import time

try:
    from roi.detect_roi import analyze_game_screen
    from frog_detection.ZumaFrogDetector import ZumaFrogDetector
    from constants import MONITOR
except ImportError:
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from roi.detect_roi import analyze_game_screen
    from frog_detection.ZumaFrogDetector import ZumaFrogDetector
    from constants import MONITOR

# ==========================================================
# إعدادات الألوان
# ==========================================================
COLORS_CONFIG = {
    "Purple": (143, 133),
    "Blue": (118, 134),
    "Yellow": (24, 125),
    "Green": (52, 139),
    "Red": (175, 134),
    # أضف باقي الألوان إذا لزم الأمر
}

def nothing(x):
    pass

def identify_color_hsv(hsv_img):
    """دالة لتحديد اللون بناء على Hue"""
    mean_hsv = cv2.mean(hsv_img)
    hue = mean_hsv[0]

    best_match = "Unknown"
    min_diff = 999

    for color_name, (known_hue, known_sat) in COLORS_CONFIG.items():
        diff = abs(hue - known_hue)
        if diff > 90:
            diff = 180 - diff
        if diff < min_diff:
            min_diff = diff
            best_match = color_name

    return best_match, int(hue)

def run_tuner():
    window_name = "Frog Ball Tuner (Ratio Calibrator)"
    cv2.namedWindow(window_name)

    # إنشاء أشرطة تحكم
    cv2.createTrackbar("Offset Y", window_name, 35, 150, nothing) # زدنا المدى قليلاً
    cv2.createTrackbar("Offset X", window_name, 0, 50, nothing)
    cv2.createTrackbar("Radius", window_name, 3, 20, nothing) # نصف القطر الافتراضي أصغر للدقة

    print("\n" + "="*50)
    print(">>> تعليمات المعايرة <<<")
    print("1. شغل اللعبة.")
    print("2. حرك الماوس للأعلى تماماً (ليظهر الضفدع الكرة).")
    print("3. حرك شريط Offset Y حتى تصبح الدائرة الحمراء فوق الكرة تماماً.")
    print("4. سجل قيمة 'Ratio' الظاهرة على الشاشة.")
    print("="*50 + "\n")

    with mss.mss() as sct:
        full_monitor = sct.monitors[MONITOR]

        while True:
            # 1. التقاط الشاشة كاملة
            screen = np.array(sct.grab(full_monitor))
            frame = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
            display_frame = frame.copy()

            # 2. تحديد منطقة اللعب (Game ROI)
            region = analyze_game_screen(frame)

            if region:
                # [Visual] رسم مربع أزرق حول منطقة اللعب للتأكد من صحة التتبع
                cv2.rectangle(display_frame, (region.x, region.y), 
                              (region.x + region.w, region.y + region.h), (255, 0, 0), 2)
                
                # 3. قص منطقة اللعبة للمعالجة
                game_frame = frame[region.y : region.y + region.h, region.x : region.x + region.w]

                # 4. اكتشاف الضفدع داخل منطقة اللعب
                h, w = game_frame.shape[:2]
                detector = ZumaFrogDetector(w, h)
                frog_box = detector.detect(game_frame)

                if frog_box:
                    fx, fy, fw, fh = frog_box
                    
                    # تحويل إحداثيات الضفدع إلى إحداثيات الشاشة (Global)
                    global_fx = region.x + fx
                    global_fy = region.y + fy
                    
                    # مركز الضفدع
                    center_x = global_fx + fw // 2
                    center_y = global_fy + fh // 2

                    # قراءة القيم من واجهة التحكم
                    offset_y_val = cv2.getTrackbarPos("Offset Y", window_name)
                    offset_x_val = cv2.getTrackbarPos("Offset X", window_name)
                    radius_val = cv2.getTrackbarPos("Radius", window_name)

                    # حساب نقطة الفحص (Sampling Point)
                    sample_x = center_x + offset_x_val
                    sample_y = center_y - offset_y_val 

                    # رسم الضفدع (مربع أخضر)
                    cv2.rectangle(display_frame, (global_fx, global_fy), 
                                  (global_fx + fw, global_fy + fh), (0, 255, 0), 2)

                    # التأكد أن نقطة الفحص داخل الحدود
                    if sample_y > radius_val and sample_x > radius_val:
                        # اقتطاع منطقة الفحص من الـ Frame الأصلي
                        roi = frame[
                            sample_y - radius_val : sample_y + radius_val,
                            sample_x - radius_val : sample_x + radius_val,
                        ]
                        
                        if roi.size > 0:
                            # تحليل اللون
                            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                            color_name, hue_val = identify_color_hsv(hsv_roi)
                            
                            # حساب النسبة المهمة (Ratio)
                            offset_ratio = offset_y_val / fh if fh > 0 else 0
                            radius_ratio = radius_val / fw if fw > 0 else 0

                            # === الرسم والعرض ===
                            # دائرة الفحص
                            cv2.circle(display_frame, (sample_x, sample_y), radius_val, (0, 0, 255), 2)
                            
                            # طباعة المعلومات بجانب الضفدع
                            info_text_lines = [
                                f"Color: {color_name} (H:{hue_val})",
                                f"Offset Y: {offset_y_val}px",
                                f"RATIO: {offset_ratio:.3f} (SAVE THIS)", # هذا هو الرقم المهم
                            ]
                            
                            for i, line in enumerate(info_text_lines):
                                y_pos = sample_y + 20 + (i * 25)
                                cv2.putText(display_frame, line, (sample_x + 15, y_pos),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                            # طباعة سطر واحد نظيف في التيرمينال
                            print(f"\r[Tuner] Color: {color_name:<8} | Hue: {hue_val:<3} | OffsetY: {offset_y_val:<3} | RATIO: {offset_ratio:.4f}", end="")

            else:
                cv2.putText(display_frame, "Searching for Game Window...", (50, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # عرض النافذة
            small_view = cv2.resize(display_frame, (0, 0), fx=0.5, fy=0.5)
            cv2.imshow(window_name, small_view)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cv2.destroyAllWindows()
    print("\nDone.")

if __name__ == "__main__":
    run_tuner()