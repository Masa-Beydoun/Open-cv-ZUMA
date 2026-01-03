import cv2
import numpy as np
import time
import json
import os
import mss

class ZumaBot:
    def __init__(self):
        self.known_colors = {}
        self.asset_map = {
            "ball_0.png": "Purple",
            "ball_1.png": "Blue",
            "ball_2.png": "Yellow",
            "ball_3.png": "Green",
            "ball_4.png": "Red"
        }

        self.ignored_zones = self.load_ignored_zones()
    

    def load_assets(self, asset_folder="images_deluxe3"):

        OPT_SAT = 40
        OPT_CROP_Y = 0.20
        OPT_CROP_X = 0.20
        
        for filename, color_name in self.asset_map.items():
            path = os.path.join(asset_folder, filename)
            image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if image is None: continue
            
            h, w = image.shape[:2]
            y_start = int(h * OPT_CROP_Y)
            x_end = int(w * (1 - OPT_CROP_X))
            image = image[y_start:h, 0:x_end]
            
            if image.shape[2] == 4:
                bgr = image[:, :, :3]
                alpha = image[:, :, 3]
                hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
                mask = (alpha > 0) & (hsv[:, :, 1] > OPT_SAT)
            else:
                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                mask = hsv[:, :, 1] > OPT_SAT

            if np.count_nonzero(mask) > 0:
                mean_color = cv2.mean(hsv, mask=mask.astype(np.uint8))
                self.known_colors[color_name] = (mean_color[0], mean_color[1])

    def identify_color(self, roi):
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mean_hsv = cv2.mean(hsv_roi)
        hue = mean_hsv[0]
        
        best_match = None
        min_diff = 999
        
        for color_name, (known_hue, known_sat) in self.known_colors.items():
            diff = abs(hue - known_hue)
            if diff > 90: diff = 180 - diff
            if diff < min_diff:
                min_diff = diff
                best_match = color_name
                
        if min_diff > 20: return None 
        return best_match
    
    def load_ignored_zones(self, filename="balls_detection\ignored_zones.json"):
        
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load ignore regions: {e}")
                return []
        return []

    def detect_from_frame(self, frame):

        output = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.ignored_zones:
            for (x, y, w, h) in self.ignored_zones:
                cv2.rectangle(gray, (x, y), (x + w, y + h), 0, -1)
                

        gray = cv2.medianBlur(gray, 5)
        
        
        
        circles = cv2.HoughCircles(
            gray, 
            cv2.HOUGH_GRADIENT, 
            dp=1, 
            minDist=26,      
            param1=56,       
            param2=39,       
            minRadius=16,    
            maxRadius=23     
        )

        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")

            for (x, y, r) in circles:
                if y-r < 0 or x-r < 0 or y+r > frame.shape[0] or x+r > frame.shape[1]:
                    continue

                y1, y2 = max(0, y-10), min(frame.shape[0], y+10)
                x1, x2 = max(0, x-10), min(frame.shape[1], x+10)
                roi = frame[y1:y2, x1:x2]
                
                if roi.size == 0: continue

                color_name = self.identify_color(roi)
                
                if color_name:
                    cv2.circle(output, (x, y), r, (0, 255, 0), 2)
                    cv2.putText(output, color_name, (x - 20, y - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return output

def select_game_region():
    
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        
        sct_img = sct.grab(monitor)
        img = np.array(sct_img)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        roi = cv2.selectROI("Select Game Region", img, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow("Select Game Region")
        
        x, y, w, h = roi
        
        if w == 0 or h == 0:
            return None
            
        return {
            "top": monitor["top"] + y,
            "left": monitor["left"] + x,
            "width": w,
            "height": h
        }
if __name__ == "__main__":
    bot = ZumaBot()
    bot.load_assets()

    region = select_game_region()
    print(region)
    
    if region:
        with mss.mss() as sct:
            prev_time = time.time()
            
            while True:
                 
                img = np.array(sct.grab(region))
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                result = bot.detect_from_frame(frame)
                
                cv2.imshow("Zuma Bot Detection", result)
                 
                current_time = time.time()
                fps = 1 / (current_time - prev_time)
                prev_time = current_time
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
            cv2.destroyAllWindows()
    else:
        print("No region selected. Exiting.")