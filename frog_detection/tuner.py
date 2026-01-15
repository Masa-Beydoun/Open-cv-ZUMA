import cv2
import numpy as np

# ==========================================
# ضع مسار الصورة التي تظهر فيها المشكلة هنا
IMAGE_PATH = "./frog_detection/green.jpg.png"
# ==========================================


def nothing(x):
    pass


# تحميل الصورة
original_frame = cv2.imread(IMAGE_PATH)
if original_frame is None:
    print("Error: Image not found! Please check the path.")
    exit()

# تصغير الصورة قليلاً للعرض إذا كانت كبيرة
original_frame = cv2.resize(original_frame, (800, 600))

# إنشاء نافذة التحكم
cv2.namedWindow("Zuma Frog Tuner", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Zuma Frog Tuner", 600, 400)

# القيم المبدئية (نفس القيم الحالية في كودك)
cv2.createTrackbar("Low H", "Zuma Frog Tuner", 35, 179, nothing)
cv2.createTrackbar("Low S", "Zuma Frog Tuner", 50, 255, nothing)
cv2.createTrackbar("Low V", "Zuma Frog Tuner", 40, 255, nothing)

cv2.createTrackbar("High H", "Zuma Frog Tuner", 85, 179, nothing)
cv2.createTrackbar("High S", "Zuma Frog Tuner", 255, 255, nothing)
cv2.createTrackbar("High V", "Zuma Frog Tuner", 255, 255, nothing)

# Kernel للمورفولوجي (نفس الموجود في كودك)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

while True:
    # 1. قراءة القيم من الـ Trackbars
    l_h = cv2.getTrackbarPos("Low H", "Zuma Frog Tuner")
    l_s = cv2.getTrackbarPos("Low S", "Zuma Frog Tuner")
    l_v = cv2.getTrackbarPos("Low V", "Zuma Frog Tuner")

    h_h = cv2.getTrackbarPos("High H", "Zuma Frog Tuner")
    h_s = cv2.getTrackbarPos("High S", "Zuma Frog Tuner")
    h_v = cv2.getTrackbarPos("High V", "Zuma Frog Tuner")

    lower_green = np.array([l_h, l_s, l_v])
    upper_green = np.array([h_h, h_s, h_v])

    # 2. تطبيق نفس منطق الكود الخاص بك تماماً
    # ROI Center Logic (Simulated on full frame for visualization)
    roi = (
        original_frame.copy()
    )  # في الكود الحقيقي أنت تأخذ ROI، هنا سنعمل على الصورة كاملة

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_green, upper_green)

    # تطبيق المورفولوجي (مهم جداً لأنه يدمج الكرة مع الضفدع أحياناً)
    mask_cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 3. إيجاد الكونتور ورسم المستطيل
    contours, _ = cv2.findContours(
        mask_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    result_frame = roi.copy()

    # البحث عن أكبر كونتور (منطق الضفدع)
    best_cnt = None
    max_area = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        # فلتر بسيط للمساحة لإزالة الضوضاء
        if area > 100:
            if area > max_area:
                max_area = area
                best_cnt = cnt

    status_text = "Frog Not Found"
    color_status = (0, 0, 255)

    if best_cnt is not None:
        x, y, w, h = cv2.boundingRect(best_cnt)

        # رسم المستطيل الأخضر (حدود الضفدع المكتشفة)
        cv2.rectangle(result_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # رسم نقطة الفحص المتوقعة (بناء على منطقك القديم)
        # dynamic_offset_y = int(nfh * BALL_OFFSET_FACTOR) -> لنفترض الفاكتور 0.5 تقريباً
        center_x = x + w // 2
        center_y = y + h // 2

        # محاكاة لمنطق الخطأ: كلما كبر الصندوق، ارتفعت النقطة
        # سنرسم خط يوضح الارتفاع
        cv2.circle(result_frame, (center_x, center_y), 5, (0, 0, 255), -1)

        status_text = f"Area: {int(max_area)} | W: {w} H: {h}"
        color_status = (0, 255, 0)

    # 4. عرض النتائج
    # تحويل الماسك لصورة ملونة لدمجها بالعرضq
    mask_bgr = cv2.cvtColor(mask_cleaned, cv2.COLOR_GRAY2BGR)

    # دمج الصورة الأصلية مع الماسك
    combined = np.hstack((result_frame, mask_bgr))

    # كتابة القيم الحالية على الصورة
    cv2.putText(
        combined,
        f"Lower: [{l_h},{l_s},{l_v}]",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2,
    )
    cv2.putText(
        combined,
        f"Upper: [{h_h},{h_s},{h_v}]",
        (10, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2,
    )
    cv2.putText(
        combined, status_text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_status, 2
    )
    print(f"Lower: [{l_h},{l_s},{l_v}]")
    print(f"Upper: [{h_h},{h_s},{h_v}]")
    cv2.imshow("Result (Left) | Mask (Right)", combined)

    key = cv2.waitKey(1)
    if key == 27:  # ESC
        break

cv2.destroyAllWindows()
