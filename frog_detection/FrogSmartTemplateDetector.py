import cv2
import os
import numpy as np


class FrogSmartTemplateDetector:
    def __init__(
        self,
        templates_dir,
        threshold=0.45,
        scales=None
    ):
        if scales is None:
            scales = np.linspace(0.5, 1.8, 20)

        self.threshold = threshold
        self.scales = scales
        self.templates = []

        self._load_templates(templates_dir)

        if not self.templates:
            raise RuntimeError("No frog templates loaded")

        print(f"[SMART] Loaded {len(self.templates)} frog templates")

    # -----------------------------------------
    def _load_templates(self, templates_dir):
        for file in sorted(os.listdir(templates_dir)):
            if file.lower().endswith((".png", ".jpg", ".jpeg")):
                path = os.path.join(templates_dir, file)
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue

                edges = cv2.Canny(img, 80, 160)
                self.templates.append((file, edges))

    # -----------------------------------------
    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 80, 160)

        h_frame, w_frame = gray.shape[:2]

        best_match = None
        best_score = 0

        for name, tmpl in self.templates:
            th, tw = tmpl.shape[:2]

            for scale in self.scales:
                rw = int(tw * scale)
                rh = int(th * scale)

                if rw >= w_frame or rh >= h_frame:
                    continue

                resized = cv2.resize(tmpl, (rw, rh))

                res = cv2.matchTemplate(edges, resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                if max_val > best_score and max_val >= self.threshold:
                    x, y = max_loc
                    area_ratio = (rw * rh) / (w_frame * h_frame)

                    # فلترة هندسية بسيطة
                    if 0.02 < area_ratio < 0.25:
                        best_score = max_val
                        best_match = (x, y, rw, rh)

        return best_match
