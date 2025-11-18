import time, base64
import threading
import uuid
import numpy as np
from datetime import datetime
import queue
import cv2
from app.globals import pose_queue, cig_queue, person_queue, qr_queue, alert_frames, face_results, face_lock
from app.models.pose_detection import check_hand_to_mouth, calc_iou
from app.models.database import get_area_by_camera, get_area_name, save_event_to_db, save_qr_log
from app.models.qr_detection import decode_qr_code
from app.utils.area_helpers import get_draw_areas_for_area, bbox_overlaps_any, is_event_enabled, is_event_allowed
from app.utils.config import CURRENT_CONFIG
from app.utils.audio import play_audio_alarm
from app.globals import save_queue, event_broadcast_queue
from app.utils.drawing import draw_label_with_bg

# Configuration
COOLDOWN = 15
HOLD_TIME = 5
HAND_TO_MOUTH_DIST = 30

def hand2mouth_thread(pose_model):
    """Hand-to-mouth detection thread (light alert only)"""
    while True:
        try:
            # Nhận dữ liệu từ pose_queue
            item = pose_queue.get(timeout=1)
        except queue.Empty:
            continue

        # Giải tuple: (camera_id, frame)
        if isinstance(item, tuple):
            cam_id, frame = item
        else:
            cam_id, frame = 0, item

        try:
            # Dự đoán pose
            res_pose = pose_model.track(frame, tracker=None, persist=False, verbose=False)[0]
            if res_pose and getattr(res_pose, "keypoints", None) is not None:
                kpts_np = res_pose.keypoints.xy.cpu().numpy()
                boxes_np = (
                    res_pose.boxes.xyxy.cpu().numpy()
                    if res_pose.boxes.xyxy is not None
                    else []
                )
                ids_np = (
                    res_pose.boxes.id.cpu().numpy()
                    if res_pose.boxes.id is not None
                    else [None] * len(boxes_np)
                )

                for kpts, bx, tid in zip(kpts_np, boxes_np, ids_np):
                    if tid is None:
                        continue
                    x1, y1, x2, y2 = map(int, bx[:4])

                    # Kiểm tra tay đưa miệng
                    if check_hand_to_mouth(kpts):
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        draw_label_with_bg(frame, "🚬 Smoking Detected", (x1, y1))
                        # Cập nhật vùng cảnh báo (hiển thị trong vài giây)
                        alert_frames[int(tid)] = {
                            "bbox": (x1, y1, x2, y2),
                            "label": "SMOKING",
                            "display_label": "🚬 Smoking",
                            "end_time": time.time() + HOLD_TIME,
                            "cam_id": cam_id,
                        }

        except Exception as e:
            continue

def cigarette_thread(pose_model, cig_model=None, lstm_model=None, scaler=None, lbl_map=None):
    """Cigarette detection thread (main event logger)"""
    last_save = {}
    
    while True:
        try:
            camera_id, frame = cig_queue.get(timeout=1)
        except queue.Empty:
            continue

        H, W = frame.shape[:2]
        try:
            res_pose = pose_model.track(frame, tracker="bytetrack.yaml", persist=True, verbose=False)[0]
        except Exception:
            res_pose = None

        if res_pose and getattr(res_pose, "keypoints", None) is not None:
            kpts_np = res_pose.keypoints.xy.cpu().numpy()
            boxes_np = res_pose.boxes.xyxy.cpu().numpy() if res_pose.boxes.xyxy is not None else []
            ids_np = res_pose.boxes.id.cpu().numpy() if res_pose.boxes.id is not None else [None] * len(boxes_np)

            with face_lock:
                frs = face_results.copy()

            for kpts, bx, tid in zip(kpts_np, boxes_np, ids_np):
                
                area_id = None

                if tid is None or np.isnan(bx).any() or np.isinf(bx).any():
                    continue

                tid = int(tid)
                x1, y1, x2, y2 = map(int, bx[:4])
                now = time.time()
               
                if check_hand_to_mouth(kpts) and now - last_save.get(tid, 0) > COOLDOWN:
                    person_name, person_id = "Unknown", None
                    for fface in frs:
                        top, right, bottom, left = fface["loc"]
                        face_box = (left, top, right, bottom)
                        if calc_iou((x1, y1, x2, y2), face_box) > 0.1:
                            person_name = fface.get("name", "Unknown")
                            person_id = fface.get("person_id")
                            break
                    area_id = get_area_by_camera(camera_id)

                    if not area_id:
                        print(f"🚫[smoking] Không tìm thấy khu vực cho camera {camera_id}")
                        continue

                    if not is_event_enabled(area_id, "smoking"):
                        # nếu sự kiện này bị tắt
                        print(f"🚫 Khu vực {area_id} đã tắt sự kiện smoking")
                        continue

                    if not is_event_allowed(area_id, "smoking"):
                        print(f"⏰ [SKIP] Ngoài giờ cho phép smoking tại khu vực {area_id}")
                        continue

                    # ✅ Kiểm tra giới hạn vùng vẽ (nếu có)
                    draw_areas = get_draw_areas_for_area(area_id)
                    if draw_areas and len(draw_areas) > 0:
                        if not bbox_overlaps_any((x1, y1, x2, y2), draw_areas, W, H, min_fraction=0.05):
                            print(f"⚠️ [CIGARETTE] Bỏ qua bbox ngoài vùng vẽ tại area {area_id}")
                            continue
                    else:
                        pass

                    area_id = get_area_by_camera(camera_id)
                    area_name = get_area_name(area_id)

                    ev_id = str(uuid.uuid4())
                    event = {
                        "id": ev_id,
                        "label": "smoking",
                        "method": "iou_pose",
                        "time": datetime.now().isoformat(),
                        "bbox": [x1, y1, x2, y2],
                        "name": person_name,
                        "person_id": person_id,
                        "camera_id": camera_id,
                        "area_id": area_id,
                        "area_name": area_name,
                        "image_url": None,
                        "video_url": None,
                    }

                    img_path = f"warning_hand_{tid}_{int(time.time())}.jpg"
                    save_queue.put(("image", {
                        "frame": frame.copy(),
                        "bbox": (x1, y1, x2, y2),
                        "event": event,
                        "path": img_path,
                        "display_label": "Warning Smoking",
                    }))
                    save_event_to_db(event)

                    # Start video saving in separate thread
                    from app.utils.video_processing import save_violation_clip
                    from app.threads.camera_thread import frame_buffers, camera_queues
                    threading.Thread(
                        target=save_violation_clip,
                        args=(event, frame.copy(), frame_buffers, camera_queues),
                        daemon=True
                    ).start()

                    area_id = get_area_by_camera(event.get("camera_id"))
                    area_name = get_area_name(area_id)

                    event["area_id"] = area_id
                    event["area_name"] = area_name

                    event_broadcast_queue.put(event)

                    # Play audio alarm if configured
                    try:
                        if camera_id:
                            area_cfg = CURRENT_CONFIG.get("areas", {}).get(str(camera_id), {})
                            linkage = area_cfg.get("linkage", {})
                            normal_linkage = linkage.get("normal", {})

                            if normal_linkage.get("audibleWarning", False):  
                                play_audio_alarm()
                                print(f"🔊 [ALERT] Phát âm thanh cảnh báo smoking tại khu vực {camera_id}")
                    except Exception as e:
                        print("[ALERT AUDIO ERROR]", e)

                    last_save[tid] = now

        global last_pose_result
        last_pose_result = {"alerts": []}

def person_detection_thread(yolo_model):
    """Person detection thread"""
    print("[PERSON] Thread running...")
    last_trigger = {}  # tránh spam

    while True:
        try:
            camera_id, frame = person_queue.get(timeout=1)
        except queue.Empty:
            continue

        H, W = frame.shape[:2]

        # ============================
        # 1️⃣ YOLO DETECT
        # ============================
        try:
            result = yolo_model(frame, verbose=False)[0]
        except Exception as e:
            print("❌ YOLO Person detect failed:", e)
            continue

        if result.boxes is None:
            continue

        boxes = result.boxes.xyxy.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy()
        ids = result.boxes.id.cpu().numpy() if result.boxes.id is not None else [None] * len(boxes)

        # ============================
        # 2️⃣ LOOP TỪNG BOUNDING BOX
        # ============================
        for box, cls_id, tid in zip(boxes, classes, ids):

            # Chỉ lấy class 'person'
            if int(cls_id) != 0:
                continue

            # Nếu không có tracking ID → tạo ID giả
            if tid is None:
                tid = int(time.time() * 1000)

            tid = int(tid)

            x1, y1, x2, y2 = map(int, box[:4])
            now = time.time()

            # Cooldown tránh spam liên tục
            if now - last_trigger.get(tid, 0) < COOLDOWN:
                continue

            # ============================
            # 3️⃣ Lấy area theo camera
            # ============================
            area_id = get_area_by_camera(camera_id)
            if not area_id:
                print(f"🚫[PERSON] Không tìm thấy khu vực cho camera {camera_id}")
                continue

            # ============================
            # 4️⃣ Check cấu hình sự kiện
            # ============================
            if not is_event_enabled(area_id, "person_detection"):
                print(f"⛔ Sự kiện person_detection bị tắt tại area {area_id}")
                continue

            if not is_event_allowed(area_id, "person_detection"):
                print(f"⏳ Ngoài giờ cho phép person_detection tại area {area_id}")
                continue

            # ============================
            # 5️⃣ Kiểm tra vùng vẽ
            # ============================
            draw_areas = get_draw_areas_for_area(area_id)

            if draw_areas and len(draw_areas) > 0:
                if not bbox_overlaps_any((x1, y1, x2, y2), draw_areas, W, H, min_fraction=0.05):
                    print(f"⚠️ Bỏ qua bbox ngoài vùng vẽ tại area {area_id}")
                    continue

            person_name, person_id = "Unknown", None

            # ============================
            # 6️⃣ Ghép với face recognition (nếu có)
            # ============================
            with face_lock:
                frs = face_results.copy()

            for face in frs:
                top, right, bottom, left = face["loc"]
                if calc_iou((x1, y1, x2, y2), (left, top, right, bottom)) > 0.2:
                    person_name = face.get("name", "Unknown")
                    person_id = face.get("person_id")
                    break

            # ============================
            # 7️⃣ Tạo EVENT
            # ============================
            ev_id = str(uuid.uuid4())

            event = {
                "id": ev_id,
                "label": "person_detection",
                "method": "object",
                "time": datetime.now().isoformat(),
                "bbox": [x1, y1, x2, y2],
                "name": person_name,
                "person_id": person_id,
                "camera_id": camera_id,
                "area_id": area_id,
                "area_name": get_area_name(area_id),
                "image_url": None,
                "video_url": None,
            }

            # =====================================================
            # 8️⃣ KHÔNG LƯU LOCAL — TRẢ ẢNH BASE64 LÊN FRONTEND
            # =====================================================
            crop = frame[y1:y2, x1:x2]

            try:
                _, buffer = cv2.imencode(".jpg", crop)
                img_base64 = base64.b64encode(buffer).decode("utf-8")
                event["image_url"] = f"data:image/jpeg;base64,{img_base64}"
            except Exception as e:
                print("[BASE64 ERROR]", e)
                event["image_url"] = None

            # Lưu DB (có image_url = base64)
            save_event_to_db(event)

            # ============================
            # 9️⃣ Gửi SSE về frontend
            # ============================
            event_broadcast_queue.put(event)

            print(f"🧍 [PERSON DETECT] {person_name} – Camera {camera_id}")

            # ============================
            # 🔟 Phát âm thanh cảnh báo (nếu bật)
            # ============================
            try:
                area_cfg = CURRENT_CONFIG.get("areas", {}).get(str(camera_id), {})
                linkage = area_cfg.get("linkage", {})
                normal_linkage = linkage.get("normal", {})

                if normal_linkage.get("audibleWarning", False):
                    play_audio_alarm()
                    print(f"🔊 [ALERT] Phát âm thanh cảnh báo person tại camera {camera_id}")
            except Exception as e:
                print("[ALERT AUDIO ERROR]", e)

            # Cập nhật cooldown
            last_trigger[tid] = now

def qr_detection_thread():
    """QR code detection thread"""
    last_qr_time = {}

    while True:
        try:
            camera_id, frame = qr_queue.get(timeout=1)
        except queue.Empty:
            continue

        # detect
        results = decode_qr_code(frame)
        if not results:
            continue

        for qr in results:
            data = qr["data"]
            x, y, x2, y2 = qr["bbox"]
            now = time.time()

            # loại bỏ spam
            if now - last_qr_time.get(data, 0) < 5:
                continue
            last_qr_time[data] = now

            area_id = get_area_by_camera(camera_id)
            area_name = get_area_name(area_id)

            if not is_event_enabled(area_id, "qr_scan"):
                print(f"[QR] Sự kiện QR bị tắt tại area {area_id}")
                continue
            
            if not is_event_allowed(area_id, "qr_scan"):
                print(f"[QR] Ngoài giờ cho phép QR tại {area_id}")
                continue

            # tạo event
            ev_id = str(uuid.uuid4())
            event = {
                "id": ev_id,
                "label": "qr_scan",
                "method": "qrcode",
                "bbox": [x, y, x2, y2],
                "camera_id": camera_id,
                "area_id": area_id,
                "area_name": area_name,
                "qr_data": data,
                "time": datetime.now().isoformat(),
                "image_url": None,
                "video_url": None
            }

            # LƯU QR LOG VÀO BẢNG qr_logs
            save_qr_log(camera_id, data)

            filename = f"qr_{ev_id}.jpg"
            qr_crop = frame[y:y2, x:x2]
            cv2.imwrite(f"static/events/{filename}", qr_crop)

            save_event_to_db(event)
            event_broadcast_queue.put(event)

            print(f"[QR] Đã quét QR: {data} tại camera {camera_id}")