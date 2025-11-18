from flask import Blueprint, request, jsonify
from app.utils.config import CURRENT_CONFIG, load_config, save_config, apply_all_configs

bp = Blueprint('config', __name__)

@bp.route("/api/config", methods=["GET"])
def api_get_config():
    return jsonify(load_config())

@bp.route("/api/config", methods=["POST"])
def api_save_config():
    data = request.json or {}
    CURRENT_CONFIG.update(data)
    save_config(CURRENT_CONFIG)
    return jsonify({"status": "ok", "config": CURRENT_CONFIG})

@bp.route("/api/config/event_schedule", methods=["POST"])
def api_update_event_schedule():
    """Cập nhật khung giờ cho phép sự kiện theo khu vực hoặc toàn hệ thống"""
    data = request.json or {}
    event_schedules = data.get("event_schedules", {})
    area_id = data.get("area_id")
    apply_realtime = data.get("apply_realtime", False)

    cfg = load_config()
    if not area_id:
        # Nếu không có area_id, cập nhật vào system-level
        cfg.setdefault("system", {})
        cfg["system"]["event_schedules"] = event_schedules
        print("🌐 [CONFIG] Updated global event schedule.")
    else:
        area_id = str(area_id)
        cfg.setdefault("areas", {})
        cfg["areas"].setdefault(area_id, {})
        cfg["areas"][area_id]["event_schedules"] = event_schedules
        print(f"🏠 [CONFIG] Updated event schedule for area {area_id}")

    save_config(cfg)

    if apply_realtime:
        apply_all_configs()
        print("⚡ [REALTIME] Event schedule applied immediately.")

    return jsonify({"status": "ok", "applied": apply_realtime})