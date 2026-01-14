import cv2
import os
import numpy as np


class FrogTemplateDetector:
    def __init__(self, templates_dir, threshold=0.6):
        self.templates = []
        self.threshold = threshold

        for file in os.listdir(templates_dir):
            if file.lower().endswith((".png", ".jpg", ".jpeg")):
                path = os.path.join(templates_dir, file)
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.templates.append(img)

        if not self.templates:
            raise RuntimeError("No frog templates loaded")

        print(f"[TEMPLATE] Loaded {len(self.templates)} frog templates")

    # --------------------------------------------------
    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h_frame, w_frame = gray.shape[:2]

        best_score = 0
        best_box = None

        # Multi-scale search
        scales = np.linspace(0.5, 1.8, 14)

        for template in self.templates:
            for scale in scales:
                resized = cv2.resize(
                    template,
                    None,
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_LINEAR
                )

                h, w = resized.shape[:2]
                if h > h_frame or w > w_frame:
                    continue

                result = cv2.matchTemplate(
                    gray,
                    resized,
                    cv2.TM_CCOEFF_NORMED
                )

                _, max_val, _, max_loc = cv2.minMaxLoc(result)

                if max_val > self.threshold and max_val > best_score:
                    best_score = max_val
                    best_box = (max_loc[0], max_loc[1], w, h)

        return best_box, best_score
