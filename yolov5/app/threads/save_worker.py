import queue
import os
import cv2
import base64
import uuid
from datetime import datetime
import pytz
from app.models.database import save_event_to_db, get_area_by_camera, get_area_name, update_event_media
from app.utils.video_processing import save_violation_clip
from app.utils.drawing import draw_label_with_bg
from app.globals import save_queue, event_broadcast_queue, frame_buffers, camera_queues

def save_worker():
    """
    save_queue items:
      ("image", {"frame": frame, "bbox": (x1,y1,x2,y2), "event": event, "path": path, "display_label": str})
      ("video", {"frames": frames, "W": W, "H": H, "path": path, "event": event})
    """
    while True:
        job = save_queue.get()
        if job is None:
            break
        kind, data = job
        try:
            if kind == "video":
                if "frames" in data and data["frames"]:
                    save_violation_clip(data["event"], data["frames"][0], frame_buffers, camera_queues)
                else:
                    print("[WARN] Không có frames hợp lệ để lưu video.")
                event_broadcast_queue.put(data["event"])

            elif kind == "image":
                try:
                    frame_hi = data["frame"].copy()
                    x1, y1, x2, y2 = map(int, data["bbox"])
                    cv2.rectangle(frame_hi, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    if data.get("display_label"):
                        draw_label_with_bg(frame_hi, data["display_label"], (x1, max(30, y1 - 8)))

                    filename = data["path"]
                    local_path = os.path.join("static", "events", filename)
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    cv2.imwrite(local_path, frame_hi)

                    image_url = f"/static/events/{filename}"
                    data["event"]["image_path"] = image_url
                    data["event"]["image_url"] = f"http://localhost:5000{image_url}"
                    
                    area_id = get_area_by_camera(data["event"].get("camera_id"))
                    area_name = get_area_name(area_id)

                    data["event"]["area_id"] = area_id
                    data["event"]["area_name"] = area_name

                    save_event_to_db(data["event"])
                    event_broadcast_queue.put(data["event"])

                    print(f"[LOCAL IMAGE SAVED] {image_url}")

                except Exception as e:
                    print("[SAVE IMAGE ERROR]", e)

        except Exception as e:
            print("[SAVE ERROR]", e)