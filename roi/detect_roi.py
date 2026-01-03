import cv2
import numpy as np

try:
    from .game_region import GameRegion
except Exception:
    from game_region import GameRegion

def analyze_game_screen(input_source, save_path=None):
    if isinstance(input_source, str):
        img = cv2.imread(input_source)
    else:
        img = input_source # الصورة قادمة مباشرة من الذاكرة

    if img is None:
        print("خطأ: الصورة غير صالحة")
        return None

    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # --- تعريف الألوان ---
    # اللون البيج الخاص بحاوية الموقع
    lower_beige = np.array([10, 20, 180])   # (H, S, V) - حد أدنى
    upper_beige = np.array([19, 44, 216])  # (H, S, V) - حد أقصى


    # ========================================================
    # الخطوة 1: الكشف الأولي عن الكتل البيج
    # ========================================================
    mask_beige = cv2.inRange(hsv, lower_beige, upper_beige)
    
    # تنظيف القناع
    kernel = np.ones((5, 5), np.uint8)
    mask_beige = cv2.morphologyEx(mask_beige, cv2.MORPH_OPEN, kernel)
    mask_beige = cv2.morphologyEx(mask_beige, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask_beige, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    is_standard_mode = False
    container_rect = None

    if contours:
        # نأخذ أكبر كتلة بيج
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w_cont, h_cont = cv2.boundingRect(largest_contour)
        area = cv2.contourArea(largest_contour)
        
        img_area = h * w
        
        # --- الفحص الذكي (The Smart Check) ---
        # 1. هل المساحة منطقية؟ (ليست صغيرة جداً وليست الصورة كاملة بنسبة 100%)
        # 2. هل توجد هوامش؟ (إذا كان المستطيل يلامس حواف الصورة اليسرى أو اليمنى، فهو ليس حاوية، بل لعبة بملء الشاشة)
        
        margin_threshold = 10 # 10 بكسل هامش خطأ
        touches_sides = (x <= margin_threshold) or ((x + w_cont) >= w - margin_threshold)
        
        # الشرط: مساحة معقولة + لا يلامس الحواف الجانبية (لأن حاوية الموقع دائماً وسطية وحولها صخور)
        if area > (img_area * 0.1) and not touches_sides:
            is_standard_mode = True
            container_rect = (x, y, w_cont, h_cont)
            print(f"تم اكتشاف حاوية موقع (مع هوامش جانبية). الأبعاد: {container_rect}")
        else:
            print("الكتلة البيج تلامس الحواف أو تغطي الشاشة، سيتم اعتبارها وضع شاشة كاملة.")

    # ========================================================
    # الخطوة 2: التوجيه حسب الوضع المكتشف
    # ========================================================
    
    result_img = img.copy()
    final_rect = (0, 0, w, h) # القيمة الافتراضية

    if is_standard_mode:
        print(">> الوضع: Standard Browser Mode")
        final_rect = process_standard_mode(img, hsv, container_rect, lower_beige, upper_beige)
    else:
        print(">> الوضع: Full Screen Mode")
        final_rect = process_fullscreen_mode(img)

    # ========================================================
    # الخطوة 3: الرسم والحفظ
    # ========================================================
    fx, fy, fw, fh = final_rect
    
    if save_path != None:
        
        # # رسم المستطيل النهائي
        cv2.rectangle(result_img, (fx, fy), (fx+fw, fy+fh), (0, 255, 0), 4)
        
        # # كتابة الأبعاد والوضع
        mode_text = "Mode: Standard" if is_standard_mode else "Mode: Full Screen"
        cv2.putText(result_img, f"{mode_text} ({fw}x{fh})", (fx, fy - 15), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        cv2.imwrite(save_path, result_img)
        print(f'image saved to {save_path}')
    
    game_data = GameRegion(fx, fy, fw, fh, img)
    
    return game_data
    
    # عرض النتيجة (اختياري)
    # cv2.imshow("Final Result", result_img)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()


def process_standard_mode(img, hsv, cont_rect, lower_b, upper_b):
    x_c, y_c, w_c, h_c = cont_rect
    
    # التركيز فقط داخل الحاوية المكتشفة
    roi_hsv = hsv[y_c:y_c+h_c, x_c:x_c+w_c]
    
    # عزل اللعبة عن الحاوية (Inverse Mask)
    mask_inner = cv2.inRange(roi_hsv, lower_b, upper_b)
    mask_not_beige = cv2.bitwise_not(mask_inner)
    
    # تنظيف لإزالة النصوص الصغيرة
    clean_kernel = np.ones((3, 3), np.uint8)
    mask_game = cv2.morphologyEx(mask_not_beige, cv2.MORPH_OPEN, clean_kernel)
    
    # البحث عن أكبر كتلة "ليست بيج" داخل الحاوية
    contours, _ = cv2.findContours(mask_game, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        game_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(game_contour) > 2000: # تجاهل الضوضاء الصغيرة
            gx, gy, gw, gh = cv2.boundingRect(game_contour)
            return (x_c + gx, y_c + gy, gw, gh)
    
    # في حال فشل العزل الداخلي، نرجع الحاوية كاملة كحل بديل
    return cont_rect

def process_fullscreen_mode(img):
    """ 
    منطق ذكي لفصل اللعبة عن نافذة Inspector 
    يعتمد على: الفصل (Erosion) + التمركز (Centrality) 
    """
    h_img, w_img = img.shape[:2]
    center_x, center_y = w_img // 2, h_img // 2
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. العتبة: عزل المناطق المضيئة (اللعبة + المفتش) عن الخلفية السوداء
    _, thresh = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY)
    
    # 2. الفصل الجراحي (Erosion):
    # نقوم بتآكل الكتل قليلاً لفصل اللعبة عن المفتش إذا كانا متلامسين
    # نستخدم كيرنل (3,3) لقطع الوصلات الصغيرة
    separation_kernel = np.ones((3, 3), np.uint8) 
    thresh_separated = cv2.erode(thresh, separation_kernel, iterations=2)
    
    # 3. العثور على الكتل المنفصلة
    contours, _ = cv2.findContours(thresh_separated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best_rect = (0, 0, w_img, h_img)
    best_score = -float('inf')
    
    found_candidate = False

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h # نستخدم مساحة المستطيل بدلاً من الكونتور لتجنب الفراغات الداخلية
        
        # تجاهل العناصر الصغيرة جداً
        if area < (h_img * w_img * 0.05):
            continue
            
        # --- نظام النقاط الذكي (Scoring System) ---
        
        # 1. حساب مركز هذا الجسم
        obj_center_x = x + w // 2
        obj_center_y = y + h // 2
        
        # 2. حساب المسافة عن مركز الشاشة (نفضل الأجسام المركزية)
        dist_from_center = ((obj_center_x - center_x)**2 + (obj_center_y - center_y)**2)**0.5
        
        # 3. عقوبة الالتصاق بالحواف السفلية أو الجانبية (Inspector Penalty)
        # نافذة المفتش عادة تكون ملتصقة تماماً بالأسفل أو اليمين
        edge_penalty = 0
        if y + h >= h_img - 5: # يلامس الأسفل
             edge_penalty += 1000 
        if x + w >= w_img - 5: # يلامس اليمين
             edge_penalty += 1000
             
        # المعادلة النهائية: المساحة أهم شيء، لكن نطرح المسافة والعقوبات
        # نضرب المساحة في عامل لكي لا تطغى المسافة عليها
        score = area - (dist_from_center * 500) - (edge_penalty * 5000)
        
        if score > best_score:
            best_score = score
            # يجب "توسيع" المستطيل قليلاً لتعويض الـ Erosion الذي قمنا به سابقاً
            padding = 6 # (iterations * kernel_size / 2) تقريباً
            
            final_x = max(0, x - padding)
            final_y = max(0, y - padding)
            final_w = min(w_img - final_x, w + padding*2)
            final_h = min(h_img - final_y, h + padding*2)
            
            best_rect = (final_x, final_y, final_w, final_h)
            found_candidate = True

    if not found_candidate:
        print("تحذير: لم يتم العثور على كتل واضحة، سيتم إرجاع الصورة كاملة.")
        
    return best_rect