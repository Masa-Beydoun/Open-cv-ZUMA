import cv2
import numpy as np
import mss
import os
import sys
import json

# --- إعداد المسارات والاستيراد ---
try:
    from roi.detect_roi import analyze_game_screen
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from roi.detect_roi import analyze_game_screen

# متغيرات للرسم (Global variables for mouse callback)
drawing = False
ix, iy = -1, -1
current_rect = None
zones_buffer = []

def draw_zone_callback(event, x, y, flags, param):
    global ix, iy, drawing, current_rect, zones_buffer
    
    # عند الضغط على زر الماوس الأيسر: بداية الرسم
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y

    # عند تحريك الماوس مع الضغط: تحديث المستطيل الوهمي
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            current_rect = (ix, iy, x, y)

    # عند رفع زر الماوس: إنهاء الرسم وحفظ المستطيل
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        # تصحيح الإحداثيات (في حال الرسم من اليمين لليسار أو من الأسفل للأعلى)
        x_start, x_end = sorted([ix, x])
        y_start, y_end = sorted([iy, y])
        w = x_end - x_start
        h = y_end - y_start
        
        if w > 5 and h > 5: # تجاهل النقرات الصغيرة جداً
            zones_buffer.append([x_start, y_start, w, h])
        current_rect = None

def select_zones_manually(img):
    global zones_buffer, current_rect
    zones_buffer = [] # تصفير القائمة
    
    window_name = "Step 1: Draw Ignored Zones"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, draw_zone_callback)
    
    print(">> وضع الرسم: ارسم مستطيلات حول المناطق غير المهمة.")
    print(">> 'z': تراجع عن آخر مستطيل")
    print(">> 'c': مسح الكل")
    print(">> 'Enter': حفظ وبدء الـ Tuner")

    clone = img.copy()
    
    while True:
        display_img = clone.copy()
        
        # رسم المناطق المحفوظة
        for (x, y, w, h) in zones_buffer:
            cv2.rectangle(display_img, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.rectangle(display_img, (x, y), (x + w, y + h), (0, 0, 255), -1) # تعبئة خفيفة
            
        # رسم المستطيل الحالي (الذي يتم سحبه الآن)
        if current_rect:
            (x1, y1, x2, y2) = current_rect
            cv2.rectangle(display_img, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # إضافة الشفافية للمناطق الحمراء
        alpha = 0.3
        cv2.addWeighted(display_img, alpha, clone, 1 - alpha, 0, display_img)
        
        # تعليمات
        cv2.putText(display_img, "Draw zones to IGNORE. Press ENTER to Save & Start.", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(display_img, f"Zones: {len(zones_buffer)} (Press 'z' to undo)", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow(window_name, display_img)
        key = cv2.waitKey(1) & 0xFF

        if key == 13: # Enter Key
            break
        elif key == ord("c"): # Clear
            zones_buffer = []
        elif key == ord("z"): # Undo
            if zones_buffer:
                zones_buffer.pop()

    cv2.destroyWindow(window_name)
    
    # حفظ المناطق في ملف JSON
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "ignored_zones.json")
    with open(json_path, 'w') as f:
        json.dump(zones_buffer, f)
    
    print(f"✅ تم حفظ {len(zones_buffer)} منطقة في ملف ignored_zones.json")
    return zones_buffer

# --- بقية كود الـ Tuner ---
def nothing(x): pass

def run_tuner():
    print("Looking for game window...")
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        full_img = np.array(sct.grab(monitor))
        full_img = cv2.cvtColor(full_img, cv2.COLOR_BGRA2BGR)
        region = analyze_game_screen(full_img)
        
        if not region:
            print("لم يتم العثور على اللعبة!")
            return

        capture_area = region.to_mss_dict(monitor["left"], monitor["top"])
        
        # التقاط صورة واحدة لاستخدامها في الرسم
        base_img = np.array(sct.grab(capture_area))
        base_img = cv2.cvtColor(base_img, cv2.COLOR_BGRA2BGR)
        
        # === الخطوة 1: الرسم اليدوي ===
        ignored_zones = select_zones_manually(base_img)

        # === الخطوة 2: بدء الـ Tuner ===
        window_name = "Step 2: Real-time Tuner"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)
        
        cv2.createTrackbar("Min Dist", window_name, 26, 100, nothing)
        cv2.createTrackbar("Param 1", window_name, 56, 300, nothing)
        cv2.createTrackbar("Param 2", window_name, 39, 100, nothing)
        cv2.createTrackbar("Min Radius", window_name, 16, 100, nothing)
        cv2.createTrackbar("Max Radius", window_name, 23, 100, nothing)

        while True:
            img = np.array(sct.grab(capture_area))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            output = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # تطبيق المناطق التي رسمتها
            if ignored_zones:
                for (ix, iy, iw, ih) in ignored_zones:
                    cv2.rectangle(gray, (ix, iy), (ix + iw, iy + ih), 0, -1)
                    # عرض المناطق باللون الأحمر
                    cv2.rectangle(output, (ix, iy), (ix + iw, iy + ih), (0, 0, 255), 2)
                    cv2.line(output, (ix, iy), (ix+iw, iy+ih), (0, 0, 255), 1)
                    cv2.line(output, (ix+iw, iy), (ix, iy+ih), (0, 0, 255), 1)

            gray = cv2.medianBlur(gray, 5)

            # قراءة القيم
            min_dist = max(1, cv2.getTrackbarPos("Min Dist", window_name))
            p1 = max(1, cv2.getTrackbarPos("Param 1", window_name))
            p2 = max(1, cv2.getTrackbarPos("Param 2", window_name))
            min_r = max(1, cv2.getTrackbarPos("Min Radius", window_name))
            max_r = max(1, cv2.getTrackbarPos("Max Radius", window_name))
            if max_r <= min_r: max_r = min_r + 1

            circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1, 
                                     minDist=min_dist, param1=p1, param2=p2, 
                                     minRadius=min_r, maxRadius=max_r)

            detected_count = 0
            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                detected_count = len(circles)
                for (x, y, r) in circles:
                    cv2.circle(output, (x, y), r, (0, 0, 0), 1)
                    cv2.circle(output, (x, y), 2, (255, 0, 0), 1)

            info_text = [
                f"Detected: {detected_count}",
                f"Ignored Zones: {len(ignored_zones)} (Active)",
                f"Reference Width: {capture_area['width']}"
            ]
            for i, line in enumerate(info_text):
                cv2.putText(output, line, (10, 30 + (i * 30)), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

            cv2.imshow(window_name, output)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print(f"\nFinal Settings saved from width {capture_area['width']}:")
                print(f"Dist: {min_dist}, P1: {p1}, P2: {p2}, R: {min_r}-{max_r}")
                break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_tuner()