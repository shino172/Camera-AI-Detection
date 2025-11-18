import time, queue
import threading
import uuid
from app.globals import face_queue, face_results, face_lock, last_recognition_time, last_seen
from app.models.face_recognition import recognize_on_frame, add_pending_face
from app.models.database import get_area_by_camera
from app.utils.area_helpers import get_draw_areas_for_area, bbox_overlaps_any, is_event_allowed
from app.utils.config import CURRENT_CONFIG

# Configuration
RECOGNITION_INTERVAL = 0.1

def log_checkin_checkout(r, frame, camera_id=None):
    """Log checkin/checkout events"""
    global last_seen
    now = time.time()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    name = r.get("name")
    empid = r.get("employee_id")

    if not name or name == "Unknown" or not empid:
        return
    
    # === 1️⃣ Lấy khu vực theo camera
    area_id = get_area_by_camera(camera_id)
    if not area_id:
        print(f"🚫[attendances] Không xác định được khu vực cho camera {camera_id}")
        return

    # === 2️⃣ Kiểm tra khu vực có bật checkin/checkout không
    if not is_event_enabled(area_id, "checkincheckout"):
        print(f"🚫[attendances] Khu vực {area_id} đã tắt sự kiện checkin/checkout")
        return

    day_key = time.strftime("%Y-%m-%d")

    # === 3️⃣ CHECK-IN ===
    if name not in last_seen or last_seen[name].get("day") != day_key:
        ev = {
            "id": str(uuid.uuid4()),
            "camera_id": camera_id,
            "label": "checkin",
            "method": "face_recognition",
            "time": ts,
            "image_url": None,
            "video_url": None,
            "name": name,
            "employee_id": empid,
            "person_id": empid,
        }

        # --- lưu ảnh ---
        img_name = f"checkin_{empid}_{int(now)}.jpg"
        from app.globals import save_queue
        save_queue.put(("image", {
            "frame": frame.copy(),
            "bbox": (r["loc"][3], r["loc"][0], r["loc"][1], r["loc"][2]),
            "event": ev,
            "path": img_name,
            "display_label": "CHECKIN",
        }))
        
        # --- cập nhật ảnh và lưu DB ---
        ev["image_path"] = f"static/events/{img_name}"
        ev["image_url"] = f"http://localhost:5000/{ev['image_path']}"
        from app.models.database import save_event_to_db
        save_event_to_db(ev)

        area_id = get_area_by_camera(camera_id)
        area_name = get_area_name(area_id)

        ev["area_id"] = area_id
        ev["area_name"] = area_name

        # --- phát realtime ---
        from app.globals import event_broadcast_queue
        event_broadcast_queue.put(ev)

        last_seen[name] = {
            "time": now,
            "day": day_key,
            "checked_in": True,
            "checkout": False
        }
        print(f"✅ {name} CHECK-IN tại khu vực {area_id}")

    else:
        # cập nhật thời gian cuối nhìn thấy
        last_seen[name]["time"] = now

    # === 4️⃣ CHECK-OUT ===
    for person, info in list(last_seen.items()):
        if now - info["time"] > 400 and not info.get("checkout"):
            ev = {
                "id": str(uuid.uuid4()),
                "camera_id": camera_id,
                "label": "checkout",
                "method": "face_recognition",
                "time": ts,
                "image_url": None,
                "video_url": None,
                "name": person,
                "employee_id": empid,
                "person_id": empid,
            }

            img_name = f"checkout_{empid}_{int(now)}.jpg"
            save_queue.put(("image", {
                "frame": frame.copy(),
                "bbox": (r["loc"][3], r["loc"][0], r["loc"][1], r["loc"][2]),
                "event": ev,
                "path": img_name,
                "display_label": "CHECKOUT",
            }))

            ev["image_path"] = f"static/events/{img_name}"
            ev["image_url"] = f"http://localhost:5000/{ev['image_path']}"
            
            save_event_to_db(ev)
            event_broadcast_queue.put(ev)

            last_seen[person]["checkout"] = True
            print(f"👋 {person} CHECK-OUT sau 400 giây")

def is_event_enabled(area_id, event_name: str) -> bool:
    """Check if event is enabled for area"""
    cfg = CURRENT_CONFIG
    try:
        return event_name in cfg.get("areas", {}).get(str(area_id), {}).get("enabled_events", [])
    except Exception as e:
        print("[DEBUG ERROR]", e)
        return False

def get_area_name(area_id):
    """Get area name by ID"""
    from app.models.database import get_area_name as db_get_area_name
    return db_get_area_name(area_id)

def recognition_thread():
    """Main face recognition thread"""
    global face_results, last_recognition_time
    last_seen = {}
    
    while True:
        now = time.time()
        if now - last_recognition_time < RECOGNITION_INTERVAL:
            time.sleep(0.01)
            continue

        try:
            item = face_queue.get_nowait()
            if isinstance(item, tuple):
                camera_id, frame = item
            else:
                camera_id, frame = None, item
        except queue.Empty:
            time.sleep(0.01)
            continue

        try:
            results = recognize_on_frame(frame)
            for r in results:
                r["camera_id"] = camera_id
        except Exception as e:
            print("[RECOGNIZE ERR]", e)
            results = []

        with face_lock:
            face_results = results.copy()
        last_recognition_time = now

        for r in results:
            if r["name"] == "Unknown":
                add_pending_face(frame, r["loc"], r["encoding"])
            else:
                try:
                    # ✅ Giới hạn vùng vẽ cho khu vực (nếu có)
                    area_id = get_area_by_camera(camera_id)
                    if area_id:
                        draw_areas = get_draw_areas_for_area(area_id)
                        if draw_areas and len(draw_areas) > 0:
                            top, right, bottom, left = r["loc"]
                            bbox = (left, top, right, bottom)
                            H, W = frame.shape[:2]
                            if not bbox_overlaps_any(bbox, draw_areas, W, H, min_fraction=0.02):
                                print(f"⚠️ [RECOG] Bỏ qua nhận diện ngoài vùng vẽ tại area {area_id}")
                                continue
                        else:
                            # 🟢 Nếu chưa vẽ vùng nào -> cho phép toàn khung
                            pass
                    if not is_event_allowed(area_id, "checkincheckout"):
                        print(f"⏰ [SKIP] Ngoài giờ cho phép checkincheckout tại khu vực {area_id}")
                        continue
                    log_checkin_checkout(r, frame, camera_id)
                except Exception as e:
                    print("[RECOG ERROR]", e)