import os
import json
from datetime import datetime

# Configuration constants
CONFIG_FILE = "config.json"

# Default configuration
DEFAULT_CONFIG = {
    "system": {
        "recognition_interval": 0.1,
        "cooldown": 15,
        "video_duration": 15,
        "compare_tolerance": 0.45,
    },
    "events": {
        "face_recognition": True,
        "smoking": True,
        "violence": False,
        "checkincheckout": True,
        "person_detection": True,
        "scan_qr": True
    },
    "areas": {}
}

DEFAULT_EVENTS = {
    "face_recognition": True,
    "smoking": True,
    "violence": False,
    "checkincheckout": True,
    "person_detection": True,
    "scan_qr": True
}

# Global config
CURRENT_CONFIG = DEFAULT_CONFIG.copy()

def load_config():
    """Đọc file config.json"""
    global CURRENT_CONFIG
    if not os.path.exists(CONFIG_FILE):
        # ✅ Nếu file chưa tồn tại — tạo mới với cấu hình mặc định
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(CURRENT_CONFIG, f, indent=2, ensure_ascii=False)
        return CURRENT_CONFIG

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # ✅ Nếu thiếu trường "events" thì thêm mặc định
    if "events" not in cfg:
        cfg["events"] = {
            "face_recognition": True,
            "smoking": True,
            "violence": False,
            "checkincheckout": True,
            "person_detection": True,
            "scan_qr": True
        }

    CURRENT_CONFIG = cfg
    return cfg

def save_config(cfg):
    """Lưu file config.json"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def sync_current_config():
    """Đồng bộ config từ file"""
    global CURRENT_CONFIG
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                CURRENT_CONFIG = json.load(f)
        else:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(CURRENT_CONFIG, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[CONFIG LOAD ERROR]", e)
    return CURRENT_CONFIG

def save_current_config():
    """Ghi lại file config.json"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CURRENT_CONFIG, f, ensure_ascii=False, indent=2)

def apply_all_configs():
    """Áp dụng toàn bộ cấu hình cho hệ thống"""
    for area_id in CURRENT_CONFIG.get("areas", {}):
        apply_area_config(int(area_id))
    print("✅ [APPLY ALL CONFIG] Tất cả cấu hình khu vực đã được cập nhật realtime.")
    return True

def apply_area_config(area_id: int):
    """Áp dụng cấu hình khu vực realtime"""
    area_cfg = CURRENT_CONFIG.get("areas", {}).get(str(area_id))
    if not area_cfg:
        print(f"[⚠️ APPLY AREA] Không tìm thấy cấu hình cho khu vực {area_id}")
        return False
    print(f"✅ [APPLY AREA CONFIG] Khu vực {area_id} đã được áp dụng realtime.")
    return True

def is_event_allowed(area_id, event_name):
    """Kiểm tra sự kiện có được phép theo thời gian cấu hình không"""
    area_cfg = CURRENT_CONFIG.get("areas", {}).get(str(area_id), {})
    schedules = area_cfg.get("event_schedules", {})

    # Nếu chưa cấu hình thì mặc định cho phép
    if event_name not in schedules:
        return True

    cfg = schedules[event_name]
    if not cfg.get("enabled", True) or not cfg.get("allowed", True):
        return False

    # kiểm tra thời gian trong ngày
    now = datetime.now().strftime("%H:%M")
    start = cfg.get("start", "00:00")
    end = cfg.get("end", "23:59")

    return start <= now <= end