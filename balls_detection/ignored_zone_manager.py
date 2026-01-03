
import json
import os

import cv2


class IgnoredZonesManager:
    def __init__(self, filename="ignored_zones.json"):
        self.filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        self.zones = []
        self.drawing = False
        self.ix, self.iy = -1, -1
        self.current_rect = None

    def load_zones(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.zones = json.load(f)
                print(f"✅ Loaded {len(self.zones)} ignored zones.")
                return self.zones
            except:
                return []
        return []

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.ix, self.iy = x, y
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing:
                self.current_rect = (self.ix, self.iy, x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            x_start, x_end = sorted([self.ix, x])
            y_start, y_end = sorted([self.iy, y])
            w, h = x_end - x_start, y_end - y_start
            if w > 5 and h > 5:
                self.zones.append([x_start, y_start, w, h])
            self.current_rect = None

    def select_zones(self, img):
        print(">> وضع الرسم: ارسم مستطيلات حول المناطق غير المهمة. اضغط Enter للحفظ.")
        cv2.namedWindow("Select Ignored Zones")
        cv2.setMouseCallback("Select Ignored Zones", self.mouse_callback)
        
        clone = img.copy()
        while True:
            display_img = clone.copy()
            for (x, y, w, h) in self.zones:
                cv2.rectangle(display_img, (x, y), (x+w, y+h), (0, 0, 255), -1)
            
            if self.current_rect:
                cv2.rectangle(display_img, (self.current_rect[0], self.current_rect[1]), 
                              (self.current_rect[2], self.current_rect[3]), (0, 255, 0), 2)
            
            cv2.addWeighted(display_img, 0.4, clone, 0.6, 0, display_img)
            cv2.imshow("Select Ignored Zones", display_img)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 13: # Enter
                break
            elif key == ord('c'): # Clear
                self.zones = []
            elif key == ord('z') and self.zones: # Undo
                self.zones.pop()
        
        cv2.destroyWindow("Select Ignored Zones")
        with open(self.filename, 'w') as f:
            json.dump(self.zones, f)
        return self.zones
       