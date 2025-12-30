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
        # Pre-load ignored zones ONCE (Optimization)
        self.ignored_zones = self.load_ignored_zones()
        if self.ignored_zones:
            print(f"Loaded {len(self.ignored_zones)} ignored zones.")

    def load_assets(self, asset_folder="images_deluxe3"):
        # Optimal values from your testing
        OPT_SAT = 40
        OPT_CROP_Y = 0.20
        OPT_CROP_X = 0.20

        print(f"Loading assets...")
        
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
                print(f" - {color_name} Ready")

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
    
    def load_ignored_zones(self, filename="balls_detection/ignore_regions.py"):
        # Note: Ensure the file content is valid JSON even if extension is .py
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load ignore regions: {e}")
                return []
        return []

    def detect_from_frame(self, frame):
        """
        Processes a single frame for real-time detection.
        Returns the annotated frame.
        """
        output = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1. APPLY IGNORE MASK (Fast)
        if self.ignored_zones:
            for (x, y, w, h) in self.ignored_zones:
                # Fill ignored zones with Black (0) directly on the gray image
                cv2.rectangle(gray, (x, y), (x + w, y + h), 0, -1)
                # Visual debug: draw red box on output
                # cv2.rectangle(output, (x, y), (x + w, y + h), (0, 0, 255), 1)

        # 2. Blur
        gray = cv2.medianBlur(gray, 5)
        
        # 3. Detect Circles (Using your Tuned Values)
        circles = cv2.HoughCircles(
            gray, 
            cv2.HOUGH_GRADIENT, 
            dp=1, 
            minDist=26,      # User Tuned
            param1=56,       # User Tuned
            param2=39,       # User Tuned
            minRadius=16,    # User Tuned
            maxRadius=23     # User Tuned
        )

        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")

            for (x, y, r) in circles:
                # Boundary checks
                if y-r < 0 or x-r < 0 or y+r > frame.shape[0] or x+r > frame.shape[1]:
                    continue

                # ROI Extraction (Using r to be safe, or your hardcoded 10px)
                # Using 10px as per your logic, but clamped to image bounds
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
    """
    Takes a snapshot of the screen and lets the user draw a box.
    Returns the coordinates (top, left, width, height).
    """
    with mss.mss() as sct:
        # Get information of monitor 1
        monitor = sct.monitors[1]
        
        # Grab the screen
        sct_img = sct.grab(monitor)
        img = np.array(sct_img)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR) # Convert to OpenCV format

        print("--- SELECT REGION ---")
        print("Draw a box around the game area.")
        print("Press ENTER or SPACE to confirm.")
        print("Press c to cancel.")
        
        # Opens a GUI to draw a box
        roi = cv2.selectROI("Select Game Region", img, showCrosshair=True, fromCenter=False)
        cv2.destroyWindow("Select Game Region")
        
        # roi is (x, y, w, h)
        x, y, w, h = roi
        
        # If user cancelled (w=0 or h=0)
        if w == 0 or h == 0:
            return None
            
        # Add the monitor offset (if you have multiple screens, 'top' might not be 0)
        return {
            "top": monitor["top"] + y,
            "left": monitor["left"] + x,
            "width": w,
            "height": h
        }

if __name__ == "__main__":
    # 1. Initialize Bot and Load Assets
    bot = ZumaBot()
    bot.load_assets()

    # 2. Select Region
    region = select_game_region()
    
    if region:
        print(f"Region selected: {region}")
        print("Starting Real-Time Detection... Press 'q' to stop.")

        # 3. Real-Time Loop
        with mss.mss() as sct:
            prev_time = time.time()
            
            while True:
                # Capture only the selected region
                img = np.array(sct.grab(region))
                
                # Convert RGBA (Screen) to BGR (OpenCV)
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Run Detection
                result = bot.detect_from_frame(frame)
                
                # Calculate FPS
                curr_time = time.time()
                fps = 1 / (curr_time - prev_time)
                prev_time = curr_time
                cv2.putText(result, f"FPS: {int(fps)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                
                # Show Result
                cv2.imshow("Real-Time Zuma Bot", result)
                
                # Exit condition
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        cv2.destroyAllWindows()
    else:
        print("No region selected. Exiting.")