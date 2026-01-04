import cv2
import numpy as np
import os
import glob

try:
    from constants import GAME_VERSION
except ImportError:
    import sys, os

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from constants import GAME_VERSION

# ==========================================
# إعدادات
# ==========================================
WINDOW_NAME = "Multi-Ball Tuner"
THUMB_SIZE = 150 

def nothing(x):
    pass


def resize_and_pad(img, target_size):
    if img is None: return np.zeros((target_size, target_size, 3), dtype=np.uint8)

    h, w = img.shape[:2]
    scale = min(target_size / w, target_size / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((target_size, target_size, 3), dtype=np.uint8)
    y_offset = (target_size - new_h) // 2
    x_offset = (target_size - new_w) // 2
    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized_img

    return canvas


def load_images(folder):
    images = []
    names = []
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder)
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), folder)
    
    if not os.path.exists(path):
        print(f"Error: Folder '{folder}' not found.")
        return [], []

    files = sorted(glob.glob(os.path.join(path, "ball_*.png")))
    
    if not files:
        print(f"No ball images found in {path}")
        return [], []

    for f in files:
        img = cv2.imread(f, cv2.IMREAD_UNCHANGED)
        if img is not None:
            images.append(img)
            names.append(os.path.basename(f))
            print(f"Loaded: {os.path.basename(f)}")
            
    return images, names

def run_multi_tuner():
    images, names = load_images(GAME_VERSION)
    if not images: return

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, THUMB_SIZE * 3 + 50, len(images) * THUMB_SIZE + 100)

    cv2.createTrackbar("Crop Top %", WINDOW_NAME, 20, 50, nothing) 
    cv2.createTrackbar("Crop Right %", WINDOW_NAME, 20, 50, nothing)
    cv2.createTrackbar("Min Saturation", WINDOW_NAME, 40, 255, nothing)

    print("\n=== Controls ===")
    print("Adjust sliders to find ONE setting that works for ALL balls.")
    print("Press 'q' to save values and exit.\n")

    while True:
        crop_y_pct = cv2.getTrackbarPos("Crop Top %", WINDOW_NAME) / 100.0
        crop_x_pct = cv2.getTrackbarPos("Crop Right %", WINDOW_NAME) / 100.0
        sat_thresh = cv2.getTrackbarPos("Min Saturation", WINDOW_NAME)

        rows = []

        # [NEW] قاموس لتخزين النتائج (Hue, Saturation)
        current_colors = {}

        for i, original_img in enumerate(images):
            # 1. عملية القص
            h, w = original_img.shape[:2]
            y_start = int(h * crop_y_pct)
            x_end = int(w * (1 - crop_x_pct))
            if y_start >= h: y_start = h - 1
            if x_end <= 0: x_end = 1
            cropped = original_img[y_start:h, 0:x_end].copy()

            # 2. عملية العزل
            if cropped.shape[2] == 4:
                bgr = cropped[:, :, :3]
                alpha = cropped[:, :, 3]
                hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
                mask = (alpha > 0) & (hsv[:, :, 1] > sat_thresh)
            else:
                hsv = cv2.cvtColor(cropped, cv2.COLOR_BGR2HSV)
                mask = hsv[:, :, 1] > sat_thresh

            # 3. حساب متوسط اللون (Hue AND Saturation)
            mean_color_bgr = (50, 50, 50)
            hue_val = 0
            sat_val = 0

            if np.count_nonzero(mask) > 0:
                mean = cv2.mean(hsv, mask=mask.astype(np.uint8))
                hue_val = int(mean[0])
                sat_val = int(mean[1])  # [NEW] استخراج التشبع

                # [NEW] تخزين القيمتين
                current_colors[names[i]] = (hue_val, sat_val)

                dummy_hsv = np.uint8([[[mean[0], mean[1], mean[2]]]])
                dummy_bgr = cv2.cvtColor(dummy_hsv, cv2.COLOR_HSV2BGR)
                mean_color_bgr = (int(dummy_bgr[0][0][0]), int(dummy_bgr[0][0][1]), int(dummy_bgr[0][0][2]))

            # 4. تجهيز العرض
            def to_bgr(img):
                if len(img.shape) == 2: return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                if img.shape[2] == 4: return img[:, :, :3]
                return img

            view_crop = resize_and_pad(to_bgr(cropped), THUMB_SIZE)
            mask_vis = (mask.astype(np.uint8) * 255)
            view_mask = resize_and_pad(cv2.cvtColor(mask_vis, cv2.COLOR_GRAY2BGR), THUMB_SIZE)

            view_color = np.zeros((THUMB_SIZE, THUMB_SIZE, 3), dtype=np.uint8)
            cv2.rectangle(view_color, (0,0), (THUMB_SIZE, THUMB_SIZE), mean_color_bgr, -1)

            cv2.putText(view_color, names[i], (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
            # [NEW] عرض Hue و Saturation
            cv2.putText(
                view_color,
                f"H:{hue_val} S:{sat_val}",
                (5, THUMB_SIZE - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
            )

            row = np.hstack([view_crop, view_mask, view_color])
            rows.append(row)

        final_grid = np.vstack(rows)
        cv2.imshow(WINDOW_NAME, final_grid)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("\n" + "="*40)
            print(" انسخ هذه القيم وضعها في ملف الإعدادات:")
            print("="*40)
            print(f"OPT_CROP_Y = {crop_y_pct:.2f}")
            print(f"OPT_CROP_X = {crop_x_pct:.2f}")
            print(f"OPT_SAT = {sat_thresh}")
            print("-" * 20)
            print("# COLORS (Hue, Saturation):")
            print("BALL_COLORS = {")
            # [NEW] طباعة القيم بتنسيق Tuple (Hue, Sat)
            for name, (h, s) in current_colors.items():
                clean_name = os.path.splitext(name)[0]
                print(f"    '{clean_name}': ({h}, {s}),")
            print("}")
            print("="*40 + "\n")
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_multi_tuner()
