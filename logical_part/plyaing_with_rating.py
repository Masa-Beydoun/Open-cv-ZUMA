# game_engine.py

import cv2
import numpy as np
import time
import mss
import pyautogui
import keyboard
import math
from datetime import datetime

import ctypes

# هذا السطر يخبر الويندوز أن التطبيق واعي للأبعاد الحقيقية (DPI Aware)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

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


# إعدادات المنطقة المحظورة (الزاوية العليا اليمنى)
# هذه النسب تقريبية بناءً على صور Zuma Deluxe 3
IGNORED_ZONE_CONFIG = {
    "rel_x": 0.82,  # تبدأ من 82% من عرض اللعبة (باتجاه اليمين)
    "rel_y": 0.0,  # تبدأ من أعلى اللعبة (0%)
    "rel_w": 0.18,  # تغطي 18% من العرض المتبقي
    "rel_h": 0.15,  # تغطي 15% من الارتفاع (لتشمل الأزرار الثلاثة)
}


pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

# ==========================================
# إعدادات المنطقة المحظورة (الزاوية العليا اليمنى)
# ==========================================
FORBIDDEN_WIDTH = 330  # عرض المنطقة المحظورة (بالبكسل) من جهة اليمين
FORBIDDEN_HEIGHT = 110  # ارتفاع المنطقة المحظورة (بالبكسل) من الأعلى

BALL_OFFSET_FACTOR = 0.552  # النسبة التي حصلت عليها (0.5522)
SAMPLE_RADIUS_RATIO = 0.03  # حجم دائرة الفحص كنسبة من عرض الضفدع (للدقة)

# إعداد حركة الخطف (يمكنك تركها ثابتة أو جعلها نسبية أيضاً)
FLICK_CHECK_OFFSET = (0, -200)


def active_color_check(sct, monitor, initial_frog_box, game_offset, color_config):
    gx, gy = game_offset

    # استخدام مكان الضفدع الأولي
    fx, fy, fw, fh = initial_frog_box
    cx = fx + fw // 2
    cy = fy + fh // 2

    # === [تعديل هام] حركة الماوس ===
    target_mouse_x = gx + cx

    # المشكلة كانت هنا: كنا نستخدم monitor["top"] وهذا يخرج الماوس للمتصفح
    # الحل: نستخدم gy (بداية اللعبة) + هامش بسيط (مثلا 5 بكسل) لضمان البقاء داخل اللعبة
    top_limit = gy + 5
    target_mouse_y = max(top_limit, gy + cy - 300)

    # Clamping (حماية إضافية)
    target_mouse_x = max(0, min(target_mouse_x, monitor["width"] - 1))
    target_mouse_y = max(0, min(target_mouse_y, monitor["height"] - 1))

    # تحريك الماوس
    pyautogui.moveTo(target_mouse_x, target_mouse_y, duration=0.1)

    # انتظار للدوران
    time.sleep(0.15)

    # === إعادة اكتشاف الضفدع (Re-detect) ===
    search_margin = 80  # تقليل الهامش قليلاً للسرعة
    search_x = max(0, int(fx - search_margin))
    search_y = max(0, int(fy - search_margin))
    search_w = int(fw + search_margin * 2)
    search_h = int(fh + search_margin * 2)

    global_search_area = {
        "top": int(gy + search_y),
        "left": int(gx + search_x),
        "width": search_w,
        "height": search_h,
    }

    try:
        new_img = np.array(sct.grab(global_search_area))
        new_frame = cv2.cvtColor(new_img, cv2.COLOR_BGRA2BGR)

        h_new, w_new = new_frame.shape[:2]
        detector = ZumaFrogDetector(w_new, h_new)
        new_frog_box = detector.detect(new_frame)

        if not new_frog_box:
            return None, None, None

        nfx, nfy, nfw, nfh = new_frog_box
        real_cx = search_x + nfx + nfw // 2
        real_cy = search_y + nfy + nfh // 2

        # الحسابات
        dynamic_offset_y = int(nfh * BALL_OFFSET_FACTOR)
        dynamic_radius = int(nfw * SAMPLE_RADIUS_RATIO)
        dynamic_radius = max(2, dynamic_radius)

        ball_global_x = int(gx + real_cx)
        ball_global_y = int(gy + real_cy - dynamic_offset_y)

        sample_point_global = (ball_global_x, ball_global_y)

        # الفحص
        grab_area = {
            "top": int(ball_global_y - dynamic_radius),
            "left": int(ball_global_x - dynamic_radius),
            "width": dynamic_radius * 2,
            "height": dynamic_radius * 2,
        }

        sample_img = np.array(sct.grab(grab_area))
        sample_bgr = cv2.cvtColor(sample_img, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(sample_bgr, cv2.COLOR_BGR2HSV)
        hue = cv2.mean(hsv)[0]

        best_match = None
        min_diff = 999

        for color_name, (known_hue, known_sat) in color_config.items():
            diff = abs(hue - known_hue)
            if diff > 90:
                diff = 180 - diff
            if diff < min_diff:
                min_diff = diff
                best_match = color_name

        if best_match == "Green":
            # طباعة للتوضيح في التيرمينال
            if DEBUG_MODE:
                print(f"DEBUG: Rejected Green. Hue: {hue:.1f}")
            return (
                None,
                sample_point_global,
                dynamic_radius,
            )  # نعيد النقطة لنرسمها حتى لو فشل اللون

        return best_match, sample_point_global, dynamic_radius

    except Exception as e:
        print(f"Error: {e}")
        return None, None, None


# ============================================================
#                    إعدادات التصحيحq
# ============================================================
SHOT_COOLDOWN = 0.6  # ثانية ونصف بين كل طلقة (بطيء للمراقبة)
DEBUG_MODE = True  # طباعة كل التفاصيل
shot_counter = 0  # عداد الطلقات
shot_history = []  # سجل الطلقات


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
        "end_idx": 0,
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
                "end_idx": i,
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

    distance = math.sqrt((tx - fx) ** 2 + (ty - fy) ** 2)
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
    num = abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1)
    den = math.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2)
    if den == 0:
        return float("inf")
    return num / den


def find_best_target(balls, current_ball_color, frog_center=None):
    """
    إيجاد أفضل كرة للتصويب - مع تسجيل مفصل
    """
    if not balls:
        log("No balls detected!", "WARNING")
        return None, float("-inf"), "No balls"

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
    best_score = float("-inf")
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
            difficulty = calculate_shot_difficulty(
                frog_center, target_pos, balls, target_ball
            )
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
            "ball": target_ball,
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
        log(
            f"{marker} #{i+1} {c['color']:8} | Score: {c['score']:6.0f} | Size: {c['group_size']} | Danger: {c['danger']:.2f}",
            "ANALYSIS",
        )
        log(f"       Pos: {c['position']} | Reasons: {c['reasons']}", "ANALYSIS")
    log("=" * 60, "ANALYSIS")

    if best_target:
        log(
            f"SELECTED: {best_target['color']} at {best_target['position']} with score {best_score:.0f}",
            "DECISION",
        )
    else:
        log("NO TARGET FOUND!", "WARNING")

    return best_target, best_score, best_reason


def execute_shot(target_pos, game_offset, target_color, score, reason):
    """تنفيذ التصويب مع تسجيل مفصل"""
    global shot_counter, shot_history, CURRENT_BALL_COLOR

    shot_counter += 1
    real_target_x = target_pos[0] + game_offset[0]
    real_target_y = target_pos[1] + game_offset[1]

    # تسجيل الطلقة
    shot_record = {
        "id": shot_counter,
        "time": datetime.now().strftime("%H:%M:%S"),
        "color": target_color,
        "local_pos": target_pos,
        "screen_pos": (real_target_x, real_target_y),
        "score": score,
        "reason": reason,
    }
    shot_history.append(shot_record)

    # طباعة مفصلة
    print("\n" + "🎯" * 30)
    print(f"  SHOT #{shot_counter}")
    print(f"  Time: {shot_record['time']}")
    print(f"  Target Color: {target_color}")
    print(f"  Local Position: {target_pos}")
    print(f"  Screen Position: ({real_target_x}, {real_target_y})")
    print(f"  Score: {score:.0f}")
    print(f"  Reason: {reason}")
    print("🎯" * 30 + "\n")

    # ============================================================

    # تنفيذ التصويب
    pyautogui.moveTo(real_target_x, real_target_y, duration=0)
    time.sleep(0.05)
    pyautogui.click()
    log(f"Shot #{shot_counter} executed!", "SHOT")
    CURRENT_BALL_COLOR = None


def print_shot_history():
    """طباعة سجل كل الطلقات"""
    print("\n" + "=" * 70)
    print("SHOT HISTORY")
    print("=" * 70)
    for shot in shot_history:
        print(
            f"#{shot['id']:3} | {shot['time']} | {shot['color']:8} | Pos: {shot['screen_pos']} | Score: {shot['score']:.0f}"
        )
    print("=" * 70)
    print(f"Total shots: {len(shot_history)}")
    print("=" * 70 + "\n")


# ============================================================
#                    الحلقة الرئيسية
# ============================================================
if __name__ == "__main__":

    SELECTED_CONFIG = Deluxe3
    PATH_CONFIG = ZUMA_DELUXE_CONFIG

    CURRENT_BALL_COLOR = None
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

    keyboard.add_hotkey("s", toggle_shoot)
    keyboard.add_hotkey("q", stop_shooting)
    keyboard.add_hotkey("x", quit_program)
    keyboard.add_hotkey("esc", quit_program)

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
                    (gx - capture_x, gy - capture_y) for gx, gy in global_path_points
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
        last_sample_info = None  # سيخزن (point_global, radius)

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
                            (gx - game_x, gy - game_y) for gx, gy in global_path_points
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
                        cv2.putText(
                            result,
                            "FROG",
                            (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 255, 0),
                            2,
                        )
                        cv2.circle(result, frog_center, 5, (0, 0, 255), -1)
                    else:
                        frog_center = None

                    if CURRENT_BALL_COLOR is None and frog_center:

                        log("Performing flick check...", "ACTION")

                        # [تعديل] استلام القيم الثلاثة من الدالة
                        # استدعاء الدالة
                        detected_color, sample_pt, sample_rad = active_color_check(
                            sct,
                            full_monitor,
                            frog_box,
                            (game_x, game_y),
                            SELECTED_CONFIG["hue_sat"],
                        )

                        # [تعديل هام] تحديث معلومات الرسم دائماً إذا وجدت نقطة فحص
                        if sample_pt is not None:
                            last_sample_info = (sample_pt, sample_rad)

                        if detected_color:
                            CURRENT_BALL_COLOR = detected_color
                            log(f"Result: {detected_color}", "SUCCESS")
                        else:
                            # لا تمسح last_sample_info هنا! اتركه لنرى أين يحاول البوت أن ينظر
                            pass

                    # =======================================================
                    # ... هنا يكمل الكود باقي العمليات (البحث عن الهدف والتصويب) ...
                    # =======================================================

                    # ═══════════════════════════════════════════
                    # التصويب التلقائي
                    # ═══════════════════════════════════════════
                    if AUTO_SHOOT and CURRENT_BALL_COLOR:
                        current_time = time.time()
                        time_since_last = current_time - last_shot_time
                        time_until_next = max(0, SHOT_COOLDOWN - time_since_last)

                        # عرض العد التنازلي
                        cv2.putText(
                            result,
                            f"Next shot in: {time_until_next:.1f}s",
                            (10, 150),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 255),
                            2,
                        )

                        if frog_center is None:
                            log("Frog not detected!", "WARNING")
                        if not balls:
                            log("No balls detected!", "WARNING")

                        if time_since_last > SHOT_COOLDOWN:
                            if frog_center and balls:
                                log("Analyzing targets...", "SCAN")
                                best_target, score, reason = find_best_target(
                                    balls, CURRENT_BALL_COLOR, frog_center
                                )

                                if best_target:
                                    target_pos = best_target["position"]
                                    game_offset = (game_x, game_y)

                                    # 1. نحصل على عرض اللعبة الحالي (من مكتشف الضفدع لأنه يعرف حجم الصورة)
                                    game_w = frog_detector.w

                                    # 2. نفحص: هل الهدف يقع في أقصى اليمين؟ (العرض الكلي - 180)
                                    is_in_right_edge = target_pos[0] > (
                                        game_w - FORBIDDEN_WIDTH
                                    )

                                    # 3. نفحص: هل الهدف يقع في أعلى الشاشة؟ (أقل من 100)
                                    is_in_top_edge = target_pos[1] < FORBIDDEN_HEIGHT

                                    # 4. الشرط القاتل: إذا تحقق الشرطان، إلغِ العملية فوراً
                                    if is_in_right_edge and is_in_top_edge:
                                        log(
                                            "⛔ STOP! Target is inside the FORBIDDEN BUTTONS zone.",
                                            "WARNING",
                                        )

                                        # رسم مستطيل أحمر حول المنطقة المحظورة لنرى التحذير
                                        # (اختياري: يمكنك حذفه إذا لم ترد الرسم)
                                        top_left_x = int(game_w - FORBIDDEN_WIDTH)
                                        cv2.rectangle(
                                            result,
                                            (top_left_x, 0),
                                            (game_w, FORBIDDEN_HEIGHT),
                                            (0, 0, 255),
                                            3,
                                        )
                                        cv2.putText(
                                            result,
                                            "X",
                                            (top_left_x + 50, 50),
                                            cv2.FONT_HERSHEY_SIMPLEX,
                                            2,
                                            (0, 0, 255),
                                            3,
                                        )

                                        CURRENT_BALL_COLOR = (
                                            None  # تصفير اللون للبحث عن كرة أخرى
                                        )

                                        # تخطي كل ما تبقى في هذا التكرار (لن يتم استدعاء execute_shot)
                                        continue

                                    cv2.line(
                                        result,
                                        frog_center,
                                        target_pos,
                                        (0, 255, 255),
                                        3,
                                    )
                                    cv2.circle(result, target_pos, 20, (0, 0, 255), 3)

                                    execute_shot(
                                        target_pos,
                                        game_offset,
                                        best_target["color"],
                                        score,
                                        reason,
                                    )
                                    last_shot_time = current_time

                    # عرض الهدف المحتمل (بدون تصويب)
                    elif frog_center and balls:
                        best_target, score, reason = find_best_target(
                            balls, CURRENT_BALL_COLOR, frog_center
                        )
                        if best_target:
                            target_pos = best_target["position"]
                            cv2.line(result, frog_center, target_pos, (255, 255, 0), 2)
                            cv2.circle(result, target_pos, 15, (255, 0, 255), 2)

                    if last_sample_info and game_x > 0:
                        # تفكيك المعلومات
                        (global_sx, global_sy), s_radius = last_sample_info

                        # تحويل الإحداثيات العالمية إلى محلية (بالنسبة لنافذة اللعبة)
                        local_sx = global_sx - game_x
                        local_sy = global_sy - game_y

                        # رسم دائرة صفراء تحدد المنطقة التي تم فحص لونها
                        # الدائرة الخارجية
                        cv2.circle(
                            result, (local_sx, local_sy), s_radius + 2, (0, 255, 255), 2
                        )
                        # نقطة حمراء في المركز
                        cv2.circle(result, (local_sx, local_sy), 1, (0, 0, 255), -1)

                        # كتابة توضيح
                        cv2.putText(
                            result,
                            "Scan Point",
                            (local_sx + 10, local_sy),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 255, 255),
                            1,
                        )

                    if frog_detector:
                        game_w = frog_detector.w
                        game_h = frog_detector.h

                        # إحداثيات المستطيل
                        pt1 = (int(game_w - FORBIDDEN_WIDTH), 0)
                        pt2 = (int(game_w), int(FORBIDDEN_HEIGHT))

                        # رسم المستطيل الأحمر
                        cv2.rectangle(result, pt1, pt2, (0, 0, 255), 2)

                        # إضافة نص للتوضيح
                        cv2.putText(
                            result,
                            "NO CLICK ZONE",
                            (pt1[0] + 5, 20),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 0, 255),
                            1,
                        )

                    # =======================================================
                    # معلومات العرض (FPS etc...)
                    # =======================================================
                    frame_count += 1

                    # معلومات العرض
                    frame_count += 1
                    elapsed = time.time() - start_time
                    if elapsed > 1.0:
                        fps = frame_count / elapsed
                        frame_count = 0
                        start_time = time.time()

                    # الشريط العلوي
                    cv2.putText(
                        result,
                        f"FPS: {int(fps)} | Balls: {len(balls)} | Shots: {shot_counter}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2,
                    )

                    cv2.putText(
                        result,
                        f"Frog Ball: {CURRENT_BALL_COLOR}",
                        (10, 55),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 200, 255),
                        1,
                    )

                    status = "[S] AUTO: ON" if AUTO_SHOOT else "[S] AUTO: OFF"
                    color = (0, 255, 0) if AUTO_SHOOT else (0, 0, 255)
                    cv2.putText(
                        result,
                        status,
                        (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color,
                        2,
                    )
                    cv2.putText(
                        result,
                        "[Q] Stop+History | [X] Quit",
                        (10, 115),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        (200, 200, 200),
                        1,
                    )

                    cv2.imshow(window_name, result)

                except Exception as e:
                    log(f"Error: {e}", "ERROR")
                    import traceback

                    traceback.print_exc()
            else:
                blank_screen = np.zeros((300, 500, 3), dtype=np.uint8)
                cv2.putText(
                    blank_screen,
                    "Searching for game...",
                    (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),
                    2,
                )
                cv2.imshow(window_name, blank_screen)

            cv2.waitKey(1)

        keyboard.unhook_all()
        cv2.destroyAllWindows()

    print("\nProgram ended.")
    print_shot_history()
