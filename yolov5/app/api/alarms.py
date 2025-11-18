from flask import Blueprint, request, jsonify
from app.utils.config import load_config, save_config, apply_all_configs
from app.utils.audio import play_audio_alarm

bp = Blueprint('alarms', __name__)

# API/Alarm
@bp.route("/api/alarm-config/<int:area_id>/<int:camera_id>", methods=["GET"])
def api_get_alarm_config(area_id, camera_id):
    cfg = load_config()
    area_cfg = cfg.get("areas", {}).get(str(area_id), {})
    result = {
        "arming_schedule": area_cfg.get("arming_schedule", []),
        "linkage": area_cfg.get("linkage", {}),
        "event_schedules": area_cfg.get("event_schedules", {}),
    }
    return jsonify(result)

# lưu cấu hình alarm
@bp.route("/api/alarm-config", methods=["POST"])
def api_save_alarm_config():
    data = request.json or {}
    cfg = load_config()

    area_id = str(data.get("area_id"))
    if not area_id:
        return jsonify({"status": "error", "msg": "Missing area_id"}), 400

    if "areas" not in cfg:
        cfg["areas"] = {}

    if area_id not in cfg["areas"]:
        cfg["areas"][area_id] = {}

    # Gộp dữ liệu gửi từ frontend
    if "arming_schedule" in data:
        cfg["areas"][area_id]["arming_schedule"] = data["arming_schedule"]
    if "linkage" in data:
        cfg["areas"][area_id]["linkage"] = data["linkage"]
    if "event_schedules" in data:
        cfg["areas"][area_id]["event_schedules"] = data["event_schedules"]

    save_config(cfg)
    apply_all_configs()

    print(f"💾 [CONFIG] Saved alarm config for area {area_id}")
    return jsonify({"status": "ok", "area_id": area_id})

# lưu cấu hình
CURRENT_ALARM_SCHEDULES = {}
@bp.route("/api/alarm-config/apply/<int:area_id>", methods=["POST"])
def apply_realtime_config(area_id):
    """Áp dụng toàn bộ event_schedules realtime"""
    data = request.get_json()
    schedules = data.get("schedules", [])

    from app.utils.config import CURRENT_CONFIG
    CURRENT_CONFIG.setdefault("areas", {})
    CURRENT_CONFIG["areas"].setdefault(str(area_id), {})
    CURRENT_CONFIG["areas"][str(area_id)]["event_schedules"] = {
        e["event"]: {
            "start": e["start"],
            "end": e["end"],
            "enabled": e["enabled"],
            "allowed": e.get("allowed", True)
        }
        for e in schedules
    }

    # ✅ cập nhật bộ nhớ realtime
    CURRENT_ALARM_SCHEDULES[area_id] = schedules
    print(f"✅ [REALTIME APPLIED] Area {area_id} updated with {len(schedules)} schedules")

    return jsonify({"status": "applied", "count": len(schedules)})

@bp.route("/api/alarm/play-audio", methods=["POST"])
def api_play_audio_alarm():
    """Phát âm thanh cảnh báo"""
    def _play():
        try:
            play_audio_alarm()
        except Exception as e:
            print("[AUDIO ALERT ERR]", e)

    import threading
    threading.Thread(target=_play, daemon=True).start()
    return jsonify({"ok": True, "message": "Playing alarm sound"})