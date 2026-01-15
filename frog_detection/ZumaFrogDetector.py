import cv2
import numpy as np


class ZumaFrogDetector:
    def __init__(self, frame_width, frame_height):
        self.w = frame_width
        self.h = frame_height

        self.center_roi_ratio = 0.75

        self.lower_green = np.array([70, 128, 102])
        self.upper_green = np.array([84, 245, 215])

        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (5, 5)
        )

    def _center_roi(self, frame):
        cx, cy = self.w // 2, self.h // 2
        rw = int(self.w * self.center_roi_ratio)
        rh = int(self.h * self.center_roi_ratio)

        x1 = max(cx - rw // 2, 0)
        y1 = max(cy - rh // 2, 0)
        x2 = min(cx + rw // 2, self.w)
        y2 = min(cy + rh // 2, self.h)

        return frame[y1:y2, x1:x2], (x1, y1)

    def _green_mask(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        mask = cv2.inRange(
            hsv, self.lower_green, self.upper_green
        )

        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel)

        return mask

    def _is_frog_blob(self, cnt, roi_area, roi_shape):
        area = cv2.contourArea(cnt)
        if area < 0.003 * roi_area:
            return False

        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0:
            return False

        solidity = area / hull_area
        if not (0.60 < solidity < 0.88):
            return False

        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            return False

        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity > 0.75:
            return False

        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / h
        if not (0.75 < aspect < 1.35):
            return False

        roi_h, roi_w = roi_shape[:2]
        cx = x + w / 2
        cy = y + h / 2

        dist = np.hypot(cx - roi_w / 2, cy - roi_h / 2)
        if dist > 0.30 * min(roi_w, roi_h):
            return False

        return True

    def detect(self, frame, debug=True):

        roi, (ox, oy) = self._center_roi(frame)
        """ roi = frame
        ox, oy = 0, 0 """

        mask = self._green_mask(roi)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        best = None
        best_area = 0

        roi_area = roi.shape[0] * roi.shape[1]

        for cnt in contours:
            if not self._is_frog_blob(cnt, roi_area, roi.shape):
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)

            if area > best_area:
                best_area = area
                best = (x + ox, y + oy, w, h)

        return best
