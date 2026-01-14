import cv2
import mss
import numpy as np
from roi.detect_roi import analyze_game_screen
from path_detection.path_detection import solve_zuma_path, ZUMA_SPACE_CONFIG , ZUMA_DELUXE_CONFIG ,ZUMA_GREEN_JUNGLE_CONFIG 

def run_zuma_solver():
    config = ZUMA_SPACE_CONFIG 
    
    with mss.mss() as sct:
        monitor_full = sct.monitors[1]
        

        while True:
            # 1. التقاط الشاشة كاملة
            screenshot = np.array(sct.grab(monitor_full))
            frame = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

            # 2. تحديد منطقة اللعبة
            game_region = analyze_game_screen(frame, save_path=None)

            if game_region:
                # 3. قص منطقة اللعبة
                x, y, w, h = game_region.x, game_region.y, game_region.w, game_region.h
                cropped_game = frame[y:y+h, x:x+w]

                # 4. استدعاء تابع المسار (نمرر المصفوفة المقصوصة مباشرة)
                result_data = solve_zuma_path(cropped_game, config)

                if result_data and 'path' in result_data:
                    visual_output = cv2.cvtColor(result_data['visual'], cv2.COLOR_RGB2BGR)
                    
                    cv2.imshow("Detected Path (Live)", visual_output)
                    print(f" Path found: {len(result_data['path'])} points")
                else:
                    cv2.imshow("Detected Path (Live)", cropped_game)
                    print(" Game ROI found, but path failed.")
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_zuma_solver()