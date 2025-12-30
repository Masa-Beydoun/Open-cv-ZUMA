import cv2
import json
import os

class RegionTuner:
    def __init__(self, screenshot_path):
        self.image = cv2.imread(screenshot_path)
        if self.image is None:
            print(f"Error: Could not load {screenshot_path}")
            return
        
        self.window_name = "Region Tuner - Press S to Save"
        self.ignored_regions = []
        self.start_point = None
        self.current_point = None
        self.drawing = False

    def select_regions(self):
        # Fix: Use WINDOW_AUTOSIZE or WINDOW_NORMAL to prevent coordinate drift
        cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(self.window_name, self.mouse_handler)

        print("--- Region Tuner ---")
        print("1. Click and drag to draw Red rectangles over the Frog/UI.")
        print("2. Press 'S' to save and exit.")
        print("3. Press 'C' to clear.")
        
        while True:
            display = self.image.copy()
            
            # Draw finalized regions
            for (x, y, w, h) in self.ignored_regions:
                cv2.rectangle(display, (x, y), (x + w, y + h), (0, 0, 255), 2)

            # Draw the active rectangle while dragging
            if self.drawing and self.start_point and self.current_point:
                cv2.rectangle(display, self.start_point, self.current_point, (0, 255, 0), 1)

            cv2.imshow(self.window_name, display)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('s'):
                self.save_regions()
                break
            elif key == ord('c'):
                self.ignored_regions = []

        cv2.destroyAllWindows()

    def mouse_handler(self, event, x, y, flags, param):
        # Event: Press Down
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
            self.current_point = (x, y)

        # Event: Moving Mouse
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing:
                self.current_point = (x, y)

        # Event: Release Button
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            x_start, y_start = self.start_point
            
            # Calculate width and height correctly regardless of drag direction
            final_x = min(x_start, x)
            final_y = min(y_start, y)
            final_w = abs(x_start - x)
            final_h = abs(y_start - y)
            
            if final_w > 5 and final_h > 5: # Ignore tiny accidental clicks
                self.ignored_regions.append((final_x, final_y, final_w, final_h))

    def save_regions(self, filename="ignored_zones.json"):
        with open(filename, 'w') as f:
            json.dump(self.ignored_regions, f)
        print(f"Successfully saved regions to {filename}.")
# Usage
if __name__ == "__main__":
    tuner = RegionTuner("balls_detection/screenshot.png")
    tuner.select_regions()