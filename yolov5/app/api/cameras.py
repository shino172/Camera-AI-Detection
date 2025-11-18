from flask import Blueprint, request, jsonify, Response
import time
from app.models.database import get_conn
from app.threads.camera_thread import add_camera, stop_camera, switch_camera, cameras
from app.globals import face_results, alert_frames, last_pose_result
from app.utils.video_processing import process_and_encode_frame

bp = Blueprint('cameras', __name__)

@bp.route("/api/cameras", methods=["POST"])
def api_create_camera():
    data = request.json
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cameras (name, nvr_id, channel, area_id, rtsp_url, location, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING camera_id, rtsp_url
            """, (
                data["name"],
                data["nvr_id"],
                data["channel"],
                data["area_id"],
                data["rtsp_url"],
                data.get("location"),
                data.get("status", "active")
            ))
            result = cur.fetchone()
            cam_id, rtsp_url = result[0], result[1]
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("[ERROR] ❌ Failed to insert camera:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

    # ✅ Khởi tạo camera mới nếu chưa có trong hệ thống
    if cam_id not in cameras and rtsp_url:
        try:
            add_camera(cam_id, rtsp_url)
            print(f"[HOT-ADD] 🚀 Started new camera {cam_id} ({rtsp_url})")
        except Exception as e:
            print(f"[HOT-ADD] ❌ Failed to start camera {cam_id}:", e)
            return jsonify({
                "camera_id": cam_id,
                "message": "Camera added to DB, but failed to start thread",
                "error": str(e)
            }), 500

    return jsonify({
        "camera_id": cam_id,
        "message": "Camera created and started successfully"
    }), 201

@bp.route("/api/cameras/<int:camera_id>", methods=["PUT"])
def api_update_camera(camera_id):
    data = request.json
    conn = get_conn()

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE cameras
                    SET name=%s, nvr_id=%s, channel=%s, area_id=%s, rtsp_url=%s, status=%s
                    WHERE camera_id=%s
                """, (
                    data["name"],
                    data["nvr_id"],
                    data["channel"],
                    data["area_id"],
                    data["rtsp_url"],
                    data.get("status", "active"),
                    camera_id
                ))
            conn.commit()
    finally:
        conn.close()

    # ✅ Sau khi DB cập nhật — restart thread camera nếu có
    if camera_id in cameras:
        try:
            stop_camera(camera_id)
            print(f"[RELOAD] 🔁 Stopped old camera {camera_id}")
        except Exception as e:
            print(f"[RELOAD ERROR] {e}")

    try:
        # khởi động lại camera thread mới với rtsp_url mới
        rtsp_url = data["rtsp_url"]
        add_camera(camera_id, rtsp_url)
        print(f"[RELOAD] 🚀 Restarted camera {camera_id} with new RTSP {rtsp_url}")
    except Exception as e:
        print(f"[RELOAD ERROR] Failed to restart camera {camera_id}: {e}")

    return jsonify({"message": "Camera updated and reloaded successfully"})

@bp.route("/api/cameras/<int:camera_id>", methods=["DELETE"])
def api_delete_camera(camera_id):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cameras WHERE camera_id=%s", (camera_id,))
    conn.close()
    
    # Stop camera thread if running
    if camera_id in cameras:
        stop_camera(camera_id)
        
    return jsonify({"message": "Camera deleted successfully"})

@bp.route("/api/cameras", methods=["GET"])
def api_get_cameras():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                c.camera_id,
                c.name,
                c.nvr_id,
                n.name AS nvr_name,
                c.area_id,
                a.name AS area_name,
                c.channel,
                c.rtsp_url,
                c.location,
                c.status
            FROM cameras c
            LEFT JOIN areas a ON c.area_id = a.id
            LEFT JOIN nvrs n ON c.nvr_id = n.id
            ORDER BY c.camera_id;
        """)
        rows = cur.fetchall()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "name": r[1],
            "nvr_id": r[2],
            "nvr_name": r[3],
            "area_id": r[4],
            "area_name": r[5],
            "channel": r[6],
            "rtsp_url": r[7],
            "location": r[8],
            "status": r[9]
        }
        for r in rows
    ])

@bp.route("/api/cameras/<int:camera_id>/status", methods=["PUT"])
def api_toggle_camera_status(camera_id):
    """Bật hoặc tắt camera theo trạng thái"""
    data = request.get_json()
    new_status = data.get("status")  # 'active' hoặc 'inactive'

    if new_status not in ["active", "inactive"]:
        return jsonify({"error": "Invalid status"}), 400

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE cameras SET status=%s WHERE camera_id=%s", (new_status, camera_id))
        conn.commit()
    conn.close()

    # ===== Quản lý thread camera =====
    if new_status == "inactive":
        # 🔴 Dừng camera
        if camera_id in cameras:
            try:
                stop_camera(camera_id)
                print(f"[STOPPED] 🛑 Camera {camera_id} stopped manually.")
            except Exception as e:
                print(f"[STOP ERROR] {e}")
        else:
            print(f"[INFO] Camera {camera_id} is already inactive.")
    else:
        # 🟢 Bật lại camera
        try:
            # Lấy RTSP URL từ DB
            conn = get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT rtsp_url FROM cameras WHERE camera_id=%s", (camera_id,))
                row = cur.fetchone()
            conn.close()

            if row and row[0]:
                rtsp_url = row[0]
                add_camera(camera_id, rtsp_url)
                print(f"[STARTED] 🚀 Camera {camera_id} started with {rtsp_url}")
            else:
                print(f"[ERROR] No RTSP URL for camera {camera_id}")
        except Exception as e:
            print(f"[START ERROR] {e}")

    return jsonify({"message": f"Camera {camera_id} set to {new_status}"})

@bp.route("/video_feed/<int:camera_id>")
def video_feed(camera_id):
    """API stream video MJPEG cho 1 camera"""
    from app.threads.camera_thread import cameras
    
    if camera_id not in cameras:
        return "Camera not found", 404
        
    def generate():
        while True:
            if camera_id not in cameras:
                time.sleep(0.1)
                continue
            frame = cameras[camera_id].latest_frame
            if frame is None:
                time.sleep(0.01)
                continue
            yield process_and_encode_frame(frame.copy(), camera_id, face_results, alert_frames, last_pose_result)
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')