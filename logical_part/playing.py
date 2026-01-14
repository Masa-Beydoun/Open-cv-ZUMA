# game_engine.py

import cv2
import numpy as np
import time
import mss
import pyautogui
import keyboard
import math

try:
    from roi.detect_roi import analyze_game_screen
    from balls_detection.ignored_zone_manager import IgnoredZonesManager
    from balls_detection.detect_balls import ZumaBot
    from frog_detection.ZumaFrogDetector import ZumaFrogDetector
    from path_detection.capture_game_path import capture_game_path
    from path_detection.path_detection import (
        ZUMA_GREEN_JUNGLE_CONFIG,
        ZUMA_SPACE_CONFIG,
        ZUMA_DELUXE_CONFIG,
    )
    from constants import *
except ImportError:
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from roi.detect_roi import analyze_game_screen
    from balls_detection.ignored_zone_manager import IgnoredZonesManager
    from balls_detection.detect_balls import ZumaBot
    from frog_detection.ZumaFrogDetector import ZumaFrogDetector
    from path_detection.capture_game_path import capture_game_path
    from path_detection.path_detection import (
        ZUMA_GREEN_JUNGLE_CONFIG,
        ZUMA_SPACE_CONFIG,
        ZUMA_DELUXE_CONFIG,
    )
    from constants import *


pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True


# ============================================================
#                    دوال تحليل الكرات
# ============================================================

def find_color_groups(balls):
    if not balls:
        return []
    
    groups = []
    current_group = {
        "color": balls[0]["color"],
        "balls": [balls[0]],
        "start_idx": 0,
        "end_idx": 0
    }
    
    for i in range(1, len(balls)):
        if balls[i]["color"] == current_group["color"]:
            current_group["balls"].append(balls[i])
            current_group["end_idx"] = i
        else:
            groups.append(current_group)
            current_group = {
                "color": balls[i]["color"],
                "balls": [balls[i]],
                "start_idx": i,
                "end_idx": i
            }
    
    groups.append(current_group)
    return groups


def check_chain_potential(groups, group_idx):
    if group_idx <= 0 or group_idx >= len(groups) - 1:
        return 0
    
    before_group = groups[group_idx - 1]
    after_group = groups[group_idx + 1]
    
    if before_group["color"] == after_group["color"]:
        combined_count = len(before_group["balls"]) + len(after_group["balls"])
        if combined_count >= 3:
            return combined_count
    
    return 0


def calculate_danger_level(ball_distance, max_distance):
    if max_distance == 0:
        return 0
    
    progress = 1 - (ball_distance / max_distance)
    
    if progress < 0.5:
        return 0
    elif progress < 0.7:
        return (progress - 0.5) * 1.5
    elif progress < 0.85:
        return 0.3 + (progress - 0.7) * 2
    else:
        return 0.6 + (progress - 0.85) * 2.67


def calculate_shot_difficulty(frog_center, target_pos, all_balls, target_ball):
    if frog_center is None:
        return 0
    
    fx, fy = frog_center
    tx, ty = target_pos
    
    distance = math.sqrt((tx - fx)**2 + (ty - fy)**2)
    distance_penalty = min(distance / 500, 1) * 20
    
    obstacles = 0
    for ball in all_balls:
        if ball == target_ball:
            continue
        bx, by = ball["position"]
        line_dist = point_to_line_distance(bx, by, fx, fy, tx, ty)
        if line_dist < ball["radius"] * 2:
            obstacles += 1
    
    obstacle_penalty = obstacles * 15
    
    return distance_penalty + obstacle_penalty


def point_to_line_distance(px, py, x1, y1, x2, y2):
    num = abs((y2-y1)*px - (x2-x1)*py + x2*y1 - y2*x1)
    den = math.sqrt((y2-y1)**2 + (x2-x1)**2)
    if den == 0:
        return float('inf')
    return num / den


def find_best_target(balls, current_ball_color, frog_center=None):
    """
    إيجاد أفضل كرة للتصويب - مع Fallback إذا ما لقى اللون
    """
    if not balls:
        print("[DEBUG] No balls detected!")
        return None, float('-inf')
    
    groups = find_color_groups(balls)
    max_distance = max(b["distance"] for b in balls) if balls else 1
    
    # طباعة الألوان الموجودة
    colors_found = set(b["color"] for b in balls)
    print(f"[DEBUG] Colors found: {colors_found} | Looking for: {current_ball_color}")
    
    best_target = None
    best_score = float('-inf')
    best_reason = ""
    
    # ═══════════════════════════════════════════
    # المرحلة 1: البحث عن اللون المطابق
    # ═══════════════════════════════════════════
    for group_idx, group in enumerate(groups):
        if group["color"] != current_ball_color:
            continue
        
        group_size = len(group["balls"])
        target_ball = group["balls"][0]
        target_pos = target_ball["position"]
        
        score = 0
        reasons = []
        
        # تطابق اللون
        score += 100  # مكافأة كبيرة لتطابق اللون
        reasons.append("COLOR MATCH +100")
        
        # حجم المجموعة
        if group_size >= 3:
            group_bonus = group_size * 30
            score += group_bonus
            reasons.append(f"Group({group_size}) +{group_bonus}")
        elif group_size == 2:
            score += 80
            reasons.append("Complete3 +80")
        else:
            score += 20
            reasons.append("Single +20")
        
        # Chain
        chain_count = check_chain_potential(groups, group_idx)
        if chain_count > 0:
            chain_bonus = chain_count * 40
            score += chain_bonus
            reasons.append(f"Chain({chain_count}) +{chain_bonus}")
        
        # الخطر
        avg_distance = sum(b["distance"] for b in group["balls"]) / group_size
        danger = calculate_danger_level(avg_distance, max_distance)
        
        if danger > 0.7:
            score += 200
            reasons.append("DANGER! +200")
        elif danger > 0.4:
            score += 80
            reasons.append("MedDanger +80")
        else:
            early_bonus = int((1 - danger) * 30)
            score += early_bonus
            reasons.append(f"Early +{early_bonus}")
        
        # الصعوبة
        if frog_center:
            difficulty = calculate_shot_difficulty(frog_center, target_pos, balls, target_ball)
            score -= difficulty
            if difficulty > 0:
                reasons.append(f"Diff -{int(difficulty)}")
        
        if score > best_score:
            best_score = score
            best_target = target_ball
            best_reason = " | ".join(reasons)
    
    # ═══════════════════════════════════════════
    # المرحلة 2: Fallback - إذا ما لقينا اللون المطلوب
    # ═══════════════════════════════════════════
    if best_target is None:
        print(f"[DEBUG] No {current_ball_color} found! Using FALLBACK...")
        
        for group_idx, group in enumerate(groups):
            group_size = len(group["balls"])
            target_ball = group["balls"][0]
            target_pos = target_ball["position"]
            
            score = 0
            reasons = [f"Fallback({group['color']})"]
            
            # بدون مكافأة تطابق اللون
            
            # حجم المجموعة
            if group_size >= 2:
                group_bonus = group_size * 20
                score += group_bonus
                reasons.append(f"Group({group_size}) +{group_bonus}")
            
            # الخطر (أهم شي في الـ Fallback)
            avg_distance = sum(b["distance"] for b in group["balls"]) / group_size
            danger = calculate_danger_level(avg_distance, max_distance)
            
            if danger > 0.7:
                score += 300  # أولوية قصوى للخطر
                reasons.append("DANGER! +300")
            elif danger > 0.4:
                score += 100
                reasons.append("MedDanger +100")
            else:
                score += 10
            
            if score > best_score:
                best_score = score
                best_target = target_ball
                best_reason = " | ".join(reasons)
    
    # طباعة النتيجة
    if best_target:
        print(f"[TARGET] {best_target['color']} @ dist={best_target['distance']} | Score: {best_score:.0f}")
        print(f"  → {best_reason}")
    else:
        print("[DEBUG] NO TARGET FOUND AT ALL!")
    
    return best_target, best_score


def execute_shot(target_pos, game_offset):
    real_target_x = target_pos[0] + game_offset[0]
    real_target_y = target_pos[1] + game_offset[1]

    pyautogui.moveTo(real_target_x, real_target_y, duration=0)
    time.sleep(0.05)
    pyautogui.click()
    print(f"[SHOT] Fired at ({real_target_x}, {real_target_y})")


# ============================================================
#                    الحلقة الرئيسية
# ============================================================
if __name__ == "__main__":

    SELECTED_CONFIG = Deluxe3
    PATH_CONFIG = ZUMA_DELUXE_CONFIG
    
    CURRENT_BALL_COLOR = "PURPLE"
    AUTO_SHOOT = False
    RUNNING = True

    def toggle_shoot():
        global AUTO_SHOOT
        AUTO_SHOOT = not AUTO_SHOOT
        status = "ON" if AUTO_SHOOT else "OFF"
        print(f"\n{'='*40}")
        print(f">>> Auto Shoot: {status} <<<")
        print(f"{'='*40}\n")

    def stop_shooting():
        global AUTO_SHOOT
        AUTO_SHOOT = False
        print("\n>>> Auto Shoot: STOPPED <<<\n")

    def quit_program():
        global RUNNING, AUTO_SHOOT
        AUTO_SHOOT = False
        RUNNING = False
        print("\n>>> QUITTING PROGRAM... <<<\n")

    keyboard.add_hotkey('s', toggle_shoot)
    keyboard.add_hotkey('q', stop_shooting)
    keyboard.add_hotkey('x', quit_program)
    keyboard.add_hotkey('esc', quit_program)

    zone_manager = IgnoredZonesManager("ignored_zones.json")
    ignored_zones = None

    bot = ZumaBot(SELECTED_CONFIG)
    frog_detector = None

    local_path_points = None
    cached_path_mask = None
    cached_path_points = None

    window_name = "Zuma Bot - Combined"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 600, 450)

    with mss.mss() as sct:
        full_monitor = sct.monitors[MONITOR]
        global_path_points, raw_mask = capture_game_path(PATH_CONFIG)

        if global_path_points is not None:
            temp_screen = np.array(sct.grab(full_monitor))
            temp_frame = cv2.cvtColor(temp_screen, cv2.COLOR_BGRA2BGR)
            region = analyze_game_screen(temp_frame)

            if region:
                capture_x, capture_y = region.x, region.y
                local_path_points = [
                    (gx - capture_x, gy - capture_y)
                    for gx, gy in global_path_points
                ]
                cached_path_mask = raw_mask
                cached_path_points = local_path_points
                print("Path converted to Local Coordinates successfully.")
            else:
                print("Error: Could not find game window.")
        else:
            print("Warning: Path not detected!")

        capture_area = None
        last_recheck_time = 0
        RECHECK_INTERVAL = 3
        
        last_shot_time = 0
        SHOT_COOLDOWN = 0.4

        fps = 0
        frame_count = 0
        start_time = time.time()

        game_x, game_y = 0, 0
        balls = []
        frog_box = None
        frog_center = None

        print("=" * 50)
        print("Starting Main Loop...")
        print(f"Current Ball Color: {CURRENT_BALL_COLOR}")
        print("=" * 50)
        print("GLOBAL HOTKEYS:")
        print("  [S]     - Toggle Auto Shoot ON/OFF")
        print("  [Q]     - Stop Shooting (keep running)")
        print("  [X/ESC] - Quit Program")
        print("=" * 50)

        while RUNNING:
            loop_start = time.time()

            if loop_start - last_recheck_time > RECHECK_INTERVAL:
                full_screenshot = np.array(sct.grab(full_monitor))
                full_screenshot_bgr = cv2.cvtColor(full_screenshot, cv2.COLOR_BGRA2BGR)
                new_region_data = analyze_game_screen(full_screenshot_bgr)

                if new_region_data:
                    game_x = new_region_data.x
                    game_y = new_region_data.y

                    capture_area = new_region_data.to_mss_dict(
                        full_monitor["left"], full_monitor["top"]
                    )

                    if global_path_points:
                        local_points = [
                            (gx - game_x, gy - game_y)
                            for gx, gy in global_path_points
                        ]
                        cached_path_points = local_points
                        cached_path_mask = raw_mask

                last_recheck_time = loop_start

            if capture_area:
                try:
                    sct_img = sct.grab(capture_area)
                    frame = np.array(sct_img)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                    if frog_detector is None:
                        h, w = frame.shape[:2]
                        frog_detector = ZumaFrogDetector(w, h)

                    result, balls = bot.detect_from_frame(
                        frame,
                        ignored_zones=ignored_zones,
                        path_points=cached_path_points,
                    )

                    if cached_path_points:
                        pts = np.array(cached_path_points, np.int32)
                        pts = pts.reshape((-1, 1, 2))
                        cv2.polylines(result, [pts], False, (0, 255, 0), 1)

                    frog_box = frog_detector.detect(frame)

                    if frog_box:
                        x, y, fw, fh = frog_box
                        frog_center = (x + fw // 2, y + fh // 2)
                        
                        cv2.rectangle(result, (x, y), (x + fw, y + fh), (0, 255, 0), 2)
                        cv2.putText(result, "FROG", (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        cv2.circle(result, frog_center, 5, (0, 0, 255), -1)
                    else:
                        frog_center = None

                    # ═══════════════════════════════════════════
                    # التصويب التلقائي
                    # ═══════════════════════════════════════════
                    if AUTO_SHOOT:
                        current_time = time.time()
                        
                        # Debug
                        if frog_center is None:
                            print("[DEBUG] Frog not detected!")
                        if not balls:
                            print("[DEBUG] No balls detected!")
                        
                        if current_time - last_shot_time > SHOT_COOLDOWN:
                            if frog_center and balls:
                                best_target, score = find_best_target(balls, CURRENT_BALL_COLOR, frog_center)
                                
                                # نصوب حتى لو السكور منخفض (لكن موجب)
                                if best_target:
                                    target_pos = best_target["position"]
                                    game_offset = (game_x, game_y)
                                    
                                    cv2.line(result, frog_center, target_pos, (0, 255, 255), 2)
                                    cv2.circle(result, target_pos, 15, (0, 0, 255), 3)
                                    
                                    execute_shot(target_pos, game_offset)
                                    last_shot_time = current_time
                    
                    # عرض الهدف المحتمل (بدون تصويب)
                    elif frog_center and balls:
                        best_target, score = find_best_target(balls, CURRENT_BALL_COLOR, frog_center)
                        if best_target:
                            target_pos = best_target["position"]
                            cv2.line(result, frog_center, target_pos, (255, 255, 0), 2)
                            cv2.circle(result, target_pos, 10, (255, 0, 255), 2)
                            cv2.putText(result, f"Target: {best_target['color']} S:{score:.0f}", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

                    frame_count += 1
                    elapsed = time.time() - start_time
                    if elapsed > 1.0:
                        fps = frame_count / elapsed
                        frame_count = 0
                        start_time = time.time()

                    cv2.putText(result, f"FPS: {int(fps)} | Balls: {len(balls)}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    status = "[S] AUTO: ON" if AUTO_SHOOT else "[S] AUTO: OFF"
                    color = (0, 255, 0) if AUTO_SHOOT else (0, 0, 255)
                    cv2.putText(result, status, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    cv2.putText(result, "[Q] Stop | [X] Quit", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

                    cv2.imshow(window_name, result)

                except Exception as e:
                    print(f"Error: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                blank_screen = np.zeros((300, 500, 3), dtype=np.uint8)
                cv2.putText(blank_screen, "Searching...", (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                cv2.imshow(window_name, blank_screen)

            cv2.waitKey(1)

        keyboard.unhook_all()
        cv2.destroyAllWindows()

    print("Program ended.")