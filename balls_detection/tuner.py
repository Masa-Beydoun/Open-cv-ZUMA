import cv2
import numpy as np
import time
import os


def tune_parameters( screenshot_path):
        frame = cv2.imread(screenshot_path)
        if frame is None: return

        cv2.namedWindow("Tuner")
        cv2.resizeWindow("Tuner", 400, 200) # تصغير نافذة العرض

        # Helper function for trackbars
        def nothing(x): pass

        # Create sliders (Name, Window, StartVal, MaxVal, Callback)
        cv2.createTrackbar("DP", "Tuner", 1, 5, nothing)
        cv2.createTrackbar("MinDist", "Tuner", 30, 100, nothing)
        cv2.createTrackbar("Param1", "Tuner", 50, 255, nothing)
        cv2.createTrackbar("Param2", "Tuner", 25, 100, nothing)
        cv2.createTrackbar("MinRad", "Tuner", 15, 50, nothing)
        cv2.createTrackbar("MaxRad", "Tuner", 28, 100, nothing)
        cv2.createTrackbar("Blur", "Tuner", 2, 10, nothing) # Will be (x*2 + 1)

        print("Tuning mode active. Press 'q' to finish and save values.")

        while True:
            # 1. Get current trackbar positions
            dp = max(1, cv2.getTrackbarPos("DP", "Tuner"))
            min_dist = max(1, cv2.getTrackbarPos("MinDist", "Tuner"))
            p1 = max(1, cv2.getTrackbarPos("Param1", "Tuner"))
            p2 = max(1, cv2.getTrackbarPos("Param2", "Tuner"))
            min_r = cv2.getTrackbarPos("MinRad", "Tuner")
            max_r = cv2.getTrackbarPos("MaxRad", "Tuner")
            blur_val = cv2.getTrackbarPos("Blur", "Tuner") * 2 + 1

            # 2. Process frame with these values
            output = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.medianBlur(gray, blur_val)
            
            circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=dp, 
                                       minDist=min_dist, param1=p1, param2=p2, 
                                       minRadius=min_r, maxRadius=max_r)

            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                for (x, y, r) in circles:
                    cv2.circle(output, (x, y), r, (0, 255, 0), 2)

            cv2.imshow("Tuner", output)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print(f"Final Values -> dp={dp}, minDist={min_dist}, p1={p1}, p2={p2}, minR={min_r}, maxR={max_r}")
                break
        
        cv2.destroyAllWindows()
        
        


if __name__ == "__main__":

    # This simulates ONE frame
    tune_parameters("balls_detection/screenshot.png")
    
    
    
import cv2
import numpy as np
import time
import json
import os
import mss

class ZumaBot:
    def __init__(self):
        self.known_colors = {}
        # Make sure this path is correct
        self.background_img = cv2.imread("images_deluxe3/bg_game_1.jpg")
        
        # --- CALIBRATION (Based on your data) ---
        # "At 690px width, the ball radius is 20px"
        self.REF_SCREEN_W = 690
        self.REF_BALL_RADIUS = 17
        self.ball_ratio = self.REF_BALL_RADIUS / self.REF_SCREEN_W
        
        self.asset_map = {
            "ball_0.png": "Purple", "ball_1.png": "Blue", "ball_2.png": "Yellow",
            "ball_3.png": "Green", "ball_4.png": "Red"
        }
        
        if self.background_img is None:
            print("Warning: Background image not found. BG Subtraction disabled.")

    def align_background(self, bg_img, target_w, target_h):
        """
        Smartly scales and centers the background image to fit the user's selection.
        """
        bg_h, bg_w = bg_img.shape[:2]
        
        # Scale to cover
        scale_w = target_w / bg_w
        scale_h = target_h / bg_h
        scale = max(scale_w, scale_h)
        
        new_w = int(bg_w * scale)
        new_h = int(bg_h * scale)
        resized_bg = cv2.resize(bg_img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Center Crop
        start_x = (new_w - target_w) // 2
        start_y = (new_h - target_h) // 2
        
        return resized_bg[start_y : start_y + target_h, start_x : start_x + target_w]

    def get_combined_mask(self, current_frame):
        h, w = current_frame.shape[:2]
        master_mask = np.ones((h, w), dtype="uint8") * 255

        # 1. Background Subtraction
        if self.background_img is not None:
            try:
                bg_aligned = self.align_background(self.background_img, w, h)
                
                # Double check size (fixes rounding errors)
                if bg_aligned.shape[:2] != (h, w):
                    bg_aligned = cv2.resize(bg_aligned, (w, h))

                diff = cv2.absdiff(current_frame, bg_aligned)
                gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                
                # Threshold & Clean
                _, diff_mask = cv2.threshold(gray_diff, 40, 255, cv2.THRESH_BINARY)
                kernel = np.ones((3,3), np.uint8)
                diff_mask = cv2.erode(diff_mask, kernel, iterations=1)
                
                master_mask = cv2.bitwise_and(master_mask, diff_mask)
            except Exception as e:
                pass # Fail silently and use full mask if BG fails

        # 2. Ignored Zones (Safety check included)
        ignored_zones = self.load_ignored_zones()
        for (x, y, rect_w, rect_h) in ignored_zones:
            if x + rect_w <= w and y + rect_h <= h:
                cv2.rectangle(master_mask, (x, y), (x + rect_w, y + rect_h), 0, -1)

        return master_mask

    def load_assets(self, asset_folder="images_deluxe3"):
        # Your optimized asset loading logic
        OPT_SAT = 40; OPT_CROP_Y = 0.20; OPT_CROP_X = 0.20
        print(f"Loading assets...")
        
        for filename, color_name in self.asset_map.items():
            path = os.path.join(asset_folder, filename)
            image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if image is None: continue
            
            h, w = image.shape[:2]
            image = image[int(h*OPT_CROP_Y):h, 0:int(w*(1-OPT_CROP_X))]
            
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
                print(f" - {color_name} ready")

    def identify_color(self, roi):
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mean_hsv = cv2.mean(hsv_roi)
        hue = mean_hsv[0]
        
        best_match, min_diff = None, 999
        for color_name, (known_hue, known_sat) in self.known_colors.items():
            diff = abs(hue - known_hue)
            if diff > 90: diff = 180 - diff
            if diff < min_diff:
                min_diff, best_match = diff, color_name
                
        if min_diff > 20: return None
        return best_match

    def load_ignored_zones(self, filename="ignored_zones.json"):
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f: return json.load(f)
            except: return []
        return []

    def detect_from_frame(self, frame):
        if frame is None: return frame
        h_curr, w_curr = frame.shape[:2]

        # --- DYNAMIC SCALING ---
        target_radius = int(w_curr * self.ball_ratio)
        min_r = max(1, int(target_radius * 0.7))
        max_r = max(1, int(target_radius * 1.3))
        min_dist = max(1, int(target_radius * 1.8)) 

        output = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Get Mask & Apply
        combined_mask = self.get_combined_mask(frame)
        gray_masked = cv2.bitwise_and(gray, gray, mask=combined_mask)
        gray_masked = cv2.medianBlur(gray_masked, 5)
        
        circles = cv2.HoughCircles(
            gray_masked, cv2.HOUGH_GRADIENT, dp=1, 
            minDist=min_dist, param1=50, param2=25, 
            minRadius=min_r, maxRadius=max_r
        )

        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                if y-r < 0 or x-r < 0 or y+r > h_curr or x+r > w_curr: continue
                
                offset = int(r * 0.6)
                roi = frame[y-offset : y+offset, x-offset : x+offset]
                if roi.size == 0: continue
                
                color_name = self.identify_color(roi)
                if color_name:
                    cv2.circle(output, (x, y), r, (0, 255, 0), 2)
                    cv2.putText(output, color_name, (x - 10, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        return output

def select_game_region():
    """ Let user manually draw the game box on the screen """
    with mss.mss() as sct:
        # Grab the full screen of monitor 1
        monitor_full = sct.monitors[1]
        screenshot = np.array(sct.grab(monitor_full))
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
        
        print("Select the Game Region and press ENTER. Press 'c' to cancel.")
        # cv2.selectROI allows you to draw a box with your mouse
        r = cv2.selectROI("Select Game Region", screenshot, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow("Select Game Region")
        
        # r is (x, y, w, h)
        if r[2] == 0 or r[3] == 0: return None # User cancelled
        
        # Adjust for multiple monitors if necessary (mss handles this, but be careful of offsets)
        # For simplicity, we assume the ROI is relative to the monitor we captured.
        return {"top": monitor_full["top"] + int(r[1]), 
                "left": monitor_full["left"] + int(r[0]), 
                "width": int(r[2]), 
                "height": int(r[3])}

if __name__ == "__main__":
    bot = ZumaBot()
    bot.load_assets()
    
    # 1. Select Region
    time.sleep(2) # Give you time to switch windows

    region = select_game_region()
    
    if region:
        print(f"Region Selected: {region}")
        print("Starting Bot... Press 'q' to stop.")
        
        with mss.mss() as sct:
            while True:
                # 2. Capture ONLY the selected region (Very fast)
                img = np.array(sct.grab(region))
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # 3. Detect
                output = bot.detect_from_frame(frame)
                
                # 4. Show Result
                cv2.imshow("Zuma Bot (Running)", output)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    else:
        print("No region selected.")

    cv2.destroyAllWindows()