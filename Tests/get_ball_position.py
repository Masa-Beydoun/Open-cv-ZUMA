import numpy as np

def get_ball_progress(ball_pos, full_path):
    """
    حساب مدى تقدم الكرة على المسار
    ball_pos: (x, y) إحداثيات مركز الكرة المكتشفة
    full_path: قائمة النقاط [(x1,y1), (x2,y2), ...] الناتجة عن الهيكل العظمي
    """
    if not full_path:
        return -1
    
    # تحويل المسار لمصفوفة لسرعة الحساب
    path_array = np.array(full_path)
    ball_array = np.array(ball_pos)
    
    # حساب المسافة بين مركز الكرة وكل نقطة في المسار
    distances = np.linalg.norm(path_array - ball_array, axis=1)
    
    # إيجاد "اندكس" أقرب نقطة
    closest_index = np.argmin(distances)
    
    # إذا كانت المسافة لأقرب نقطة كبيرة جداً، فالكرة ليست على هذا المسار
    if distances[closest_index] > 20: # عتبة (Threshold) اختيارية
        return -1
        
    return closest_index # كلما زاد الرقم، كانت الكرة أقرب للنهاية (الفتحة)