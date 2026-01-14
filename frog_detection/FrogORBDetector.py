import cv2
import os
import numpy as np


class FrogORBDetector:
    def __init__(
        self,
        templates_dir,
        min_matches=15
    ):
        self.orb = cv2.ORB_create(nfeatures=1500)
        self.min_matches = min_matches

        self.templates = []
        self._load_templates(templates_dir)

        if not self.templates:
            raise RuntimeError("No ORB templates loaded")

        print(f"[ORB] Loaded {len(self.templates)} frog templates")


    def _load_templates(self, templates_dir):
        for file in os.listdir(templates_dir):
            if file.lower().endswith((".png", ".jpg", ".jpeg")):
                path = os.path.join(templates_dir, file)
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue

                kp, des = self.orb.detectAndCompute(img, None)
                if des is not None:
                    self.templates.append((file, kp, des))


    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp_frame, des_frame = self.orb.detectAndCompute(gray, None)

        if des_frame is None:
            return None

        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        h_frame, w_frame = gray.shape[:2]

        best_box = None
        best_score = 0

        for name, kp_t, des_t in self.templates:
            matches = bf.knnMatch(des_t, des_frame, k=2)

            good = []
            for m, n in matches:
                if m.distance < 0.8 * n.distance:
                    good.append(m)

            if len(good) < self.min_matches:
                continue

            src_pts = np.float32([kp_t[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp_frame[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

            if H is None:
                continue

            inliers = mask.ravel().tolist()
            if sum(inliers) < self.min_matches:
                continue

            inlier_pts = dst_pts[mask.ravel() == 1]

            x, y, w, h = cv2.boundingRect(inlier_pts)

            area_ratio = (w * h) / (w_frame * h_frame)
            aspect = w / float(h + 1e-5)

            if not (0.01 < area_ratio < 0.30):
                continue

            if not (0.6 < aspect < 1.6):
                continue

            inlier_count = sum(inliers)
            template_kp_count = len(kp_t)

            normalized_score = inlier_count / (template_kp_count + 1e-5)
            
            if not (
                inlier_count >= self.min_matches
                or normalized_score >= 0.15
            ):
                continue


            if normalized_score > best_score:
                best_score = normalized_score
                best_box = (x, y, w, h)


        return best_box

