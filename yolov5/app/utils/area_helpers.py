import os
import json
from app.models.database import get_area_by_camera as db_get_area_by_camera
from app.utils.config import CURRENT_CONFIG, is_event_allowed as config_is_event_allowed

def get_draw_areas_for_area(area_id):
    """Lấy danh sách vùng vẽ (normalized) cho khu vực."""
    cfg = CURRENT_CONFIG.get("areas", {})
    entry = cfg.get(str(area_id)) or {}
    return entry.get("draw_areas") or []

def bbox_intersects_rect(bbox, rect_px):
    """Kiểm tra phần trăm giao nhau giữa bbox và vùng vẽ (pixel)."""
    x1, y1, x2, y2 = bbox
    rx1 = rect_px['x']
    ry1 = rect_px['y']
    rx2 = rx1 + rect_px['w']
    ry2 = ry1 + rect_px['h']

    inter_x1 = max(x1, rx1)
    inter_y1 = max(y1, ry1)
    inter_x2 = min(x2, rx2)
    inter_y2 = min(y2, ry2)

    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    bbox_area = max((x2 - x1) * (y2 - y1), 1)
    return inter_area / bbox_area

def bbox_overlaps_any(bbox, draw_areas_norm, W, H, min_fraction=0.05):
    """Kiểm tra bbox có giao với bất kỳ vùng vẽ nào không."""
    for r in draw_areas_norm:
        rect_px = {
            'x': int(r['x'] * W),
            'y': int(r['y'] * H),
            'w': int(r['w'] * W),
            'h': int(r['h'] * H),
        }
        if bbox_intersects_rect(bbox, rect_px) >= min_fraction:
            return True
    return False

def get_area_by_camera(camera_id):
    """Lấy area_id từ bảng cameras (wrapper)"""
    return db_get_area_by_camera(camera_id)

def is_event_enabled(area_id, event_name: str) -> bool:
    """Kiểm tra sự kiện có được bật trong khu vực không"""
    cfg = CURRENT_CONFIG
    print(f"[DEBUG] Check event {event_name} in area {area_id}")
    print(json.dumps(cfg.get("areas", {}), indent=2, ensure_ascii=False))
    try:
        return event_name in cfg.get("areas", {}).get(str(area_id), {}).get("enabled_events", [])
    except Exception as e:
        print("[DEBUG ERROR]", e)
        return False

def is_event_allowed(area_id, event_name):
    """Kiểm tra sự kiện có được phép theo thời gian cấu hình không (wrapper)"""
    return config_is_event_allowed(area_id, event_name)