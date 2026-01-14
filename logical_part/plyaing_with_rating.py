# game_engine.py

import cv2
import numpy as np
import time
import mss
import pyautogui
import keyboard
import math
from datetime import datetime

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
#                    إعدادات التصحيح
# ============================================================
SHOT_COOLDOWN = 1.5  # ثانية ونصف بين كل طلقة (بطيء للمراقبة)
DEBUG_MODE = True    # طباعة كل التفاصيل
shot_counter = 0     # عداد الطلقات
shot_history = []    # سجل الطلقات


def log(message, level="INFO"):
    """طباعة مع الوقت"""
    if DEBUG_MODE:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")


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


def calculate_aim_position(frog_center, target_pos, distance_from_frog=100, ratio=None):
    """
    حساب نقطة التصويب على الخط بين الضفدع والكرة
    
    Args:
        frog_center: مركز الضفدع (x, y)
        target_pos: موقع الكرة المستهدفة (x, y)
        distance_from_frog: المسافة بالبكسل من الضفدع (افتراضي: 100)
        ratio: نسبة المسافة من الضفدع (0.0-1.0) - إذا تم تحديده يتجاهل distance_from_frog
    
    Returns:
        (aim_x, aim_y): نقطة التصويب الجديدة
    """
    if frog_center is None:
        return target_pos
    
    fx, fy = frog_center
    tx, ty = target_pos
    
    # حساب المسافة الكلية
    total_distance = math.sqrt((tx - fx)**2 + (ty - fy)**2)
    
    if total_distance == 0:
        return target_pos
    
    # إذا تم تحديد نسبة معينة
    if ratio is not None:
        ratio = max(0.0, min(1.0, ratio))  # تأكد أن النسبة بين 0 و 1
    else:
        # حساب النسبة بناءً على المسافة المطلوبة
        ratio = min(distance_from_frog / total_distance, 0.95)  # لا تتجاوز 95% من المسافة
    
    # حساب النقطة الجديدة
    aim_x = fx + (tx - fx) * ratio
    aim_y = fy + (ty - fy) * ratio
    
    return (int(aim_x), int(aim_y))


def find_best_target(balls, current_ball_color, frog_center=None):
    """
    إيجاد أفضل كرة للتصويب - مع تسجيل مفصل
    """
    if not balls:
        log("No balls detected!", "WARNING")
        return None, float('-inf'), "No balls"
    
    groups = find_color_groups(balls)
    max_distance = max(b["distance"] for b in balls) if balls else 1
    
    # طباعة الألوان الموجودة
    colors_found = {}
    for b in balls:
        colors_found[b["color"]] = colors_found.get(b["color"], 0) + 1
    
    log(f"Ball colors: {colors_found}", "SCAN")
    log(f"Looking for: {current_ball_color}", "SCAN")
    log(f"Total groups: {len(groups)}", "SCAN")
    
    best_target = None
    best_score = float('-inf')
    best_reason = ""
    all_candidates = []
    
    # ═══════════════════════════════════════════
    # المرحلة 1: البحث عن اللون المطابق
    # ═══════════════════════════════════════════
    for group_idx, group in enumerate(groups):
        group_size = len(group["balls"])
        target_ball = group["balls"][0]
        target_pos = target_ball["position"]
        
        score = 0
        reasons = []
        
        # تطابق اللون
        if group["color"] == current_ball_color:
            score += 100
            reasons.append("COLOR_MATCH +100")
        else:
            # Fallback: لون مختلف
            score += 0
            reasons.append(f"FALLBACK({group['color']})")
        
        # حجم المجموعة
        if group_size >= 3:
            group_bonus = group_size * 30
            score += group_bonus
            reasons.append(f"GROUP_SIZE({group_size}) +{group_bonus}")
        elif group_size == 2:
            score += 80
            reasons.append("WILL_COMPLETE_3 +80")
        else:
            score += 20
            reasons.append("SINGLE +20")
        
        # Chain
        chain_count = check_chain_potential(groups, group_idx)
        if chain_count > 0:
            chain_bonus = chain_count * 40
            score += chain_bonus
            reasons.append(f"CHAIN({chain_count}) +{chain_bonus}")
        
        # الخطر
        avg_distance = sum(b["distance"] for b in group["balls"]) / group_size
        danger = calculate_danger_level(avg_distance, max_distance)
        
        if danger > 0.7:
            score += 200
            reasons.append("HIGH_DANGER +200")
        elif danger > 0.4:
            score += 80
            reasons.append("MED_DANGER +80")
        else:
            early_bonus = int((1 - danger) * 30)
            score += early_bonus
            reasons.append(f"EARLY +{early_bonus}")
        
        # الصعوبة
        if frog_center:
            difficulty = calculate_shot_difficulty(frog_center, target_pos, balls, target_ball)
            score -= difficulty
            if difficulty > 0:
                reasons.append(f"DIFFICULTY -{int(difficulty)}")
        
        # حفظ المرشح
        candidate = {
            "color": group["color"],
            "position": target_pos,
            "score": score,
            "reasons": reasons,
            "group_size": group_size,
            "danger": danger,
            "ball": target_ball
        }
        all_candidates.append(candidate)
        
        if score > best_score:
            best_score = score
            best_target = target_ball
            best_reason = " | ".join(reasons)
    
    # طباعة كل المرشحين
    log("=" * 60, "ANALYSIS")
    log("All candidates (sorted by score):", "ANALYSIS")
    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    for i, c in enumerate(all_candidates[:5]):  # أفضل 5 فقط
        marker = ">>>" if c["ball"] == best_target else "   "
        log(f"{marker} #{i+1} {c['color']:8} | Score: {c['score']:6.0f} | Size: {c['group_size']} | Danger: {c['danger']:.2f}", "ANALYSIS")
        log(f"       Pos: {c['position']} | Reasons: {c['reasons']}", "ANALYSIS")
    log("=" * 60, "ANALYSIS")
    
    if best_target:
        log(f"SELECTED: {best_target['color']} at {best_target['position']} with score {best_score:.0f}", "DECISION")
    else:
        log("NO TARGET FOUND!", "WARNING")
    
    return best_target, best_score, best_reason


def execute_shot(target_pos, game_offset, target_color, score, reason, frog_center=None):
    """تنفيذ التصويب مع تسجيل مفصل"""
    global shot_counter, shot_history
    
    shot_counter += 1
    
    # ═══════════════════════════════════════════════════════════
    # حساب نقطة التصويب (قريبة من الضفدع، في اتجاه الكرة)
    # ═══════════════════════════════════════════════════════════
    if frog_center:
        # الخيار 1: مسافة ثابتة من الضفدع (100 بكسل)
        adjusted_target = calculate_aim_position(frog_center, target_pos, distance_from_frog=100)
        
        # أو الخيار 2: نسبة من المسافة (30% من المسافة الكلية)
        # adjusted_target = calculate_aim_position(frog_center, target_pos, ratio=0.3)
    else:
        adjusted_target = target_pos
    
    # تحويل إلى إحداثيات الشاشة
    real_target_x = adjusted_target[0] + game_offset[0]
    real_target_y = adjusted_target[1] + game_offset[1]
    
    # تسجيل الطلقة
    shot_record = {
        "id": shot_counter,
        "time": datetime.now().strftime("%H:%M:%S"),
        "color": target_color,
        "original_target": target_pos,
        "adjusted_target": adjusted_target,
        "screen_pos": (real_target_x, real_target_y),
        "score": score,
        "reason": reason
    }
    shot_history.append(shot_record)
    
    # طباعة مفصلة
    print("\n" + "🎯" * 30)
    print(f"  SHOT #{shot_counter}")
    print(f"  Time: {shot_record['time']}")
    print(f"  Target Color: {target_color}")
    print(f"  Original Ball Position: {target_pos}")
    print(f"  Adjusted Aim Position: {adjusted_target}")
    print(f"  Screen Position: ({real_target_x}, {real_target_y})")
    print(f"  Score: {score:.0f}")
    print(f"  Reason: {reason}")
    print("🎯" * 30 + "\n")
    
    # تنفيذ التصويب على النقطة المعدلة
    pyautogui.moveTo(real_target_x, real_target_y, duration=0)
    time.sleep(0.05)
    pyautogui.click()
    
    log(f"Shot #{shot_counter} executed at adjusted position!", "SHOT")


def print_shot_history():
    """طباعة سجل كل الطلقات"""
    print("\n" + "=" * 70)
    print("SHOT HISTORY")
    print("=" * 70)
    for shot in shot_history:
        print(f"#{shot['id']:3} | {shot['time']} | {shot['color']:8} | Pos: {shot['screen_pos']} | Score: {shot['score']:.0f}")
    print("=" * 70)
    print(f"Total shots: {len(shot_history)}")
    print("=" * 70 + "\n")


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
        print(f"\n{'='*50}")
        print(f">>> Auto Shoot: {status} <<<")
        print(f">>> Shot Cooldown: {SHOT_COOLDOWN} seconds <<<")
        print(f"{'='*50}\n")

    def stop_shooting():
        global AUTO_SHOOT
        AUTO_SHOOT = False
        print("\n>>> Auto Shoot: STOPPED <<<")
        print_shot_history()

    def quit_program():
        global RUNNING, AUTO_SHOOT
        AUTO_SHOOT = False
        RUNNING = False
        print("\n>>> QUITTING PROGRAM... <<<")
        print_shot_history()

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

    window_name = "Zuma Bot - DEBUG MODE"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 700, 500)

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
                log("Path converted to Local Coordinates successfully.")
            else:
                log("Error: Could not find game window.", "ERROR")
        else:
            log("Warning: Path not detected!", "WARNING")

        capture_area = None
        last_recheck_time = 0
        RECHECK_INTERVAL = 3
        
        last_shot_time = 0

        fps = 0
        frame_count = 0
        start_time = time.time()

        game_x, game_y = 0, 0
        balls = []
        frog_box = None
        frog_center = None

        print("\n" + "=" * 60)
        print("  ZUMA BOT - DEBUG MODE")
        print("=" * 60)
        print(f"  Current Ball Color: {CURRENT_BALL_COLOR}")
        print(f"  Shot Cooldown: {SHOT_COOLDOWN} seconds")
        print(f"  Debug Mode: {DEBUG_MODE}")
        print("=" * 60)
        print("  CONTROLS:")
        print("  [S]     - Start/Stop Auto Shoot")
        print("  [Q]     - Stop Shooting + Show History")
        print("  [X/ESC] - Quit Program")
        print("=" * 60 + "\n")

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
                        time_since_last = current_time - last_shot_time
                        time_until_next = max(0, SHOT_COOLDOWN - time_since_last)
                        
                        # عرض العد التنازلي
                        cv2.putText(result, f"Next shot in: {time_until_next:.1f}s", (10, 150),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                        
                        if frog_center is None:
                            log("Frog not detected!", "WARNING")
                        if not balls:
                            log("No balls detected!", "WARNING")
                        
                        if time_since_last > SHOT_COOLDOWN:
                            if frog_center and balls:
                                log("Analyzing targets...", "SCAN")
                                best_target, score, reason = find_best_target(balls, CURRENT_BALL_COLOR, frog_center)
                                
                                if best_target:
                                    target_pos = best_target["position"]
                                    game_offset = (game_x, game_y)
                                    
                                    # إضافة الرسم البصري للتوضيح
                                    adjusted_aim = calculate_aim_position(frog_center, target_pos, distance_from_frog=100)
                                    
                                    # رسم الخط الكامل (رمادي خفيف)
                                    cv2.line(result, frog_center, target_pos, (100, 100, 100), 1)
                                    
                                    # رسم نقطة التصويب الفعلية (دائرة خضراء)
                                    cv2.circle(result, adjusted_aim, 10, (0, 255, 0), 3)
                                    cv2.line(result, frog_center, adjusted_aim, (0, 255, 255), 3)
                                    
                                    # رسم الكرة المستهدفة (دائرة حمراء)
                                    cv2.circle(result, target_pos, 20, (0, 0, 255), 2)
                                    
                                    execute_shot(target_pos, game_offset, best_target["color"], score, reason, frog_center=frog_center)
                                    last_shot_time = current_time
                    
                    # عرض الهدف المحتمل (بدون تصويب)
                    elif frog_center and balls:
                        best_target, score, reason = find_best_target(balls, CURRENT_BALL_COLOR, frog_center)
                        if best_target:
                            target_pos = best_target["position"]
                            
                            # عرض نقطة التصويب المعدلة حتى بدون التصويب
                            adjusted_aim = calculate_aim_position(frog_center, target_pos, distance_from_frog=100)
                            
                            cv2.line(result, frog_center, target_pos, (100, 100, 100), 1)
                            cv2.line(result, frog_center, adjusted_aim, (255, 255, 0), 2)
                            cv2.circle(result, adjusted_aim, 8, (255, 255, 0), 2)
                            cv2.circle(result, target_pos, 15, (255, 0, 255), 2)

                    # معلومات العرض
                    frame_count += 1
                    elapsed = time.time() - start_time
                    if elapsed > 1.0:
                        fps = frame_count / elapsed
                        frame_count = 0
                        start_time = time.time()

                    # الشريط العلوي
                    cv2.putText(result, f"FPS: {int(fps)} | Balls: {len(balls)} | Shots: {shot_counter}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    cv2.putText(result, f"Frog Ball: {CURRENT_BALL_COLOR}", (10, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 255), 1)
                    
                    status = "[S] AUTO: ON" if AUTO_SHOOT else "[S] AUTO: OFF"
                    color = (0, 255, 0) if AUTO_SHOOT else (0, 0, 255)
                    cv2.putText(result, status, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    cv2.putText(result, "[Q] Stop+History | [X] Quit", (10, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

                    cv2.imshow(window_name, result)

                except Exception as e:
                    log(f"Error: {e}", "ERROR")
                    import traceback
                    traceback.print_exc()
            else:
                blank_screen = np.zeros((300, 500, 3), dtype=np.uint8)
                cv2.putText(blank_screen, "Searching for game...", (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.imshow(window_name, blank_screen)

            cv2.waitKey(1)

        keyboard.unhook_all()
        cv2.destroyAllWindows()

    print("\nProgram ended.")
    print_shot_history()