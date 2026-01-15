# import cv2
# import numpy as np
# import sys, os

# # إضافة المجلد الحالي للمسار
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# try:
#     from frog_detection.FrogTemplateDetector import FrogTemplateDetector
# except ImportError:
#     # محاولة الاستيراد بالطريقة الأخرى في حال اختلف المسار
#     sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#     from frog_detection.FrogTemplateDetector import FrogTemplateDetector

# # ==========================================
# # صورة الضفدع وهو ينظر للأعلى (صورتك المرسلة)
# IMAGE_PATH = "./frog_detection/monkey_up.png"
# # ==========================================

# # ألوان زوما للمقارنة
# ZUMA_COLORS = {
#     "Green": (55, 210),
#     "Orange": (9, 251),
#     "Pink": (160, 222),
#     "Blue": (105, 235),
#     "Yellow": (25, 240),
#     "Cyan": (99, 162),
#     "White": (0, 0),
# }


# def nothing(x):
#     pass


# img = cv2.imread(IMAGE_PATH)
# if img is None:
#     print(f"Error: Image {IMAGE_PATH} not found!")
#     exit()

# # تكبير الصورة قليلاً لرؤية البكسلات بوضوح
# scale_disp = 1.0  # 1.3
# img_disp = cv2.resize(img, None, fx=scale_disp, fy=scale_disp)

# # تهيئة الكاشف
# detector = FrogTemplateDetector(
# )  # عتبة منخفضة لضمان الكشف في الصورة الثابتة

# cv2.namedWindow("Active Offset Tuner", cv2.WINDOW_NORMAL)
# cv2.resizeWindow("Active Offset Tuner", 1000, 700)

# # ==========================================
# # Trackbars: التحكم في مكان وحجم دائرة الفحص
# # ==========================================
# # 1. المسافة عن المركز (نسبة مئوية من عرض القرد)
# # القيمة الافتراضية عندك كانت 0.32 (32%)
# cv2.createTrackbar("Offset Factor %", "Active Offset Tuner", 32, 100, nothing)

# # 2. نصف قطر دائرة الفحص (بالبكسل)
# # القيمة الافتراضية عندك كانت 7
# cv2.createTrackbar("Sample Radius", "Active Offset Tuner", 7, 20, nothing)

# while True:
#     display = img_disp.copy()
#     hsv = cv2.cvtColor(display, cv2.COLOR_BGR2HSV)

#     # 1. اكتشاف القرد
#     res = detector.detect(display)

#     # معالجة اختلاف صيغة الإرجاع (tuple vs box)
#     monkey_box = None
#     if isinstance(res, tuple) and len(res) == 2 and isinstance(res[0], (list, tuple)):
#         monkey_box = res[0]
#     else:
#         monkey_box = res

#     if monkey_box:
#         mx, my, mw, mh = monkey_box

#         # مركز القرد
#         cx = mx + mw // 2
#         cy = my + mh // 2

#         # 2. قراءة قيم التونر
#         offset_pct = (
#             cv2.getTrackbarPos("Offset Factor %", "Active Offset Tuner") / 100.0
#         )
#         sample_r = cv2.getTrackbarPos("Sample Radius", "Active Offset Tuner")
#         if sample_r < 1:
#             sample_r = 1

#         # 3. حساب مكان الكرة (للأعلى - نفس منطق active_monkey_check)
#         pixel_offset = int(mw * offset_pct)

#         # ملاحظة: بما أن القرد في الصورة ينظر للأعلى، فالكرة تكون في Y أقل
#         sample_x = cx
#         sample_y = cy - pixel_offset

#         # 4. تحليل المنطقة
#         # إنشاء قناع دائري
#         mask = np.zeros(display.shape[:2], dtype=np.uint8)
#         cv2.circle(mask, (sample_x, sample_y), sample_r, 255, -1)

#         # حساب متوسط اللون
#         mean_val = cv2.mean(hsv, mask=mask)
#         curr_h, curr_s = int(mean_val[0]), int(mean_val[1])

#         # تحديد اللون الأقرب
#         best_match = "Unknown"
#         min_err = 9999
#         W_H, W_S = 1.0, 0.5

#         for name, (kh, ks) in ZUMA_COLORS.items():
#             dh = abs(curr_h - kh)
#             if dh > 90:
#                 dh = 180 - dh
#             err = (dh * W_H) + (abs(curr_s - ks) * W_S)
#             if err < min_err:
#                 min_err, best_match = err, name

#         # 5. الرسم
#         cv2.rectangle(display, (mx, my), (mx + mw, my + mh), (0, 255, 0), 1)

#         # رسم دائرة الفحص
#         # لون الدائرة يتغير حسب النتيجة: أخضر إذا تطابق، أحمر إذا فشل
#         circle_color = (0, 255, 0) if min_err < 30 else (0, 0, 255)
#         cv2.circle(display, (sample_x, sample_y), sample_r, circle_color, 2)
#         # رسم نقطة المركز
#         cv2.circle(display, (sample_x, sample_y), 1, (0, 255, 255), -1)

#         # 6. عرض المعلومات والتشخيص
#         info_x = mx + mw + 10
#         cv2.putText(
#             display,
#             f"DETECTED: {best_match}",
#             (info_x, my + 20),
#             cv2.FONT_HERSHEY_SIMPLEX,
#             0.8,
#             (0, 255, 255),
#             2,
#         )

#         cv2.putText(
#             display,
#             f"Read H: {curr_h}",
#             (info_x, my + 50),
#             cv2.FONT_HERSHEY_SIMPLEX,
#             0.6,
#             (200, 200, 200),
#             1,
#         )
#         cv2.putText(
#             display,
#             f"Read S: {curr_s}",
#             (info_x, my + 70),
#             cv2.FONT_HERSHEY_SIMPLEX,
#             0.6,
#             (200, 200, 200),
#             1,
#         )

#         # مقارنة مع القيم المثالية للون الزهري والسماوي
#         p_h, p_s = ZUMA_COLORS.get("Pink", (0, 0))
#         c_h, c_s = ZUMA_COLORS.get("Cyan", (0, 0))

#         cv2.putText(
#             display,
#             f"Ref Pink: H{p_h} S{p_s}",
#             (info_x, my + 100),
#             cv2.FONT_HERSHEY_SIMPLEX,
#             0.5,
#             (160, 160, 255),
#             1,
#         )
#         cv2.putText(
#             display,
#             f"Ref Cyan: H{c_h} S{c_s}",
#             (info_x, my + 120),
#             cv2.FONT_HERSHEY_SIMPLEX,
#             0.5,
#             (255, 255, 0),
#             1,
#         )

#     else:
#         cv2.putText(
#             display,
#             "Monkey Not Found in Image",
#             (10, 30),
#             cv2.FONT_HERSHEY_SIMPLEX,
#             0.7,
#             (0, 0, 255),
#             2,
#         )

#     cv2.imshow("Active Offset Tuner", display)

#     # الطباعة عند الخروج
#     if cv2.waitKey(1) & 0xFF == 27:
#         print(f"\n=== NEW SETTINGS FOR active_monkey_check ===")
#         print(f"OFFSET_FACTOR = {offset_pct:.2f}")
#         print(f"SAMPLE_RADIUS = {sample_r}")
#         break

# cv2.destroyAllWindows()


import cv2
import numpy as np

# ==========================================
# ضع صورة القرد وهو يحمل كرة
IMAGE_PATH = './frog_detection/m.png' 
# ==========================================
import cv2
import numpy as np

# ضع صورة القرد وهو ينظر للأعلى هنا

def nothing(x): pass

img = cv2.imread(IMAGE_PATH)
if img is None:
    print("Image not found")
    exit()

img = cv2.resize(img, None, fx=0.8, fy=0.8)
gray_orig = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

cv2.namedWindow('Hough Tuner')
cv2.createTrackbar('Param2', 'Hough Tuner', 20, 100, nothing)
cv2.createTrackbar('Min Radius', 'Hough Tuner', 5, 50, nothing)
cv2.createTrackbar('Max Radius', 'Hough Tuner', 25, 100, nothing)

while True:
    clone = img.copy()
    
    p2 = cv2.getTrackbarPos('Param2', 'Hough Tuner')
    if p2 < 1: p2 = 1
    min_r = cv2.getTrackbarPos('Min Radius', 'Hough Tuner')
    max_r = cv2.getTrackbarPos('Max Radius', 'Hough Tuner')
    
    # محاكاة المنطقة العلوية (ROI) تقريباً
    # سنطبق Hough على الصورة كاملة هنا للتجربة
    
    circles = cv2.HoughCircles(
        gray_orig, cv2.HOUGH_GRADIENT, 1.2, 30,
        param1=50, param2=p2, minRadius=min_r, maxRadius=max_r
    )
    
    if circles is not None:
        circles = np.uint16(np.around(circles))
        for i in circles[0, :]:
            cv2.circle(clone, (i[0], i[1]), i[2], (0, 255, 0), 2)
            cv2.circle(clone, (i[0], i[1]), 2, (0, 0, 255), 3)

    cv2.imshow('Hough Tuner', clone)
    if cv2.waitKey(1) == 27: break

cv2.destroyAllWindows()