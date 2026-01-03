import os
# تأكد من طريقة الاستيراد الصحيحة حسب موقع الملف كما شرحنا سابقاً
# إذا كان الملف بجانب detect_roi.py استخدم:
from detect_roi import analyze_game_screen 

# 1. تحديد المسار الحالي الذي يوجد فيه ملف playground.py
current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. تحديد مسار مجلد الصور (samples) ومجلد النتائج (results)
# نربط المسار الحالي باسم المجلد لضمان الدقة
samples_dir = os.path.join(current_dir, 'samples')
results_dir = os.path.join(current_dir, 'results')

# التأكد من أن مجلد النتائج موجود، وإلا يتم إنشاؤه
os.makedirs(results_dir, exist_ok=True)

def process_image(image_name):
    # تكوين المسار الكامل للصورة
    input_path = os.path.join(samples_dir, image_name)
    
    # تكوين مسار الحفظ (نضيف الصورة داخل مجلد results)
    output_path = os.path.join(results_dir, f"res_{image_name}")
    
    # التحقق من وجود الصورة قبل محاولة معالجتها
    if os.path.exists(input_path):
        print(f"جاري معالجة: {image_name}")
        analyze_game_screen(input_path, save_path=output_path)
    else:
        print(f"❌ خطأ: لم يتم العثور على الصورة في المسار: {input_path}")

# --- التشغيل ---
imageList = [
     'h2.png', 'h3.png', 
    's1.png', 's2.png', 's3.png', 
    'f1.png',  'f3.png'
]

for img in imageList:
    process_image(img)