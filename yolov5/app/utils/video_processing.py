import cv2, queue
import os
import base64
import uuid, time
from datetime import datetime
import pytz
from queue import Empty
from app.models.database import update_event_media
from app.utils.drawing import draw_label_with_bg

# Video configuration
VIDEO_BUFFER_SECONDS = 5
VIDEO_AFTER_SECONDS = 25
VIDEO_FPS = 20
VIDEO_PATH = os.path.join(os.getcwd(), "static", "events")

def save_violation_clip(event, current_frame, frame_buffers, camera_queues):
    """Save video clip for violation event"""
    try:
        cam_id = event.get("camera_id")
        if cam_id not in frame_buffers or cam_id not in camera_queues:
            print(f"[WARN] Không tìm thấy buffer/queue cho camera {cam_id}")
            return

        before_frames = list(frame_buffers[cam_id])
        after_frames = []
        start = time.time()

        while time.time() - start < VIDEO_AFTER_SECONDS:
            try:
                frm = camera_queues[cam_id].get(timeout=0.05)
                after_frames.append(frm.copy())
            except queue.Empty:
                continue

        all_frames = before_frames + [current_frame.copy()] + after_frames
        if not all_frames:
            print("[SAVE CLIP WARN] Không có frame để lưu video")
            return

        h, w = all_frames[0].shape[:2]
        os.makedirs(VIDEO_PATH, exist_ok=True)
        filename = f"{event['id']}.mp4"
        abs_path = os.path.join(VIDEO_PATH, filename)
        bbox = event.get("bbox")
        label = event.get("label", "violation")

        if bbox:
            x1, y1, x2, y2 = map(int, bbox)
            for f in all_frames:
                cv2.rectangle(f, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(f, label.upper(), (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Lưu video
        out = cv2.VideoWriter(abs_path, cv2.VideoWriter_fourcc(*'avc1'), VIDEO_FPS, (w, h))
        for f in all_frames:
            out.write(f)
        out.release()

        rel_path = f"/static/events/{filename}"
        event["video_url"] = rel_path

        # ✅ Snapshot đầu tiên để hiển thị ở frontend
        snapshot = all_frames[0]
        _, buffer = cv2.imencode('.jpg', snapshot)
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        event["image_base64"] = image_base64

        # ✅ Cập nhật DB (có ảnh base64 + video)
        update_event_media(event["id"], video_url=rel_path, image_base64=image_base64)

        print(f"[LOCAL SAVE] Video (cam {cam_id}) saved at {abs_path}")

    except Exception as e:
        print("[SAVE CLIP ERROR]", e)

def gen_frames(rtsp_url):
    """Generate frames from RTSP stream"""
    cap = cv2.VideoCapture(rtsp_url)
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break
        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    cap.release()

def process_and_encode_frame(frame, cam_id, face_results, alert_frames, last_pose_result):
    """Process frame for streaming (draw boxes, labels, etc.)"""
    # draw faces
    for r in face_results:
        if r.get("camera_id") != cam_id:
            continue
        top, right, bottom, left = r["loc"]
        name = r["name"]
        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(frame, name, (left, max(16, top - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # draw alerts
    now = time.time()
    for tid, a in list(alert_frames.items()):
        if a.get("end_time", 0) < now:
            alert_frames.pop(tid, None)
            continue
        x1, y1, x2, y2 = a["bbox"]
        label = a.get("display_label", a.get("label", "ALERT"))
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
        draw_label_with_bg(frame, label, (x1, max(30, y1 - 8)),
                           color=(0, 165, 255), scale=0.6, thickness=1)

    # draw cigarette boxes
    if last_pose_result and last_pose_result.get("cig_boxes"):
        for (cx1, cy1, cx2, cy2) in last_pose_result["cig_boxes"]:
            cv2.rectangle(frame, (cx1, cy1), (cx2, cy2), (255, 0, 0), 2)
            cv2.putText(frame, "cigarette", (cx1, max(30, cy1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

    ok, buf = cv2.imencode('.jpg', frame)
    if ok:
        return (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                + buf.tobytes() + b'\r\n')
    return b''