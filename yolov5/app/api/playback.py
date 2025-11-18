from flask import Blueprint, request, jsonify
from app.models.database import get_conn
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
from datetime import timedelta

bp = Blueprint('playback', __name__)

@bp.route("/api/playback/<string:event_id>", methods=["GET"])
def api_get_playback(event_id):
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT video_url, time FROM events WHERE id = %s", (event_id,))
            row = cur.fetchone()
        conn.close()

        if not row or not row[0]:
            return jsonify({"error": "Không tìm thấy video"}), 404
        event_time = row[1]
        event_time = event_time.astimezone(pytz.timezone('Asia/Ho_Chi_Minh'))
        video_url = row[0]
        if video_url.startswith("/static/"):
            video_url = f"http://localhost:5000{video_url}"

        return jsonify({
            "event_time": event_time.isoformat(),
            "playback_url": video_url
            })
    except Exception as e:
        print("[API ERROR] /api/playback/<id>", e)
        return jsonify({"error": str(e)}), 500
    
@bp.route("/api/playback_segments/<int:camera_id>", methods=["GET"])
def api_get_playback_segments(camera_id):
    date = request.args.get("date")
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id::text, start_time, end_time, video_url
                FROM events
                WHERE camera_id = %s 
                  AND start_time::date = %s
                  AND video_url IS NOT NULL
                ORDER BY start_time
            """, (camera_id, date))
            rows = cur.fetchall()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "start_time": r[1].isoformat(),
            "end_time": r[2].isoformat(),
            "video_url": f"http://localhost:5000{r[3]}" if r[3].startswith("/static/") else r[3]
        } for r in rows
    ])

@bp.route("/api/nvrs/<int:nvr_id>/authenticate", methods=["POST"])
def api_authenticate_nvr(nvr_id):
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Thiếu username hoặc password"}), 400

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT username, password FROM nvrs WHERE id = %s
        """, (nvr_id,))
        row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Không tìm thấy đầu ghi"}), 404

    db_user, db_pass = row

    # 🔒 So sánh username bình thường, password thì check hash
    if username == db_user and check_password_hash(db_pass, password):
        print(f"[✅ LOGIN SUCCESS] NVR {nvr_id}: {username}")
        return jsonify({"message": "Đăng nhập thành công"}), 200
    else:
        print(f"[❌ LOGIN FAILED] NVR {nvr_id}: sai tài khoản hoặc mật khẩu")
        return jsonify({"error": "Sai tài khoản hoặc mật khẩu"}), 401