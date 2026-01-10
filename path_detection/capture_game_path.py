import cv2
import mss
import numpy as np
import time
from roi.detect_roi import analyze_game_screen
from path_detection.path_detection import (
    solve_zuma_path, 
    ZUMA_SPACE_CONFIG, ZUMA_DELUXE_CONFIG, ZUMA_GREEN_JUNGLE_CONFIG
)

def capture_game_path(config):
    """
    يبحث عن نافذة اللعبة ويستخرج مسار الكرات بصيغة Global Coordinates (إحداثيات الشاشة).
    """
    print(f"--- Initializing Path Capture ---")
    global_path = None

    with mss.mss() as sct:
        # استخدام الشاشة الأولى كمصدر
        monitor_full = sct.monitors[1]
        
        while True:
            # 1. التقاط كامل الشاشة
            screenshot = np.array(sct.grab(monitor_full))
            frame = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

            # 2. تحديد منطقة اللعبة (Game ROI)
            game_region = analyze_game_screen(frame, save_path=None)

            if game_region:
                x, y, w, h = game_region.x, game_region.y, game_region.w, game_region.h
                cropped_game = frame[y:y+h, x:x+w]

                # 3. معالجة المسار داخل منطقة اللعبة فقط
                result_data = solve_zuma_path(cropped_game, config)

                if result_data and result_data.get('path'):
                    # 4. تحويل المسار من محلي (Local) إلى عالمي (Global)
                    global_path = [(lx + x, ly + y) for (lx, ly) in result_data['path']]
                    
                    print(f"[SUCCESS] Captured {len(global_path)} path points.")
                    
                    # معاينة بصرية سريعة
                    if 'visual' in result_data:
                        visual_output = cv2.cvtColor(result_data['visual'], cv2.COLOR_RGB2BGR)
                        cv2.imshow("Calibration - Path Found", visual_output)
                        cv2.waitKey(1500) # انتظار ثانية ونصف للمعاينة
                    
                    break 
                else:
                    print("Game detected but path tracing failed. Check lighting/assets.")
            else:
                print("Searching for Zuma game window on screen...")

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            time.sleep(0.2) 

    cv2.destroyAllWindows()
    return global_path

if __name__ == "__main__":
    # مثال للاستخدام:
    path = capture_game_path(ZUMA_DELUXE_CONFIG)
    
