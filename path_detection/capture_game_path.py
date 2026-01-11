import cv2
import mss
import numpy as np
import time
from roi.detect_roi import analyze_game_screen
from path_detection.path_detection import (
    solve_zuma_path, 
    ZUMA_SPACE_CONFIG, ZUMA_DELUXE_CONFIG, ZUMA_GREEN_JUNGLE_CONFIG
)

def get_largest_component(mask):
    
    if mask is None: return None
    
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    
    if num_labels <= 1: 
        return mask

    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    
    cleaned_mask = np.zeros_like(mask)
    cleaned_mask[labels == largest_label] = 255
    
    return cleaned_mask

def capture_game_path(config):

    print(f"--- Initializing Path & Mask Capture ---")
    global_path = None
    path_mask = None 

    with mss.mss() as sct:
        monitor_full = sct.monitors[1]
        
        while True:
            screenshot = np.array(sct.grab(monitor_full))
            frame = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
            # 1. تحديد منطقة اللعبة
            game_region = analyze_game_screen(frame, save_path=None)

            if game_region:
                x, y, w, h = game_region.x, game_region.y, game_region.w, game_region.h
                cropped_game = frame[y:y+h, x:x+w]

                # 2. استدعاء خوارزمية حل المسار
                result_data = solve_zuma_path(cropped_game, config)

                if result_data and result_data.get('mask') is not None:
                    # تحويل إحداثيات النقاط لـ Global
                    global_path = [(lx + x, ly + y) for (lx, ly) in result_data.get('path', [])]
                    
                    # --- معالجة الماسك الاحترافية ---
                    raw_mask = result_data['mask']
                    
                    # أ- ملء الفجوات (Closing) لربط المسار المقطع
                    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
                    temp_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, kernel_close)
                    
                    # ب- حذف أي ضجيج أو قطع صغيرة (النقاط اللي بالزوايا)
                    clean_single_mask = get_largest_component(temp_mask)
                    
                    # ج- إضافة Padding (توسيع) للمسار ليغطي عرض الكرة
                    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                    path_mask = cv2.dilate(clean_single_mask, kernel_dilate, iterations=3)
                    
                    print(f"[SUCCESS] Captured Path and Cleaned/Padded Mask.")
                    break 
                else:
                    print("Game detected but path tracing failed. Retrying...")
            else:
                print("Searching for Zuma game window...")

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            time.sleep(0.2) 

    cv2.destroyAllWindows()
    return global_path, path_mask

if __name__ == "__main__":
    points, mask = capture_game_path(ZUMA_GREEN_JUNGLE_CONFIG)
    
    if mask is not None:
        print(f"Path Points: {len(points) if points else 0}")
        cv2.imshow("Final Clean Mask", mask)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    