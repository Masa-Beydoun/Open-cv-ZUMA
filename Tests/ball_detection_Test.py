import sys
import os

# إضافة المجلد الرئيسي للمشروع (Open-cv-ZUMA) إلى مسار البحث
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

import cv2
import mss
import numpy as np

# الآن الاستدعاءات ستتم بشكل سليم من المجلد الرئيسي
from balls_detection.detect_balls import ZumaBot 
from path_detection.path_detection import ZUMA_GREEN_JUNGLE_CONFIG
def test_live_detection():

    bot = ZumaBot(ZUMA_GREEN_JUNGLE_CONFIG)
    
    print("--- Starting Live Test (Press 'q' to quit) ---")
    
    with mss.mss() as sct:
        # تحديد الشاشة كاملة أو جزء منها
        monitor = sct.monitors[1]
        
        while True:
            # 2. التقاط صورة للشاشة
            screenshot = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
            # 3. استدعاء التابع (تجاهلنا المناطق المتجاهلة والماسك حالياً)
            result_img, balls_data = bot.detect_from_frame(frame, ignored_zones=[])
            
            # 4. التأكد من العمل عبر الطباعة والرسم
            if len(balls_data) > 0:
                print(f"Detected {len(balls_data)} balls: {balls_data[0]}") # طباعة أول كرة للتأكد
            
            # عرض النتيجة
            cv2.imshow("Testing Zuma Bot", result_img)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_live_detection()