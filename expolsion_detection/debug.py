import cv2
import numpy as np
import os
import glob

# --- CONFIGURATION ---
# Put your actual paths here
SCREENSHOT_PATH = "./debug_screen.png"  # The screenshot you took
ASSETS_PATH = "deluxe3"                # Folder with exp_start.png, etc.

class DebugExplosionDetector:
    def __init__(self):
        self.templates = []
        self.lower_orange = np.array([10, 100, 100])
        self.upper_orange = np.array([35, 255, 255])
        self.lower_white = np.array([0, 0, 230])
        self.upper_white = np.array([180, 50, 255])
        
        # Load Templates
        files = sorted(glob.glob(os.path.join(ASSETS_PATH, "explosion*.png")))
        print(files)
        print(f"--- DEBUG STEP 1: LOADING TEMPLATES ---")
        for f in files:
            img = cv2.imread(f, cv2.IMREAD_UNCHANGED)
            if img is not None and img.shape[2] == 4:
                # Split BGR and Alpha
                base_img = img[:, :, 0:3]
                alpha_mask = img[:, :, 3]
                self.templates.append((base_img, alpha_mask))
                
                # Show the mask to verify it's correct
                cv2.imshow(f"Template Mask: {os.path.basename(f)}", alpha_mask)
                cv2.namedWindow(f"Template Mask: {os.path.basename(f)}", cv2.WINDOW_NORMAL)
                # cv2.resizeWindow(f"Template Mask: {os.path.basename(f)}", 600, 450)
                
                print(f"Loaded {os.path.basename(f)} with mask.")
            else:
                print(f"WARNING: {os.path.basename(f)} is not 4-channel (RGBA). Skipping.")
        print("---------------------------------------")
        print(self.templates)

    def debug_step_by_step(self, frame):
        
        # --- STEP 2: TEST COLOR MASKING ---
        print("\n--- DEBUG STEP 2: COLOR MASKING ---")
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        mask_orange = cv2.inRange(hsv, self.lower_orange, self.upper_orange)
        mask_white = cv2.inRange(hsv, self.lower_white, self.upper_white)
        combined_mask = cv2.bitwise_or(mask_orange, mask_white)
        
        # Show the raw mask (What the color detector sees)
        cv2.imshow("Debug: Color Mask (White = Detected)", combined_mask)
        cv2.namedWindow("Debug: Color Mask (White = Detected)", cv2.WINDOW_NORMAL)
        # cv2.resizeWindow("Debug: Color Mask (White = Detected)", 600, 450)
        
        # Count white pixels
        white_pixels = cv2.countNonZero(combined_mask)
        print(f"White Pixels found in mask: {white_pixels}")
        
        if white_pixels > (frame.shape[0] * frame.shape[1] * 0.5):
            print("CRITICAL: The Color Mask is selecting >50% of the screen! Thresholds are too loose.")

        # --- STEP 3: TEST TEMPLATE MATCHING ---
        print("\n--- DEBUG STEP 3: TEMPLATE MATCHING ---")
        output_frame = frame.copy()
        
        for i, (temp_img, temp_mask) in enumerate(self.templates):
            # Run match
            res = cv2.matchTemplate(frame, temp_img, cv2.TM_CCORR_NORMED, mask=temp_mask)
            
            # Show the "Heatmap" of where it thinks matches are
            # Brighter = Better match
            cv2.imshow(f"Debug: Match Heatmap Template {i}", res)
            cv2.namedWindow(f"Debug: Match Heatmap Template {i}", cv2.WINDOW_NORMAL)
            # cv2.resizeWindow(f"Debug: Match Heatmap Template {i}", 600, 450)
            
            threshold = 0.93
            loc = np.where(res >= threshold)
            match_count = len(loc[0])
            print(f"Template {i}: Found {match_count} matches above threshold {threshold}")
            
            # Draw rectangles for this template only
            for pt in zip(*loc[::-1]):
                h, w = temp_img.shape[:2]
                cv2.rectangle(output_frame, pt, (pt[0] + w, pt[1] + h), (0, 0, 255), 1)

        cv2.imshow("Debug: Final Result", output_frame)
        cv2.namedWindow("Debug: Final Result", cv2.WINDOW_NORMAL)
        # cv2.resizeWindow("Debug: Final Result", 600, 450)
        print("\nPress any key in the windows to close...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_PATH):
        print(f"Error: Please take a screenshot and save it as '{SCREENSHOT_PATH}'")
    else:
        frame = cv2.imread(SCREENSHOT_PATH)
        detector = DebugExplosionDetector()
        detector.debug_step_by_step(frame)