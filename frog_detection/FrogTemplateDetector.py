import cv2
import numpy as np


class FrogTemplateDetector:

    def __init__(self):
        # القيم الافتراضية للقرص الأزرق (عدلها بناء على نتيجة الـ Tuner)
        # هذا النطاق يغطي اللون السماوي/الأزرق للقاعدة

        self.lower_blue = np.array([88, 119, 86])
        self.upper_blue = np.array([99, 255, 255])

        self.kernel = np.ones((5, 5), np.uint8)

    def detect(self, frame):
        """
        يعيد (x, y, w, h) للمربع المحيط بالقاعدة الزرقاء.
        """
        # تحويل إلى HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # عزل اللون الأزرق
        mask = cv2.inRange(hsv, self.lower_blue, self.upper_blue)

        # تنظيف الماسك
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel)

        # إيجاد الكونتورات
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # نأخذ أكبر جسم أزرق في الشاشة (يفترض أنه قاعدة القرد)
        largest_cnt = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_cnt)

        # شرط أمان للحجم (حتى لا نلتقط كرة زرقاء صغيرة بالخطأ)
        if area < 1000:  # رقم تقريبي، يمكن تعديله
            return None

        # استخراج المربع المحيط
        x, y, w, h = cv2.boundingRect(largest_cnt)

        # توسيع المربع قليلاً (اختياري)
        # لأن القاعدة أصغر قليلاً من رأس القرد ويديه
        # سنضيف هامش بسيط ليغطي القرد كاملاً
        padding = int(w * 0.05)  # 20% زيادة

        # حساب الإحداثيات الجديدة مع التأكد من حدود الصورة
        h_img, w_img = frame.shape[:2]
        new_x = max(0, x - padding)
        new_y = max(0, y - padding)
        new_w = min(w_img - new_x, w + padding * 2)
        new_h = min(h_img - new_y, h + padding * 2)

        # إرجاع القيمة بنفس الصيغة التي يحبها الكود الأساسي
        # نعيد ((box), score) لكي يتقبلها الكود الذي كتبناه سابقاً
        # الـ Score هنا 1.0 لأننا واثقون من اللون
        return (new_x, new_y, new_w, new_h), 1.0
