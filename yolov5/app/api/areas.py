from flask import Blueprint, request, jsonify
from app.models.database import get_conn

bp = Blueprint('areas', __name__)

@bp.route("/areas", methods=["POST"])
def api_create_area():
    data = request.json
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO areas (code, name, description)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (data.get("code"), data.get("name"), data.get("description")))
            new_id = cur.fetchone()[0]
    conn.close()
    return jsonify({"id": new_id, "message": "Area created successfully"}), 201

@bp.route("/areas/<int:area_id>", methods=["PUT"])
def api_update_area(area_id):
    data = request.json or {}

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            # Lấy bản ghi cũ
            cur.execute("SELECT code, name, description FROM areas WHERE id = %s", (area_id,))
            old = cur.fetchone()
            if not old:
                conn.close()
                return jsonify({"error": "Area not found"}), 404

            # Giữ lại giá trị cũ nếu không có field trong request
            code = data.get("code", old[0])
            name = data.get("name", old[1])
            description = data.get("description", old[2])

            cur.execute("""
                UPDATE areas
                SET code = %s, name = %s, description = %s
                WHERE id = %s
            """, (code, name, description, area_id))
        conn.commit()
    conn.close()

    return jsonify({"message": "Area updated successfully"})

@bp.route("/areas/<int:area_id>", methods=["DELETE"])
def api_delete_area(area_id):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM areas WHERE id = %s", (area_id,))
    conn.close()
    return jsonify({"message": "Area deleted successfully"})

@bp.route("/areas", methods=["GET"])
def api_get_areas():
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, description FROM areas ORDER BY id")
            rows = cur.fetchall()
    return jsonify([{"id": r[0], "name": r[1], "description": r[2]} for r in rows])

@bp.route("/areas/<int:area_id>/cameras", methods=["GET"])
def get_cameras_by_area(area_id):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT camera_id, name, rtsp_url, location, status
            FROM cameras
            WHERE area_id = %s
        """, (area_id,))
        rows = cur.fetchall()
    return jsonify([
        {
            "camera_id": r[0],
            "name": r[1],
            "rtsp_url": r[2],
            "location": r[3],
            "status": r[4]
        } for r in rows
    ])

@bp.route("/api/config/areas/<int:area_id>", methods=["GET"])
def api_get_area_config(area_id):
    from app.utils.config import sync_current_config
    cfg = sync_current_config()
    area_cfg = cfg.get("areas", {}).get(str(area_id), {"enabled_events": []})
    return jsonify(area_cfg)

@bp.route("/api/config/areas/<int:area_id>", methods=["PUT"])
def api_save_area_config(area_id):
    """Lưu và merge cấu hình khu vực (sự kiện + vùng vẽ)."""
    from app.utils.config import CURRENT_CONFIG, save_config
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Missing payload"}), 400

        area_key = str(area_id)
        CURRENT_CONFIG.setdefault("areas", {})
        existing_cfg = CURRENT_CONFIG["areas"].get(area_key, {})

        # 🧩 Merge cấu trúc sự kiện
        enabled_events = data.get("enabled_events", existing_cfg.get("enabled_events", []))

        # 🧩 Merge cấu trúc cameras
        existing_cameras = existing_cfg.get("cameras", {})
        new_cameras = data.get("cameras", {})

        merged_cameras = {**existing_cameras, **new_cameras}

        # 🧩 Merge vùng vẽ chung
        draw_areas = data.get("draw_areas", existing_cfg.get("draw_areas", []))

        # ✅ Ghi lại dữ liệu hợp nhất
        CURRENT_CONFIG["areas"][area_key] = {
            **existing_cfg,
            **data,
            "enabled_events": enabled_events,
            "cameras": merged_cameras,
            "draw_areas": draw_areas
        }

        # Ghi file
        save_config(CURRENT_CONFIG)

        print(f"💾 [CONFIG SAVED] Area {area_id} updated with {len(draw_areas)} draw area(s)")
        return jsonify({"status": "ok", "area_id": area_id})

    except Exception as e:
        import traceback
        print("[SAVE CONFIG ERROR]", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500