import cv2
import numpy as np

# ==========================================
# ضع مسار صورة من اللعبة هنا (تظهر فيها القاعدة الزرقاء)
IMAGE_PATH = "./frog_detection/beach.png"
# ==========================================

def nothing(x):
    pass

# تحميل الصورة
img = cv2.imread(IMAGE_PATH)
if img is None:
    print("Error: Image not found!")
    exit()

# تصغير للعرض فقط إذا كانت كبيرة
scale = 0.8
img_disp = cv2.resize(img, None, fx=scale, fy=scale)

cv2.namedWindow('Blue Circle Tuner', cv2.WINDOW_NORMAL)
cv2.resizeWindow('Blue Circle Tuner', 800, 600)

# Trackbars لقيم HSV
# القيم الافتراضية للون السماوي/الأزرق
cv2.createTrackbar('Low H', 'Blue Circle Tuner', 80, 179, nothing)
cv2.createTrackbar('Low S', 'Blue Circle Tuner', 100, 255, nothing)
cv2.createTrackbar('Low V', 'Blue Circle Tuner', 50, 255, nothing)

cv2.createTrackbar('High H', 'Blue Circle Tuner', 110, 179, nothing)
cv2.createTrackbar('High S', 'Blue Circle Tuner', 255, 255, nothing)
cv2.createTrackbar('High V', 'Blue Circle Tuner', 255, 255, nothing)

while True:
    frame = img_disp.copy()
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # قراءة القيم
    l_h = cv2.getTrackbarPos('Low H', 'Blue Circle Tuner')
    l_s = cv2.getTrackbarPos('Low S', 'Blue Circle Tuner')
    l_v = cv2.getTrackbarPos('Low V', 'Blue Circle Tuner')
    h_h = cv2.getTrackbarPos('High H', 'Blue Circle Tuner')
    h_s = cv2.getTrackbarPos('High S', 'Blue Circle Tuner')
    h_v = cv2.getTrackbarPos('High V', 'Blue Circle Tuner')

    lower_blue = np.array([l_h, l_s, l_v])
    upper_blue = np.array([h_h, h_s, h_v])

    # 1. العزل اللوني
    mask = cv2.inRange(hsv, lower_blue, upper_blue)

    # 2. تحسين الماسك (إزالة النويز)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 3. إيجاد الدوائر/الكونتور
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    status_text = "No Circle Found"
    
    # البحث عن أكبر كونتور (يفترض أنه قاعدة القرد)
    if contours:
        largest_cnt = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_cnt)
        
        # فلتر الحجم (تجاهل النقاط الصغيرة جداً)
        if area > 500:
            # إيجاد أصغر دائرة تحيط بالكونتور
            ((cx, cy), radius) = cv2.minEnclosingCircle(largest_cnt)
            
            # رسم الدائرة المكتشفة
            cv2.circle(frame, (int(cx), int(cy)), int(radius), (0, 255, 255), 2)
            cv2.circle(frame, (int(cx), int(cy)), 3, (0, 0, 255), -1)
            
            # رسم المربع المحيط (وهذا ما سيرسله الكلاس للكود الأساسي)
            x, y, w, h = cv2.boundingRect(largest_cnt)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            status_text = f"Found! R={int(radius)} Area={int(area)}"

    # عرض النتائج
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    combined = np.hstack((frame, mask_bgr))
    
    cv2.putText(combined, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imshow('Blue Circle Tuner', combined)

    key = cv2.waitKey(1)
    if key == 27: # ESC
        print("\n=== Final Configuration ===")
        print(f"LOWER_BLUE = np.array([{l_h}, {l_s}, {l_v}])")
        print(f"UPPER_BLUE = np.array([{h_h}, {h_s}, {h_v}])")
        break

cv2.destroyAllWindows()