import cv2
import mss
import numpy as np
from roi.detect_roi import analyze_game_screen

def test_single_shot_roi():
    with mss.mss() as sct:
        # 1. التقاط لقطة شاشة واحدة فقط فوراً
        screenshot = np.array(sct.grab(sct.monitors[1]))
        frame = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
        
        print("تم التقاط الشاشة، جاري التحليل...")

        # 2. استدعاء تابع الـ ROI لمعرفة الإحداثيات
        game_region = analyze_game_screen(frame, save_path=None)

        if game_region:
            # 3. رسم المستطيل الأحمر على الصورة الأصلية للتأكد من المكان
            x, y, w, h = game_region.x, game_region.y, game_region.w, game_region.h
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 5)
            
            # كتابة الأبعاد فوق المستطيل
            cv2.putText(frame, f"ROI: {w}x{h}", (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            print(f" تم تحديد منطقة: x={x}, y={y}, w={w}, h={h}")
        else:
            print("التابع لم يستطع تحديد أي منطقة للعبة.")

        # 4. عرض النتيجة النهائية (صورة واحدة ثابتة)
        resized_view = cv2.resize(frame, (1280, 720))
        cv2.imshow("ROI Check - Single Shot", resized_view)
        
        print("اضغط أي مفتاح بالكييبورد لتسكير الصورة...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

if __name__ == "__main__":
    test_single_shot_roi()