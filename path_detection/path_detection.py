import sys
import cv2
import numpy as np
import matplotlib.pyplot as plt
from skimage.morphology import skeletonize
from collections import deque
from scipy.ndimage import distance_transform_edt

# ==================== helper funcitons ====================

def remove_noise_by_area(mask, min_area=500):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    new_mask = np.zeros_like(mask)
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            new_mask[labels == i] = 255
    return new_mask

def find_skeleton_endpoints(skeleton):
    kernel = np.array([[1, 1, 1],
                       [1, 10, 1],
                       [1, 1, 1]], dtype=np.uint8)
    skel_binary = (skeleton > 0).astype(np.uint8)
    filtered = cv2.filter2D(skel_binary, -1, kernel)
    y, x = np.where(filtered == 11)
    return list(zip(x, y))

# ==================== تحسين استخراج القناع ====================


def get_combined_mask_improved(img, config):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, w = img.shape[:2]
    
    lower_path = np.array(config['path_hsv_low'])
    upper_path = np.array(config['path_hsv_high'])
    mask_hsv = cv2.inRange(hsv, lower_path, upper_path)
    
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    mask_sat = ((s < config.get('sat_threshold', 70)) & 
                (v < config.get('val_high', 180)) & 
                (v > config.get('val_low', 20))).astype(np.uint8) * 255
    combined = cv2.bitwise_or(mask_hsv, mask_sat)
    
    margin_w, margin_h = int(w * 0.05), int(h * 0.05)
    cv2.rectangle(combined, (0, 0), (w, margin_h), 0, -1)
    cv2.rectangle(combined, (0, h - margin_h), (w, h), 0, -1)
    cv2.rectangle(combined, (0, 0), (margin_w, h), 0, -1)
    cv2.rectangle(combined, (w - margin_w, 0), (w, h), 0, -1)
    
    for (rx1, ry1, rx2, ry2) in config.get('ui_masks_pct', []):
        ix1, iy1 = int(rx1 * w), int(ry1 * h)
        ix2, iy2 = int(rx2 * w), int(ry2 * h)
        cv2.rectangle(combined, (ix1, iy1), (ix2, iy2), 0, -1)
    
    return combined


def clean_mask_morphology(mask, config):
    mask = remove_noise_by_area(mask, min_area=config.get('min_noise_area', 200))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    small_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, small_kernel, iterations=1)
    mask = remove_noise_by_area(mask, min_area=config.get('min_component_area', 300))
    return mask

# ==================== finding the hole ====================

def find_hole_in_mask(mask, min_area=200, max_area=20000, circularity_range=(0.15, 2.0)):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_hole = None
    max_score = 0
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            (x, y), radius = cv2.minEnclosingCircle(cnt)
            circularity = area / (np.pi * radius**2) if radius > 0 else 0
            
            if circularity_range[0] < circularity < circularity_range[1] and radius > 5:
                score = area * (circularity ** 0.5)
                if score > max_score:
                    max_score = score
                    best_hole = (int(x), int(y))
    return best_hole

def find_finish_hole_improved(img, config):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, w = img.shape[:2]
    
    ui_mask_img = np.zeros((h, w), dtype=np.uint8)
    
    if 'ui_masks_pct' in config:
        for (rx1, ry1, rx2, ry2) in config['ui_masks_pct']:
            ix1, iy1 = int(rx1 * w), int(ry1 * h)
            ix2, iy2 = int(rx2 * w), int(ry2 * h)
            cv2.rectangle(ui_mask_img, (ix1, iy1), (ix2, iy2), 255, -1)
    elif 'ui_masks' in config:
        for (x1, y1, x2, y2) in config.get('ui_masks', []):
            cv2.rectangle(ui_mask_img, (x1, y1), (x2, y2), 255, -1)
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask_dark = cv2.threshold(gray, config.get('hole_thresh', 35), 255, cv2.THRESH_BINARY_INV)
    
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 50])
    mask_black_hsv = cv2.inRange(hsv, lower_black, upper_black)
    
    combined_black = cv2.bitwise_or(mask_dark, mask_black_hsv)
    
    combined_black[ui_mask_img > 0] = 0
    
    border = 15
    cv2.rectangle(combined_black, (0, 0), (w, border), 0, -1)
    cv2.rectangle(combined_black, (0, h - border), (w, h), 0, -1)
    cv2.rectangle(combined_black, (0, 0), (border, h), 0, -1)
    cv2.rectangle(combined_black, (w - border, 0), (w, h), 0, -1)
    
    black_hole_pos = find_hole_in_mask(combined_black)
    
    if black_hole_pos is not None:
        return black_hole_pos
    
    low_g = config.get('gold_hsv_low', [15, 150, 100]) 
    high_g = config.get('gold_hsv_high', [35, 255, 255])
    mask_gold = cv2.inRange(hsv, np.array(low_g), np.array(high_g))
    
    mask_gold[ui_mask_img > 0] = 0
    cv2.rectangle(mask_gold, (0, 0), (w, border), 0, -1)
    cv2.rectangle(mask_gold, (0, h - border), (w, h), 0, -1)
    cv2.rectangle(mask_gold, (0, 0), (border, h), 0, -1)
    cv2.rectangle(mask_gold, (w - border, 0), (w, h), 0, -1)
    
    return find_hole_in_mask(mask_gold)

# ==================== دوال تتبع المسار ====================

def get_component_endpoints(skeleton, labels, component_id):
    mask = (labels == component_id).astype(np.uint8) * 255
    return find_skeleton_endpoints(mask)

def trace_single_component(skeleton, labels, component_id, start_point):
    mask = (labels == component_id).astype(np.uint8) * 255
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    path = []
    
    queue = deque([start_point])
    visited[start_point[1], start_point[0]] = True
    
    directions = [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]
    last_point = start_point
    
    while queue:
        current = queue.popleft()
        path.append(current)
        last_point = current
        
        neighbors = []
        for dx, dy in directions:
            nx, ny = current[0] + dx, current[1] + dy
            if 0 <= nx < w and 0 <= ny < h:
                if mask[ny, nx] > 0 and not visited[ny, nx]:
                    neighbors.append((nx, ny))
                    visited[ny, nx] = True
        
        if len(neighbors) > 1:
            neighbors.sort(key=lambda p: abs(p[0]-current[0]) + abs(p[1]-current[1]))
        
        for neighbor in neighbors:
            queue.append(neighbor)
    
    return path, last_point

def find_nearest_component(current_point, remaining_components, labels, skeleton):
    min_dist = float('inf')
    nearest_comp = None
    nearest_endpoint = None
    
    for comp_id in remaining_components:
        endpoints = get_component_endpoints(skeleton, labels, comp_id)
        for ep in endpoints:
            dist = np.sqrt((ep[0] - current_point[0])**2 + (ep[1] - current_point[1])**2)
            if dist < min_dist:
                min_dist = dist
                nearest_comp = comp_id
                nearest_endpoint = ep
    
    return nearest_comp, nearest_endpoint, min_dist

# ==================== ربط المكونات ====================

def order_all_segments(skeleton, hole_center, max_gap=100):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(skeleton)
    
    if num_labels <= 1:
        return None, None, [], skeleton
    
    valid_components = []
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] >= 30:
            valid_components.append(i)
    
    if not valid_components:
        return None, None, [], skeleton
    
    min_dist_to_hole = float('inf')
    end_component = None
    end_point = None
    
    for comp_id in valid_components:
        endpoints = get_component_endpoints(skeleton, labels, comp_id)
        for ep in endpoints:
            dist = np.sqrt((ep[0] - hole_center[0])**2 + (ep[1] - hole_center[1])**2)
            if dist < min_dist_to_hole:
                min_dist_to_hole = dist
                end_component = comp_id
                end_point = ep
    
    ordered_components = [end_component]
    remaining = set(valid_components) - {end_component}
    
    path_in_comp, current_exit_point = trace_single_component(
        skeleton, labels, end_component, end_point
    )
    
    full_path = path_in_comp.copy()
    connected_skeleton = skeleton.copy()
    
    while remaining:
        nearest_comp, nearest_ep, dist = find_nearest_component(
            current_exit_point, remaining, labels, skeleton
        )
        
        if nearest_comp is None or dist > max_gap:
            break
        
        cv2.line(connected_skeleton, current_exit_point, nearest_ep, 255, 1)
        
        connecting_points = generate_line_points(current_exit_point, nearest_ep)
        full_path.extend(connecting_points)
        
        ordered_components.append(nearest_comp)
        remaining.remove(nearest_comp)
        
        path_in_comp, current_exit_point = trace_single_component(
            skeleton, labels, nearest_comp, nearest_ep
        )
        full_path.extend(path_in_comp)
    
    start_point = current_exit_point
    return start_point, end_point, full_path, connected_skeleton

def generate_line_points(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    distance = int(np.sqrt((x2 - x1)**2 + (y2 - y1)**2))
    if distance <= 1:
        return [p1, p2]
    points = []
    for i in range(distance + 1):
        ratio = i / distance
        x = int(x1 * (1 - ratio) + x2 * ratio)
        y = int(y1 * (1 - ratio) + y2 * ratio)
        points.append((x, y))
    return points

# ==================== main function ====================

def solve_zuma_path(img, config):

    if img is None: return None
    
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]

    if 'ui_masks_pct' in config:
        config['ui_masks'] = [(int(x1*w), int(y1*h), int(x2*w), int(y2*h)) 
                             for (x1, y1, x2, y2) in config['ui_masks_pct']]
    
    hole_center = find_finish_hole_improved(img, config)
    if hole_center is None: return None
    
    raw_mask = get_combined_mask_improved(img, config)
    
    clean_mask = clean_mask_morphology(raw_mask, config)
    
    h, w = clean_mask.shape[:2]
    for (rx1, ry1, rx2, ry2) in config.get('ui_masks_pct', []):
        ix1, iy1 = int(rx1 * w), int(ry1 * h)
        ix2, iy2 = int(rx2 * w), int(ry2 * h)
        cv2.rectangle(clean_mask, (ix1, iy1), (ix2, iy2), 0, -1) # تصفير إجباري
    # -------------------------------------------------------------

    skel_bool = skeletonize(clean_mask > 0)
    skeleton = (skel_bool * 255).astype(np.uint8)
    skeleton = remove_noise_by_area(skeleton, min_area=30)
    
    start_point, end_point, full_path, connected_skeleton = order_all_segments(
        skeleton, hole_center, max_gap=config.get('max_gap', 100)
    )
    
    result = img_rgb.copy()
    thick_skel = cv2.dilate(connected_skeleton, np.ones((2, 2), np.uint8), iterations=1)
    result[thick_skel > 0] = [0, 255, 0]
    
    cv2.circle(result, hole_center, 15, (255, 255, 0), 3)
    cv2.putText(result, "HOLE", (hole_center[0] + 20, hole_center[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    if end_point:
        cv2.circle(result, end_point, 12, (255, 0, 0), -1)
        cv2.putText(result, "END", (end_point[0] + 15, end_point[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    
    if start_point:
        cv2.circle(result, start_point, 12, (0, 100, 255), -1)
        cv2.putText(result, "START", (start_point[0] + 15, start_point[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 100, 255), 2)
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    axes[0].imshow(img_rgb)
    axes[0].set_title("Original Image")
    
    axes[1].imshow(clean_mask, cmap='gray')
    axes[1].set_title("Cleaned Mask")
    
    axes[2].imshow(result)
    axes[2].set_title(f"Final Path: {len(full_path)} pixels" if full_path else "Final Path")
    
    for ax in axes:
        ax.axis('off')
    
    plt.tight_layout()
    plt.show()
    
    return {
        'start': start_point,
        'end': end_point,
        'hole': hole_center,
        'path': full_path
    }

def print_path_coordinates(result, label):
    if result and result['path']:
        ordered_path = result['path'][::-1]
        print(f"Total Points: {len(ordered_path)}")
        print(f"Start Point: {ordered_path[0]}")
        print(f"Sample Path: {ordered_path[:5]} ... {ordered_path[len(ordered_path)//2]} ... {ordered_path[-5:]}")
        print(f"End Point: {ordered_path[-1]}")
    else:
        print(f"No path found for {label}")

# ==================== config ====================

ZUMA_DELUXE_CONFIG = {
    'path_hsv_low': [0, 0, 40],
    'path_hsv_high': [180, 80, 140],
    'sat_threshold': 60,
    'val_low': 20,
    'val_high': 170,
    'hole_thresh': 35,
    'gold_hsv_low': [15, 100, 100],  
    'gold_hsv_high': [35, 255, 255],
    'max_gap': 200,
    'min_noise_area': 500,
    'min_component_area': 1000,
    'border_size': 10,
    'ui_masks': [(0, 0, 160, 80), (800, 0, 1000, 80)],
    'frog_center_mask': None,
    'remove_frog_auto': True
}

ZUMA_GREEN_JUNGLE_CONFIG = {
    'path_hsv_low': [85, 30, 15],
    'path_hsv_high': [130, 170, 180],
    'sat_threshold': 80,
    'val_low': 10,
    'val_high': 180,
    'gold_hsv_low': [18, 180, 150], 
    'gold_hsv_high': [26, 255, 255],
    'max_gap': 200,
    'min_noise_area': 300,
    'min_component_area': 50,
    'border_size': 10,
    'ui_masks_pct': [
    (0.0, 0.0, 1.0, 0.18),  
    (0.80, 0.0, 1.0, 0.25), 
    (0.0, 0.85, 1.0, 1.0),  
    (0.96, 0.0, 1.0, 1.0), 
    (0.0, 0.0, 0.04, 1.0)   
],
    'remove_frog_auto': False,
}

ZUMA_SPACE_CONFIG = {
    'path_hsv_low': [105, 80, 150],    
    'path_hsv_high': [120, 230, 255],  
    'sat_threshold': 30,     
    'val_low': 150,          
    'val_high': 255,          
    'hole_thresh': 100,      
    'max_gap': 100,           
    'ui_masks_pct': [
        (0.0, 0.0, 1.0, 0.20), 
        (0.70, 0.0, 1.0, 1.0), 
        (0.0, 0.0, 0.05, 1.0),
        (0.0, 0.92, 1.0, 1.0)
    ],
    'min_noise_area': 300,   
    'min_component_area': 150,
}

