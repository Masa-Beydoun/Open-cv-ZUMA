import cv2
import numpy as np
import mss
import os
import time

# 1. استيراد الملفات الخاصة بك
from balls_detection.detect_balls import ZumaBot 
from path_detection.path_detection import capture_game_path, ZUMA_DELUXE_CONFIG , ZUMA_GREEN_JUNGLE_CONFIG , ZUMA_SPACE_CONFIG
from constants import MONITOR 
from roi.detect_roi import analyze_game_screen

def get_ball_position_on_path(ball_pos, path_points):
    """التابع الحسابي لربط موقع الكرة بالمسار"""
    if not path_points or len(path_points) == 0:
        return -1
    path_array = np.array(path_points)
    ball_array = np.array(ball_pos)
    distances = np.linalg.norm(path_array - ball_array, axis=1)
    min_index = np.argmin(distances)
    # إذا كانت المسافة أكبر من 50 بكسل، نعتبر الكرة خارج المسار
    if distances[min_index] > 50: 
        return -1
    return min_index

def main():
    bot = ZumaBot()
    
    # تحميل الألوان (Assets) من مجلد xmas
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    assets_path = os.path.join(project_root, "xmas")
    bot.load_assets(assets_path)   

    # جلب إحداثيات المسار العالمي (مرة واحدة فقط عند التشغيل)
    print("برجاء الانتظار.. يتم جلب المسار الآن...")
    global_path_points = capture_game_path(ZUMA_DELUXE_CONFIG)
    
    if not global_path_points:
        print("خطأ: لم يتم العثور على المسار!")
        return

    # --- مرحلة الحلقة الرئيسية (Main Loop) ---
    with mss.mss() as sct:
        monitor_info = sct.monitors[MONITOR]
        capture_area = None

        while True:
            # تحديث موقع نافذة اللعبة دورياً (لضمان الملاحقة إذا تحركت النافذة)
            full_screenshot = np.array(sct.grab(monitor_info))
            full_frame = cv2.cvtColor(full_screenshot, cv2.COLOR_BGRA2BGR)
            game_region = analyze_game_screen(full_frame)

            if game_region:
                capture_area = game_region.to_mss_dict(monitor_info["left"], monitor_info["top"])
            
            if capture_area:
                # 1. التقاط صورة منطقة اللعبة فقط
                sct_img = sct.grab(capture_area)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # 2. استدعاء تابع الاكتشاف (يرجع الصورة المكتشفة وقائمة البيانات)
                # ملاحظة: تأكد أن التابع detect_from_frame في كلاس ZumaBot يعيد (output, detected_balls_data)
                result_img, detected_balls = bot.detect_from_frame(frame)

                # 3. الربط بين الكرات المكتشفة والمسار العالمي
                for ball in detected_balls:
                    # تحويل إحداثيات الكرة من محلي (داخل النافذة) إلى عالمي (على الشاشة)
                    g_x = ball['pos'][0] + capture_area['left']
                    g_y = ball['pos'][1] + capture_area['top']
                    
                    # البحث عن ترتيب الكرة على المسار
                    idx = get_ball_position_on_path((g_x, g_y), global_path_points)
                    
                    if idx != -1:
                        color = ball['color']
                        # طباعة النتيجة في الكونسول
                        print(f"الكرة {color} في الترتيب رقم {idx} على المسار")
                        
                        # رسم الترتيب على نافذة المعاينة
                        cv2.putText(result_img, f"Idx:{idx}", (ball['pos'][0], ball['pos'][1]-20),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

                # عرض نافذة المعاينة
                cv2.imshow("Zuma Bot - Intelligence Monitor", result_img)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()