import time
import cv2
import mss
import numpy as np

from detect_roi import analyze_game_screen


def run_dynamic_game_viewer():
    print("--- تشغيل العارض الديناميكي (يلاحق السكرول والزوم) ---")
    print("الآن يمكنك تحريك الصفحة أو تغيير حجمها وسيقوم الكود بالتحديث تلقائياً.")
    time.sleep(2) 

    # تعريف المتغيرات الأولية
    window_name = "Dynamic Game View"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 600, 400) # حجم مبدئي للنافذة
    
    # لتخزين آخر مكان معروف للعبة (للحفاظ على الاستقرار إذا فشل الكشف للحظة)
    last_game_data = None

    with mss.mss() as sct:
        # الشاشة التي سنراقبها (الشاشة الرئيسية)
        monitor_full = sct.monitors[1]
        
        while True:
            loop_start = time.time()
            
            # 1. التقاط الشاشة كاملة في كل إطار (ضروري لملاحقة الحركة)
            full_screenshot = np.array(sct.grab(monitor_full))
            full_img_bgr = cv2.cvtColor(full_screenshot, cv2.COLOR_BGRA2BGR)
            
            # 2. استدعاء دالة التحليل على الصورة الجديدة
            # ملاحظة: نمرر save_path=None لمنع الحفظ على القرص وتسريع الأداء
            current_game_data = analyze_game_screen(full_img_bgr, save_path=None)
            
            target_data = None
            
            if current_game_data:
                # تم العثور على اللعبة بنجاح في مكان جديد
                target_data = current_game_data
                last_game_data = current_game_data # تحديث الذاكرة
            elif last_game_data:
                # لم يتم العثور عليها في هذا الإطار (ربما ومضة)، نستخدم آخر مكان معروف
                target_data = last_game_data
            
            # 3. العرض والقص
            if target_data:
                # قص اللعبة من الصورة الكاملة بناءً على الإحداثيات الجديدة
                # انتبه: game_data.roi قد يكون موجوداً، لكننا سنقصه يدوياً للتأكد
                x, y, w, h = target_data.x, target_data.y, target_data.w, target_data.h
                
                # حماية من الأخطاء إذا كانت الإحداثيات خارج الحدود
                if y+h <= full_img_bgr.shape[0] and x+w <= full_img_bgr.shape[1]:
                    game_view = full_img_bgr[y:y+h, x:x+w]
                    
                    # عرض النتيجة
                    cv2.imshow(window_name, game_view)
                
                # طباعة معلومات التتبع (اختياري)
                # print(f"\rTracking: x={x}, y={y} | FPS: {1/(time.time()-loop_start):.1f}", end="")
            else:
                # إذا لم نجد اللعبة أبداً
                cv2.imshow(window_name, full_img_bgr) # نعرض الشاشة كاملة مؤقتاً
            
            # الخروج
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_dynamic_game_viewer()