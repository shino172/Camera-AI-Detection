from flask import Blueprint, jsonify, request
from ..db import get_conn
from ..threads.camera_thread import CameraThread
from ..config import VIDEO_BUFFER_SECONDS, VIDEO_AFTER_SECONDS, FPS
from collections import deque
import queue


cameras_bp = Blueprint('cameras', __name__)


cameras = {}
camera_queues = {}
frame_buffers = {}


@cameras_bp.route("/", methods=["GET"])
def list_cameras():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT camera_id, name, rtsp_url, area_id, status FROM cameras ORDER BY camera_id")
    rows = cur.fetchall()
    conn.close()
    return jsonify([
    {"camera_id": r[0], "name": r[1], "rtsp_url": r[2], "area_id": r[3], "status": r[4]} for r in rows
    ])


@cameras_bp.route("/", methods=["POST"])
def add_camera():
    data = request.get_json()
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
        INSERT INTO cameras (name, nvr_id, channel, area_id, rtsp_url, location, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING camera_id, rtsp_url
        """, (data["name"], data.get("nvr_id"), data.get("channel"), data.get("area_id"), data.get("rtsp_url"), data.get("location"), data.get("status", "active")))
        new_id, rtsp_url = cur.fetchone()
    conn.commit()
    conn.close()

    if rtsp_url:
        cam = CameraThread(camera_id=new_id, src=rtsp_url)
        cameras[new_id] = cam
        camera_queues[new_id] = queue.Queue(maxsize=1)
        frame_buffers[new_id] = deque(maxlen=(VIDEO_BUFFER_SECONDS + VIDEO_AFTER_SECONDS) * FPS)
        cam.start()

    return jsonify({"camera_id": new_id, "message": "Camera added and started"}), 201

@cameras_bp.route("/<int:camera_id>", methods=["DELETE"])
def delete_camera(camera_id):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM cameras WHERE camera_id=%s", (camera_id,))
    conn.commit()
    conn.close()

    if camera_id in cameras:
        cameras[camera_id].stop()
        del cameras[camera_id]

    return jsonify({"message": f"Camera {camera_id} deleted"})