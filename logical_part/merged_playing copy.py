# game_engine.py - FINAL OPTIMIZED VERSION 🏆

import cv2
import numpy as np
import time
import mss
import pyautogui
import keyboard
import math
from datetime import datetime
import ctypes


# ============================================================
# DPI Awareness
# ============================================================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

try:
    from frog_detection.FrogTemplateDetector import FrogTemplateDetector
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
    from frog_detection.FrogTemplateDetector import FrogTemplateDetector
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
#                    إعدادات النظام
# ============================================================
SHOT_COOLDOWN = 1.1
DEBUG_MODE = True
VERBOSE_DEBUG = False
shot_counter = 0
shot_history = []

FORBIDDEN_WIDTH = 340
FORBIDDEN_HEIGHT = 90
BALL_OFFSET_FACTOR = 0.552
SAMPLE_RADIUS_RATIO = 0.03

OCCLUSION_SAFETY_MARGIN = 1.3
TRACKING_MAX_DISTANCE = 30
TRACKING_MAX_MISSING_FRAMES = 3

DUMP_SHOT_THRESHOLD = 100
DUMP_ZONE_MIN_DISTANCE = 100
ENABLE_DUMP_SHOT = True


def log(message, level="INFO"):
    if DEBUG_MODE:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")


# ============================================================
#              Ball Tracker
# ============================================================
class BallTracker:

    def __init__(
        self,
        max_distance=TRACKING_MAX_DISTANCE,
        max_frames_missing=TRACKING_MAX_MISSING_FRAMES,
    ):
        self.tracked_balls = []
        self.next_id = 0
        self.max_distance = max_distance
        self.max_frames_missing = max_frames_missing

    def update(self, detected_balls):
        current_frame_ids = []

        for ball in detected_balls:
            best_match = None
            best_distance = self.max_distance

            for tracked in self.tracked_balls:
                if ball["color"] != tracked["color"]:
                    continue

                dist = math.sqrt(
                    (ball["position"][0] - tracked["position"][0]) ** 2
                    + (ball["position"][1] - tracked["position"][1]) ** 2
                )

                if dist < best_distance:
                    best_distance = dist
                    best_match = tracked

            if best_match:
                best_match["position"] = ball["position"]
                best_match["radius"] = ball["radius"]
                best_match["distance"] = ball.get("distance", 0)
                best_match["last_seen"] = 0
                best_match["confidence"] = min(best_match["confidence"] + 0.2, 1.0)
                best_match["original_ball"] = ball
                current_frame_ids.append(best_match["id"])
            else:
                new_tracked = {
                    "id": self.next_id,
                    "color": ball["color"],
                    "position": ball["position"],
                    "radius": ball["radius"],
                    "distance": ball.get("distance", 0),
                    "last_seen": 0,
                    "confidence": 0.5,
                    "original_ball": ball,
                }
                self.tracked_balls.append(new_tracked)
                current_frame_ids.append(self.next_id)
                self.next_id += 1

        for tracked in self.tracked_balls[:]:
            if tracked["id"] not in current_frame_ids:
                tracked["last_seen"] += 1
                tracked["confidence"] = max(tracked["confidence"] - 0.3, 0)
                if tracked["last_seen"] > self.max_frames_missing:
                    self.tracked_balls.remove(tracked)

        return [
            b["original_ball"] for b in self.tracked_balls if b["confidence"] >= 0.4
        ]


# ============================================================
#     كشف اللون الديناميكي
# ============================================================
def active_color_check(sct, monitor, initial_frog_box, game_offset, color_config):
    # دالة داخلية لحساب الهيو المسيطر (أدق من المتوسط العادي)
    def get_dominant_hue(hsv_img, mask):
        # حساب الهستوجرام لقناة الـ Hue فقط داخل القناع
        # الرينج 180 لأن OpenCV Hue من 0-179
        hist = cv2.calcHist([hsv_img], [0], mask, [180], [0, 180])

        # البحث عن القيمة الأكثر تكراراً (القمة)
        dominant_hue = np.argmax(hist)
        return dominant_hue

    gx, gy = game_offset
    fx, fy, fw, fh = initial_frog_box
    cx = fx + fw // 2
    cy = fy + fh // 2

    target_mouse_x = gx + cx
    top_limit = gy + 5
    target_mouse_y = max(top_limit, gy + cy - 300)

    target_mouse_x = max(0, min(target_mouse_x, monitor["width"] - 1))
    target_mouse_y = max(0, min(target_mouse_y, monitor["height"] - 1))

    # تحريك الماوس لكشف اللون (إجراء ضروري في كودك)
    pyautogui.moveTo(target_mouse_x, target_mouse_y, duration=0.1)
    time.sleep(0.15)

    search_margin = 80
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

        dynamic_offset_y = int(nfh * BALL_OFFSET_FACTOR)
        dynamic_radius = int(nfw * SAMPLE_RADIUS_RATIO)
        dynamic_radius = max(2, dynamic_radius)

        ball_global_x = int(gx + real_cx)
        ball_global_y = int(gy + real_cy - dynamic_offset_y)
        sample_point_global = (ball_global_x, ball_global_y)

        grab_area = {
            "top": int(ball_global_y - dynamic_radius),
            "left": int(ball_global_x - dynamic_radius),
            "width": dynamic_radius * 2,
            "height": dynamic_radius * 2,
        }

        sample_img = np.array(sct.grab(grab_area))
        sample_bgr = cv2.cvtColor(sample_img, cv2.COLOR_BGRA2BGR)
        hsv_roi = cv2.cvtColor(sample_bgr, cv2.COLOR_BGR2HSV)

        # ---------------------------------------------------------
        # >>> التحسين الجديد: القناع الدائري وحساب اللون المسيطر <<<
        # ---------------------------------------------------------
        h_roi, w_roi = hsv_roi.shape[:2]

        # 1. إنشاء قناع دائري (أسود بالكامل مع دائرة بيضاء في المنتصف)
        mask = np.zeros((h_roi, w_roi), dtype=np.uint8)
        # نصف القطر يكون أصغر قليلاً من العرض لتجنب الحواف تماماً
        cv2.circle(mask, (w_roi // 2, h_roi // 2), int(w_roi / 2) - 1, 255, -1)

        mean_val = cv2.mean(hsv_roi, mask=mask)
        current_hue = mean_val[0]
        current_sat = mean_val[1]  # <--- استخرجنا التشبع الآن

        best_match = None
        # نرفع القيمة الابتدائية لأننا سنجمع رقمين الآن
        min_error = 9999

        # معاملات الأهمية (Weights)
        # نعيطي الـ Hue أهمية أكبر (مثلاً 1.0) والـ Saturation أهمية مساندة (0.5)
        W_HUE = 1.0
        W_SAT = 0.4

        for color_name, (known_hue, known_sat) in color_config.items():
            # 1. حساب فرق الـ Hue (مع مراعاة الدائرة 180)
            diff_h = abs(current_hue - known_hue)
            if diff_h > 90:
                diff_h = 180 - diff_h

            # 2. حساب فرق الـ Saturation
            diff_s = abs(current_sat - known_sat)

            # 3. حساب الخطأ الكلي الموزون
            # المعادلة: الخطأ = (فرق اللون) + (نصف فرق التشبع)
            total_error = (diff_h * W_HUE) + (diff_s * W_SAT)

            # تتبع الأفضل
            if total_error < min_error:
                min_error = total_error
                best_match = color_name

        # --- فلتر الأمان (هام جداً للضفدع) ---

        # إذا كان اللون المكتشف هو الأخضر، والتشبع منخفض جداً
        # فهذا غالباً جلد الضفدع وليس الكرة -> نرفضه
        if best_match == "Green" and current_sat < 80:  # عدل الـ 80 حسب التجربة
            if DEBUG_MODE:
                log(f"Rejected Dull Green (Frog Skin). Sat: {current_sat:.1f}", "DEBUG")
            return None, sample_point_global, dynamic_radius

        # شرط الدقة (أصبح يعتمد على الـ Error الموزون)
        # قد تحتاج لتعديل الرقم 30 بناء على تجربتك
        if min_error > 35:
            # log(f"Unsure color. Error: {min_error:.1f}", "DEBUG")
            return None, sample_point_global, dynamic_radius

        return best_match, sample_point_global, dynamic_radius

    except Exception as e:
        log(f"Color check error: {e}", "ERROR")
        return None, None, None


# ============================================================
#              دوال تحليل الكرات
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


def point_to_line_distance(px, py, x1, y1, x2, y2):
    num = abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1)
    den = math.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2)
    if den == 0:
        return float("inf")
    return num / den


# ============================================================
#              Occlusion Detection
# ============================================================
def is_shot_blocked(frog_center, target_pos, all_balls, target_ball):
    if frog_center is None:
        return True, None

    fx, fy = frog_center
    tx, ty = target_pos

    for ball in all_balls:
        if ball == target_ball:
            continue

        bx, by = ball["position"]
        b_radius = ball["radius"]

        dist_to_line = point_to_line_distance(bx, by, fx, fy, tx, ty)
        dist_frog_to_ball = math.sqrt((bx - fx) ** 2 + (by - fy) ** 2)
        dist_frog_to_target = math.sqrt((tx - fx) ** 2 + (ty - fy) ** 2)

        if dist_to_line < (b_radius * OCCLUSION_SAFETY_MARGIN):
            if dist_frog_to_ball < dist_frog_to_target * 0.95:
                return True, ball

    return False, None


def check_if_shootable(target_ball, all_balls, frog_center):
    if not frog_center:
        return True

    blocked, _ = is_shot_blocked(
        frog_center, target_ball["position"], all_balls, target_ball
    )
    return not blocked


# ============================================================
#     🔥 DUMP SHOT SYSTEM
# ============================================================
def find_dump_zone(balls, frog_center, game_width, game_height):
    if not frog_center or not balls:
        return None

    candidate_zones = [
        (game_width * 0.15, game_height * 0.25),
        (game_width * 0.15, game_height * 0.75),
        (game_width * 0.5, game_height * 0.15),
        (game_width * 0.85, game_height * 0.75),
    ]

    best_zone = None
    max_min_distance = 0

    for zone_x, zone_y in candidate_zones:
        min_distance_to_ball = float("inf")

        for ball in balls:
            bx, by = ball["position"]
            dist = math.sqrt((zone_x - bx) ** 2 + (zone_y - by) ** 2)
            min_distance_to_ball = min(min_distance_to_ball, dist)

        if (
            min_distance_to_ball > max_min_distance
            and min_distance_to_ball > DUMP_ZONE_MIN_DISTANCE
        ):
            max_min_distance = min_distance_to_ball
            best_zone = (int(zone_x), int(zone_y))

    return best_zone


def should_dump_ball(best_score, current_ball_color, balls):
    """
    قرار الرمي المحسّن
    """
    if not ENABLE_DUMP_SHOT:
        return False

    same_color_count = sum(1 for b in balls if b["color"] == current_ball_color)

    # حالة 1: لا يوجد كرات بنفس اللون
    if same_color_count == 0:
        log(f"⚡ DUMP: No {current_ball_color} balls!", "DECISION")
        return True

    # حالة 2: Score سالب (FALLBACK سيء)
    if best_score < 0:
        log(f"⚠️ DUMP: Negative score ({best_score})", "DECISION")
        return True

    # حالة 3: كرة واحدة + Score ضعيف
    if same_color_count == 1 and best_score < 100:
        log(f"🔹 DUMP: Only 1 ball + low score ({best_score})", "DECISION")
        return True

    return False


# ============================================================
#              🔥 OPTIMIZED Target Finding
# ============================================================
def find_best_target(balls, current_ball_color, frog_center=None):
    if not balls:
        log("No balls detected!", "WARNING")
        return None, float("-inf"), "No balls"

    shootable_balls = []

    for ball in balls:
        if check_if_shootable(ball, balls, frog_center):
            shootable_balls.append(ball)

    if not shootable_balls:
        shootable_balls = balls

    groups = find_color_groups(shootable_balls)
    max_distance = (
        max(b.get("distance", 0) for b in shootable_balls) if shootable_balls else 1
    )
    has_color_match = any(g["color"] == current_ball_color for g in groups)

    best_target = None
    best_score = float("-inf")
    best_reason = ""

    for group_idx, group in enumerate(groups):
        group_size = len(group["balls"])
        target_ball = group["balls"][0]
        target_pos = target_ball["position"]

        score = 0
        reasons = []

        # أولوية COLOR_MATCH قوية جداً
        if group["color"] == current_ball_color:
            score += 1000  # ← مضاعفة
            reasons.append("MATCH")

            is_first_match = all(
                prev_group["color"] != current_ball_color
                for prev_group in groups[:group_idx]
            )
            if is_first_match:
                score += 200
                reasons.append("FIRST")
        else:
            if has_color_match:
                score -= 1000  # ← عقوبة ضخمة
                reasons.append("BAD_FB")
            else:
                score -= 100  # ← عقوبة خفيفة
                reasons.append("FB")

        # بونصات أقل أهمية
        if group_size >= 3:
            score += group_size * 20
            reasons.append(f"GRP({group_size})")
        elif group_size == 2:
            score += 50
            reasons.append("PAIR")
        else:
            score += 10
            reasons.append("ONE")

        chain = check_chain_potential(groups, group_idx)
        if chain:
            score += chain * 15
            reasons.append(f"CHN({chain})")

        avg_dist = sum(b.get("distance", 0) for b in group["balls"]) / group_size
        danger = calculate_danger_level(avg_dist, max_distance)

        if danger > 0.7:
            score += 150
            reasons.append("DNG")
        elif danger > 0.4:
            score += 60
            reasons.append("MED")

        if frog_center:
            fx, fy = frog_center
            tx, ty = target_pos
            angle = math.atan2(ty - fy, tx - fx)
            if angle < -math.pi / 3 and tx > fx:
                score -= 50
                reasons.append("ANG")

        if score > best_score:
            best_score = score
            best_target = target_ball
            best_reason = " | ".join(reasons)

    return best_target, best_score, best_reason


# ============================================================
#     تنفيذ التصويب
# ============================================================
def execute_shot(
    target_pos,
    game_offset,
    target_color,
    score,
    reason,
    frog_center=None,
    is_dump=False,
):
    global shot_counter, shot_history, CURRENT_BALL_COLOR

    shot_counter += 1

    real_target_x = target_pos[0] + game_offset[0]
    real_target_y = target_pos[1] + game_offset[1]

    shot_type = "🗑️ DUMP" if is_dump else "🎯 SHOT"

    shot_record = {
        "id": shot_counter,
        "time": datetime.now().strftime("%H:%M:%S"),
        "color": target_color,
        "type": "dump" if is_dump else "normal",
        "score": score,
    }
    shot_history.append(shot_record)

    print(
        f"\n{shot_type} #{shot_counter} | {target_color} | Score: {score:.0f} | {reason}"
    )

    pyautogui.moveTo(real_target_x, real_target_y, duration=0)
    time.sleep(0.1)
    pyautogui.click()

    log(f"Shot #{shot_counter} executed!", "SHOT")
    CURRENT_BALL_COLOR = None


def print_shot_history():
    print("\n" + "=" * 70)
    print("SHOT HISTORY")
    print("=" * 70)

    normal_shots = sum(1 for s in shot_history if s["type"] == "normal")
    dump_shots = sum(1 for s in shot_history if s["type"] == "dump")

    for shot in shot_history[-20:]:
        shot_type = "🗑️" if shot["type"] == "dump" else "🎯"
        print(
            f"{shot_type} #{shot['id']:3} | {shot['time']} | {shot['color']:8} | Score: {shot['score']:.0f}"
        )

    print("=" * 70)
    print(f"Total: {len(shot_history)} | Normal: {normal_shots} | Dumps: {dump_shots}")
    print("=" * 70 + "\n")


# ============================================================
#                    الحلقة الرئيسية
# ============================================================
if __name__ == "__main__":

    SELECTED_CONFIG = Beach
    PATH_CONFIG = ZUMA_GREEN_JUNGLE_CONFIG

    CURRENT_BALL_COLOR = None
    AUTO_SHOOT = False
    PAUSED = False
    RUNNING = True

    def toggle_shoot():
        global AUTO_SHOOT
        AUTO_SHOOT = not AUTO_SHOOT
        print(
            f"\n{'='*50}\n>>> Auto Shoot: {'ON' if AUTO_SHOOT else 'OFF'} <<<\n{'='*50}\n"
        )

    def toggle_pause():
        global PAUSED
        PAUSED = not PAUSED
        print(
            f"\n{'='*50}\n>>> Bot: {'PAUSED' if PAUSED else 'RESUMED'} <<<\n{'='*50}\n"
        )

    def toggle_dump():
        global ENABLE_DUMP_SHOT
        ENABLE_DUMP_SHOT = not ENABLE_DUMP_SHOT
        print(
            f"\n{'='*50}\n>>> Dump Shot: {'ON' if ENABLE_DUMP_SHOT else 'OFF'} <<<\n{'='*50}\n"
        )

    def stop_shooting():
        global AUTO_SHOOT
        AUTO_SHOOT = False
        print("\n>>> STOPPED <<<")
        print_shot_history()

    def quit_program():
        global RUNNING, AUTO_SHOOT, PAUSED
        AUTO_SHOOT = False
        PAUSED = False
        RUNNING = False
        print("\n>>> QUITTING... <<<")
        print_shot_history()

    keyboard.add_hotkey("s", toggle_shoot)
    keyboard.add_hotkey("p", toggle_pause)
    keyboard.add_hotkey("d", toggle_dump)
    keyboard.add_hotkey("q", stop_shooting)
    keyboard.add_hotkey("x", quit_program)
    keyboard.add_hotkey("esc", quit_program)

    zone_manager = IgnoredZonesManager("ignored_zones.json")
    ignored_zones = None

    bot = ZumaBot(SELECTED_CONFIG)
    frog_detector = None
    ball_tracker = BallTracker()

    cached_path_points = None
    # متغير لتخزين آخر أبعاد معروفة للعبة للمقارنة
    last_game_rect = None  # (x, y, width, height)

    window_name = "Zuma Bot - FINAL"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

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
                cached_path_points = local_path_points
                log("Path detected!")

        capture_area = None
        last_recheck_time = 0
        RECHECK_INTERVAL = 3

        last_shot_time = 0
        last_sample_info = None

        fps = 0
        frame_count = 0
        start_time = time.time()

        game_x, game_y = 0, 0
        detected_balls = []
        stable_balls = []
        frog_box = None
        frog_center = None

        print("\n" + "=" * 60)
        print("  ZUMA BOT - FINAL OPTIMIZED 🏆")
        print("=" * 60)
        print(f"  Priority System: COLOR_MATCH x2")
        print(f"  Dump Logic: Smart & Fast")
        print("=" * 60)
        print("  [S] Auto  [P] Pause  [D] Dump  [Q] Stop  [X] Quit")
        print("=" * 60 + "\n")

        while RUNNING:
            loop_start = time.time()

            if PAUSED:
                blank_screen = np.zeros((300, 500, 3), dtype=np.uint8)
                cv2.putText(
                    blank_screen,
                    "PAUSED",
                    (150, 150),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 255),
                    2,
                )
                cv2.imshow(window_name, blank_screen)
                cv2.waitKey(100)
                continue

            if loop_start - last_recheck_time > RECHECK_INTERVAL:
                full_screenshot = np.array(sct.grab(full_monitor))
                full_screenshot_bgr = cv2.cvtColor(full_screenshot, cv2.COLOR_BGRA2BGR)
                new_region_data = analyze_game_screen(full_screenshot_bgr)

                if new_region_data:
                    game_x = new_region_data.x
                    game_y = new_region_data.y

                    # نحصل على أبعاد منطقة اللعب الحالية
                    temp_capture = new_region_data.to_mss_dict(
                        full_monitor["left"], full_monitor["top"]
                    )
                    current_w = temp_capture["width"]
                    current_h = temp_capture["height"]

                    current_rect = (game_x, game_y, current_w, current_h)

                    # نقوم بتحديث منطقة الالتقاط
                    capture_area = temp_capture

                    if last_game_rect != current_rect:
                        print(
                            f"\n[🔄 UPDATE] Change detected! Old: {last_game_rect} -> New: {current_rect}"
                        )
                        print("[🔄 UPDATE] Re-scanning path geometry...")

                        # 1. إعادة استدعاء دالة كشف المسار (أثقل لكن أدق)
                        # ملاحظة: ستعمل هذه الدالة على الشاشة الحالية
                        global_path_points, _ = capture_game_path(PATH_CONFIG)

                        if global_path_points:
                            # 2. تحديث المسار المحلي بناءً على الإحداثيات الجديدة
                            cached_path_points = [
                                (gx - game_x, gy - game_y)
                                for gx, gy in global_path_points
                            ]
                            print(
                                f"[✅ SUCCESS] Path updated! Points: {len(cached_path_points)}"
                            )
                        else:
                            print(
                                "[❌ FAILED] Could not find path (maybe covered by balls?)"
                            )
                            # في حال الفشل، نبقي المسار القديم كما هو أو نفرغه حسب رغبتك

                        # تحديث الأبعاد المعروفة
                        last_game_rect = current_rect

                last_recheck_time = loop_start

            if capture_area:
                try:
                    sct_img = sct.grab(capture_area)
                    frame = np.array(sct_img)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                    if frog_detector is None:
                        h, w = frame.shape[:2]
                        if SELECTED_CONFIG == Deluxe3:
                            frog_detector = ZumaFrogDetector(w, h)
                        elif SELECTED_CONFIG == Beach:
                            SELECTED_CONFIG = FrogTemplateDetector(
                                templates_dir="frog_detection/templates", threshold=0.62
                            )

                    result, detected_balls = bot.detect_from_frame(
                        frame,
                        ignored_zones=ignored_zones,
                        path_points=cached_path_points,
                    )

                    stable_balls = ball_tracker.update(detected_balls)

                    if cached_path_points and len(cached_path_points) > 0:
                        pts = np.array(cached_path_points, np.int32)
                        pts = pts.reshape((-1, 1, 2))
                        cv2.polylines(result, [pts], False, (0, 0, 0), 2)

                    frog_box = frog_detector.detect(frame)

                    if frog_box:
                        x, y, fw, fh = frog_box
                        frog_center = (x + fw // 2, y + fh // 2)
                        cv2.rectangle(result, (x, y), (x + fw, y + fh), (0, 255, 0), 2)
                        cv2.circle(result, frog_center, 5, (0, 0, 255), -1)
                    else:
                        frog_center = None

                    if CURRENT_BALL_COLOR is None and frog_center:
                        detected_color, sample_pt, sample_rad = active_color_check(
                            sct,
                            full_monitor,
                            frog_box,
                            (game_x, game_y),
                            SELECTED_CONFIG["hue_sat"],
                        )

                        if sample_pt is not None:
                            last_sample_info = (sample_pt, sample_rad)

                        if detected_color:
                            CURRENT_BALL_COLOR = detected_color
                            log(f"Color: {detected_color}", "SUCCESS")

                    if AUTO_SHOOT and CURRENT_BALL_COLOR:
                        current_time = time.time()
                        time_since_last = current_time - last_shot_time

                        if time_since_last > SHOT_COOLDOWN:
                            if frog_center and stable_balls:
                                best_target, score, reason = find_best_target(
                                    stable_balls, CURRENT_BALL_COLOR, frog_center
                                )

                                if should_dump_ball(
                                    score, CURRENT_BALL_COLOR, detected_balls
                                ):
                                    dump_zone = find_dump_zone(
                                        stable_balls,
                                        frog_center,
                                        frog_detector.w,
                                        frog_detector.h,
                                    )

                                    if dump_zone:
                                        cv2.circle(
                                            result, dump_zone, 30, (0, 255, 255), 3
                                        )
                                        cv2.line(
                                            result,
                                            frog_center,
                                            dump_zone,
                                            (0, 255, 255),
                                            2,
                                        )

                                        game_offset = (game_x, game_y)
                                        execute_shot(
                                            dump_zone,
                                            game_offset,
                                            CURRENT_BALL_COLOR,
                                            score,
                                            "DUMP",
                                            frog_center,
                                            is_dump=True,
                                        )
                                        last_shot_time = current_time
                                        continue

                                if best_target:
                                    target_pos = best_target["position"]

                                    blocked, _ = is_shot_blocked(
                                        frog_center,
                                        target_pos,
                                        stable_balls,
                                        best_target,
                                    )
                                    line_color = (0, 0, 255) if blocked else (0, 255, 0)

                                    cv2.line(
                                        result, frog_center, target_pos, line_color, 3
                                    )
                                    cv2.circle(result, target_pos, 15, (255, 0, 255), 3)

                                    game_offset = (game_x, game_y)
                                    execute_shot(
                                        target_pos,
                                        game_offset,
                                        best_target["color"],
                                        score,
                                        reason,
                                        frog_center=frog_center,
                                    )
                                    last_shot_time = current_time

                    if last_sample_info and game_x > 0:
                        (global_sx, global_sy), s_radius = last_sample_info
                        local_sx = global_sx - game_x
                        local_sy = global_sy - game_y
                        cv2.circle(
                            result, (local_sx, local_sy), s_radius + 2, (0, 255, 255), 2
                        )

                    frame_count += 1
                    elapsed = time.time() - start_time
                    if elapsed > 1.0:
                        fps = frame_count / elapsed
                        frame_count = 0
                        start_time = time.time()

                    cv2.putText(
                        result,
                        f"FPS: {int(fps)} | Balls: {len(stable_balls)} | Shots: {shot_counter}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2,
                    )

                    cv2.putText(
                        result,
                        f"Frog: {CURRENT_BALL_COLOR}",
                        (10, 55),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 0),
                        2,
                    )

                    status = "ON" if AUTO_SHOOT else "OFF"
                    color = (0, 255, 0) if AUTO_SHOOT else (0, 0, 255)
                    cv2.putText(
                        result,
                        f"[S] {status}",
                        (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color,
                        2,
                    )

                    # 1. حساب الإحداثيات للزاوية اليمنى
                    # result.shape[1] هو عرض النافذة الحالية
                    screen_w = result.shape[1]

                    # نقطة البداية (x) = عرض الشاشة - عرض المنطقة المحظورة
                    start_point = (screen_w - FORBIDDEN_WIDTH, 0)

                    # نقطة النهاية (x, y) = عرض الشاشة، ارتفاع المنطقة المحظورة
                    end_point = (screen_w, FORBIDDEN_HEIGHT)

                    # 2. الرسم
                    cv2.rectangle(result, start_point, end_point, (0, 0, 255), 2)

                    # ضبط مكان النص ليكون داخل المستطيل الأيمن
                    text_pos_x = screen_w - FORBIDDEN_WIDTH + 10
                    cv2.putText(
                        result,
                        "IGNORED",
                        (text_pos_x, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2,
                    )

                    # رسم خط X داخل المستطيل (اختياري)
                    cv2.line(result, start_point, end_point, (0, 0, 255), 1)
                    cv2.line(
                        result,
                        (screen_w, 0),
                        (screen_w - FORBIDDEN_WIDTH, FORBIDDEN_HEIGHT),
                        (0, 0, 255),
                        1,
                    )

                    cv2.imshow(window_name, result)

                except Exception as e:
                    log(f"Error: {e}", "ERROR")
            else:
                blank_screen = np.zeros((300, 500, 3), dtype=np.uint8)
                cv2.putText(
                    blank_screen,
                    "Searching...",
                    (100, 150),
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
