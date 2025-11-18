from flask import Blueprint, request, jsonify, Response, send_from_directory
from queue import Empty
import json
import time
import os
from app.models.database import get_conn, delete_event_db, delete_all_events_db
from app.globals import event_broadcast_queue

bp = Blueprint('events', __name__)

@bp.route("/events", methods=["GET"])
def api_list_events():
    limit = int(request.args.get("limit", 500))
    offset = int(request.args.get("offset", 0))
    area_id = request.args.get("area_id") 

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            query = """
                SELECT e.id::text,
                       e.person_id,
                       COALESCE(p.name, 'Không rõ') AS name,
                       e.camera_id,
                       e.label,
                       e.time,
                       e.image_url,
                       e.video_url,
                       a.id AS area_id,
                       a.name AS area_name
                FROM events e
                LEFT JOIN persons p ON e.person_id = p.person_id
                LEFT JOIN cameras c ON e.camera_id = c.camera_id
                LEFT JOIN areas a ON c.area_id = a.id   
            """

            params = []
            if area_id:
                query += " WHERE a.id = %s"
                params.append(area_id)

            query += " ORDER BY e.time DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cur.execute(query, params)
            rows = cur.fetchall()

        conn.close()

        return jsonify([
            {
                "id": r[0],
                "person_id": r[1],
                "name": r[2],
                "camera_id": r[3],
                "label": r[4],
                "time": r[5].isoformat() if r[5] else None,
                "image_url": r[6],
                "video_url": r[7],
                "area_id": r[8],
                "area_name": r[9],
            } for r in rows
        ])

    except Exception as e:
        print("[EVENTS API ERROR]", e)
        return jsonify({"error": str(e)}), 500

@bp.route('/events/stream')
def stream_events():
    def generate():
        while True:
            try:
                event = event_broadcast_queue.get(timeout=2)
                yield f"data: {json.dumps(event)}\n\n"
            except Empty:
                yield ":\n\n"
                time.sleep(1)
    return Response(generate(), mimetype='text/event-stream')

@bp.route("/events/count", methods=["GET"])
def api_events_count():
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM events")
            count = cur.fetchone()[0]
    return jsonify({"count": count})

@bp.route("/events/<event_id>", methods=["DELETE"])
def api_delete_event_api(event_id):
    deleted = delete_event_db(event_id)
    return jsonify({"deleted": deleted})

@bp.route("/events/deleteall", methods=["DELETE"])
def api_delete_all_events_api():
    deleted = delete_all_events_db()
    return jsonify({"deleted": deleted})

@bp.route("/api/events/camera/<int:camera_id>", methods=["GET"])
def get_camera_events(camera_id):
    date = request.args.get("date")

    query = """
        SELECT id::text, label, time, video_url, image_url, camera_id,
               time AS start_time, time + interval '30 seconds' AS end_time
        FROM events
        WHERE camera_id = %s
          AND video_url IS NOT NULL
    """

    params = [camera_id]

    # Nếu có tham số ngày -> lọc theo ngày
    if date:
        query += " AND DATE(time) = %s"
        params.append(date)

    query += " ORDER BY time ASC"

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
    conn.close()

    # Chuyển kết quả về JSON
    return jsonify([
        {
            "id": r[0],
            "label": r[1],
            "time": r[2].isoformat(),
            "video_url": f"http://localhost:5000{r[3]}" if r[3] and r[3].startswith("/static/") else r[3],
            "image_url": r[4],
            "camera_id": r[5],
            "start_time": r[6].isoformat() if r[6] else None,
            "end_time": r[7].isoformat() if r[7] else None
        }
        for r in rows
    ])

@bp.route('/static/events/<path:filename>')
def serve_event_media(filename):
    """Phục vụ file ảnh/video trong thư mục static/events."""
    import os
    events_dir = os.path.join(os.path.dirname(__file__), "..", "..", "static", "events")
    file_path = os.path.join(events_dir, filename)
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(events_dir, filename)