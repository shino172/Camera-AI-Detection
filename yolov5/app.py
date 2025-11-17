# app_detect_intergated.py
import os, cv2, time, queue,threading,json, uuid,base64,joblib,face_recognition,cloudinary, psycopg2, tempfile, ctypes
import numpy as np
from psycopg2 import pool, OperationalError
from psycopg2.extras import Json
from flask import Flask, Response, request, jsonify, send_from_directory, stream_with_context
from flask_cors import CORS, cross_origin
from keras.models import load_model
from ultralytics import YOLO
from scipy.spatial import distance
from dotenv import load_dotenv
from collections import deque
from ctypes import *
from datetime import datetime, timezone, timedelta
from queue import Empty
import pytz
from playsound import playsound
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash, check_password_hash
from pyzbar.pyzbar import decode

event_time = datetime.utcnow().replace(tzinfo=pytz.utc)
load_dotenv()

# ---------------- CONFIG ----------------
DATABASE_URL = os.getenv("DATABASE_URL")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

if not DATABASE_URL:
    raise RuntimeError("Missing DATABASE_URL environment variable (SUPABASE/Postgres).")

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

# conn = psycopg2.connect(
#     host="localhost",
#     database="postgres",
#     user="postgres",
#     password="your_password"
# )
# print("✅ Kết nối thành công!")

# Models & files (adjust paths if needed)
# SEQ_LEN = 30
LSTM_MODEL = "lstm_action.h5"
SCALER_FILE = "pose_scaler.pkl"
LABEL_FILE = "pose_labels.pkeml"

# CIG_MODEL = "best.pt"
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# CIG_MODEL = os.path.join(BASE_DIR, "runs", "train", "smoking_detector", "weights", "best.pt")
CIG_MODEL = "best.pt"
POSE_MODEL = "yolov8n-pose.pt"
YOLO_PERSON_MODEL = "yolo11n.pt"

TARGET_SIZE = (1920, 1080)

# Face settings
DB_TABLE = "faces"
FRAME_WAIT = 0.033
RECOGNITION_INTERVAL = 0.1 
FRAME_SCALE = 1
COMPARE_TOLERANCE = 0.45
PENDING_EXPIRY = 60.0
PENDING_MIN_DIST = 0.4
AUTO_SAVE_INTERVAL = False  

IOU_THRESHOLD = 0.50
HAND_TO_MOUTH_DIST = 30
COOLDOWN = 15
VIDEO_DURATION = 15
FPS = 20
HOLD_TIME = 5
MAX_EVENTS = 400
LOG_FILE = "events.json"
MIN_DIST_DB = 0.38
FACE_MATCH_MAX_AGE = 1.5
VIDEO_PATH = os.path.join(os.getcwd(), "static", "events")
os.makedirs(VIDEO_PATH, exist_ok=True)

# PLAYBACK_DIR = "static/playbacks"
PLAYBACK_DIR = os.path.join(os.getcwd(), "static", "playback")
os.makedirs(PLAYBACK_DIR, exist_ok=True)

LOCAL_IMAGE_DIR = os.path.join("static", "faces")
LOCAL_EVENT_DIR = os.path.join("static", "events")
os.makedirs(LOCAL_IMAGE_DIR, exist_ok=True)
os.makedirs(LOCAL_EVENT_DIR, exist_ok=True)

AUDIO_FILE = os.path.join("static", "sounds", "alarm.mp3")

HCNetSDK = ctypes.WinDLL(r"C:\Users\PC\Downloads\EN-HCNetSDKV6.1.9.48_build20230410_win64\EN-HCNetSDKV6.1.9.48_build20230410_win64\lib\HCNetSDK.dll")
HCNetSDK.NET_DVR_Init()

# ---------------- Globals / Queues ----------------
face_queue = queue.Queue(maxsize=1)
pose_queue = queue.Queue(maxsize=1)
cig_queue = queue.Queue(maxsize=1)
save_queue = queue.Queue()
person_queue = queue.Queue()
qr_queue = queue.Queue(maxsize=1)

event_broadcast_queue = queue.Queue()


VIDEO_BUFFER_SECONDS = 5
VIDEO_AFTER_SECONDS = 25
VIDEO_TOTAL_SECONDS = VIDEO_BUFFER_SECONDS + VIDEO_AFTER_SECONDS
VIDEO_FPS = FPS

# =================== AREA DRAWING HELPERS ===================
def get_draw_areas_for_area(area_id):
    """Lấy danh sách vùng vẽ (normalized) cho khu vực."""
    cfg = CURRENT_CONFIG.get("areas", {})
    entry = cfg.get(str(area_id)) or {}
    return entry.get("draw_areas") or []

def bbox_intersects_rect(bbox, rect_px):
    """Kiểm tra phần trăm giao nhau giữa bbox và vùng vẽ (pixel)."""
    x1, y1, x2, y2 = bbox
    rx1 = rect_px['x']
    ry1 = rect_px['y']
    rx2 = rx1 + rect_px['w']
    ry2 = ry1 + rect_px['h']

    inter_x1 = max(x1, rx1)
    inter_y1 = max(y1, ry1)
    inter_x2 = min(x2, rx2)
    inter_y2 = min(y2, ry2)

    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    bbox_area = max((x2 - x1) * (y2 - y1), 1)
    return inter_area / bbox_area

def bbox_overlaps_any(bbox, draw_areas_norm, W, H, min_fraction=0.05):
    """Kiểm tra bbox có giao với bất kỳ vùng vẽ nào không."""
    for r in draw_areas_norm:
        rect_px = {
            'x': int(r['x'] * W),
            'y': int(r['y'] * H),
            'w': int(r['w'] * W),
            'h': int(r['h'] * H),
        }
        if bbox_intersects_rect(bbox, rect_px) >= min_fraction:
            return True
    return False

# audio
def play_audio_alarm():
    """Phát âm thanh cảnh báo (chạy trong thread riêng để không block)."""
    if not os.path.exists(AUDIO_FILE):
        print(f"[AUDIO ALERT] ⚠️ Không tìm thấy file âm thanh: {AUDIO_FILE}")
        return
    def _play():
        try:
            playsound(AUDIO_FILE)
        except Exception as e:
            print("[AUDIO ALERT ERROR]", e)
    threading.Thread(target=_play, daemon=True).start()

frame_buffer = deque(maxlen=VIDEO_BUFFER_SECONDS * VIDEO_FPS)

pending_faces = {}
lock = threading.Lock() 
last_auto_save = {}
last_recognition_time = 0

_db_cache_encodings, _db_cache_names, _db_cache_ids, _db_cache_images, _db_cache_empids, _db_cache_ts = [], [], [], [], [], 0
DB_CACHE_TTL = 5.0

face_results = []
face_lock = threading.Lock()
alert_frames = {}
face_look= threading.Lock()
last_pose_result = None
last_seen = {}
checkin_status = {}
cameras = {}
current_camera_id = None
active_camera_id = None
camera_lock = threading.Lock()
camera_queues = {}
frame_buffers = {}
EVENTS = []

def get_area_by_camera(camera_id):
    """Lấy area_id từ bảng cameras"""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT area_id FROM cameras WHERE camera_id = %s;", (int(camera_id),))
            row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
        print(f"[DB] ⚠️ Không tìm thấy area cho camera {camera_id}")
    except Exception as e:
        print(f"[DB ERROR] get_area_by_camera({camera_id}): {e}")
    return None

def is_event_enabled(area_id, event_name: str) -> bool:
    cfg = sync_current_config()
    print(f"[DEBUG] Check event {event_name} in area {area_id}")
    print(json.dumps(cfg.get("areas", {}), indent=2, ensure_ascii=False))
    try:
        return event_name in cfg.get("areas", {}).get(str(area_id), {}).get("enabled_events", [])
    except Exception as e:
        print("[DEBUG ERROR]", e)
        return False

# ---------------- DB (Neon/Postgres) ----------------
def get_conn(retries=3, delay=2):
    """
    Kết nối PostgreSQL (Supabase / Neon / Localhost) có retry và SSL tự động.
    - Tự động thêm sslmode=require nếu là Supabase / Neon
    - Tự động disable SSL nếu là localhost
    - Ghi log chi tiết từng lần thử
    """
    global DATABASE_URL
    parsed = urlparse(DATABASE_URL)

    # 🟢 Nếu là Supabase hoặc Neon — bắt buộc SSL
    if any(x in parsed.hostname for x in ["supabase", "neon.tech", "render"]):
        if "sslmode" not in DATABASE_URL:
            if "?" in DATABASE_URL:
                DATABASE_URL += "&sslmode=require"
            else:
                DATABASE_URL += "?sslmode=require"

    # 🟠 Nếu là localhost thì disable SSL
    elif "localhost" in parsed.hostname or "127.0.0.1" in parsed.hostname:
        if "sslmode" not in DATABASE_URL:
            if DATABASE_URL.endswith("/"):
                DATABASE_URL = DATABASE_URL[:-1]
            DATABASE_URL += "?sslmode=disable"

    print(f"[DB CONFIG] Using connection: {DATABASE_URL}")

    for i in range(retries):
        try:
            print(f"[DB CONNECT ATTEMPT {i+1}/{retries}] Connecting...")
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            conn.autocommit = True
            print("✅ PostgreSQL connected successfully.")
            return conn
        except OperationalError as e:
            print(f"[DB CONNECT RETRY {i+1}/{retries}] {e}")
            time.sleep(delay * (i + 1))  # tăng delay dần theo lần thử

    print("❌ Không thể kết nối tới PostgreSQL sau nhiều lần thử. Server sẽ KHÔNG tắt.")
    return None

def init_db():
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            # PERSONS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS persons (
                    person_id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE,
                    email TEXT,
                    phone TEXT,
                    department TEXT,
                    position TEXT,
                    avatar TEXT,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)

            # USERS
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT DEFAULT 'user' CHECK (role IN ('admin','user')),
                    person_id INT REFERENCES persons(person_id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
    conn.close()


def _load_db_raw():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT id::text, person_id, name, encoding, image_url, ts
                FROM {DB_TABLE}
                ORDER BY ts DESC;
            """)
            rows = cur.fetchall()
        result = []
        for r in rows:
            enc = r[3]
            if isinstance(enc, str):
                try:
                    enc = json.loads(enc)
                except:
                    enc = []
            if isinstance(enc, list) and len(enc) == 128:
                result.append({
                    "id": r[0],
                    "employee_id": r[1],
                    "personal_id": r[1],
                    "name": r[2],
                    "encoding": enc,
                    "image_url": r[4],
                    "ts": r[5].isoformat() if r[5] else None
                })
        return result
    finally:
        conn.close()
def load_db_cache(force: bool = False):
    global _db_cache_encodings, _db_cache_names, _db_cache_ids, _db_cache_images, _db_cache_empids, _db_cache_ts
    now = time.time()
    if not force and now - _db_cache_ts < DB_CACHE_TTL and _db_cache_encodings:
        return
    raw = _load_db_raw()
    _db_cache_encodings = [np.array(r["encoding"]) for r in raw]
    _db_cache_names = [r["name"] for r in raw]
    _db_cache_ids = [r["id"] for r in raw]
    _db_cache_images = [r.get("image_url") or r.get("image") for r in raw]
    _db_cache_empids = [r["employee_id"] for r in raw]
    _db_cache_ts = now
def get_or_create_person(cur, name: str) -> int:
    cur.execute("SELECT person_id FROM persons WHERE LOWER(name) = LOWER(%s) LIMIT 1", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO persons (name) VALUES (%s) RETURNING person_id", (name,))
    return cur.fetchone()[0]
def append_db_entry(name, encoding, image_url=None):
    enc_arr = np.array(encoding).flatten().tolist()
    if len(enc_arr) != 128:
        raise ValueError(f"Invalid encoding length: {len(enc_arr)}")

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                person_id = get_or_create_person(cur, name)

                cur.execute(
                    f"""
                    INSERT INTO {DB_TABLE} (id, person_id, name, encoding, image_url)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, ts
                    """,
                    (str(uuid.uuid4()), person_id, name, Json(enc_arr), image_url)
                )
                row = cur.fetchone()
                row_id = row[0]
                ts_val = row[1].isoformat() if row[1] else None
    finally:
        conn.close()

    global _db_cache_ts
    _db_cache_ts = 0

    return {
        "id": row_id,
        "person_id": person_id,
        "name": name,
        "encoding": enc_arr,
        "image": image_url,
        "ts": ts_val
    }
def delete_db_entry(face_id):
    conn = get_conn()
    rows = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {DB_TABLE} WHERE id = %s", (face_id,))
                rows = cur.rowcount
    finally:
        conn.close()
    global _db_cache_ts
    _db_cache_ts = 0
    return rows
def update_db_name(face_id, new_name):
    conn = get_conn()
    rows = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE {DB_TABLE} SET name = %s WHERE id = %s", (new_name, face_id))
                rows = cur.rowcount
    finally:
        conn.close()
    global _db_cache_ts
    _db_cache_ts = 0
    return rows

def get_nvr_id_by_camera(camera_id):
    """
    Lấy nvr_id từ camera_id để gắn vào sự kiện (event).
    """
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT nvr_id FROM cameras WHERE camera_id = %s", (camera_id,))
            row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
        return None
    except Exception as e:
        print("[DB ERROR] get_nvr_id_by_camera:", e)
        return None

def save_event_to_db(event):
    """Lưu sự kiện vào DB (an toàn, không trùng ID)"""
    try:
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                img_url, vid_url = None, None

                if event.get("image_path"):
                    p = event["image_path"].replace("\\", "/")
                    img_url = f"http://localhost:5000/{p}" if not p.startswith("http") else p
                if event.get("video_path"):
                    v = event["video_path"].replace("\\", "/")
                    vid_url = f"http://localhost:5000/{v}" if not v.startswith("http") else v

                local_time = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
                cur.execute("""
                    INSERT INTO events (id, person_id, camera_id, nvr_id, label, method, time, image_url, video_url)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    event.get("id") or str(uuid.uuid4()),
                    event.get("person_id"),
                    event.get("camera_id"),
                    get_nvr_id_by_camera(event.get("camera_id")),
                    event.get("label"),
                    event.get("method"),
                    local_time,
                    img_url,
                    vid_url
                ))
        conn.close()
    except Exception as e:
        if "duplicate key" not in str(e).lower():
            print(f"[SAVE EVENT ERROR] {e}")

def update_event_media(event_id, image_url=None, video_url=None, image_base64=None):
    """
    Cập nhật media (ảnh/video) cho event đã tồn tại.
    Hỗ trợ cả lưu ảnh dạng Base64.
    """
    try:
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                fields = []
                values = []

                if image_url:
                    fields.append("image_url = %s")
                    values.append(image_url)
                if video_url:
                    fields.append("video_url = %s")
                    values.append(video_url)
                if image_base64:
                    fields.append("image_base64 = %s")
                    values.append(image_base64)

                if not fields:
                    print("[WARN] Không có media nào để cập nhật.")
                    return

                sql = f"UPDATE events SET {', '.join(fields)} WHERE id = %s"
                values.append(event_id)
                cur.execute(sql, tuple(values))

        conn.close()
        print(f"[DB] Updated event {event_id} (media)")
    except Exception as e:
        print("[UPDATE EVENT MEDIA ERROR]", e)

def get_event_info(event_id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    e.id::text,
                    e.camera_id,
                    e.time AS event_time,
                    c.name AS camera_name,
                    c.channel,
                    n.ip_address,
                    n.port,
                    n.username,
                    n.password
                FROM events e
                JOIN cameras c ON e.camera_id = c.camera_id
                JOIN nvrs n ON c.nvr_id = n.id
                WHERE e.id = %s
                LIMIT 1;
            """, (event_id,))
            row = cur.fetchone()
            if not row:
                return None

            return {
                "event_id": row[0],
                "camera_id": row[1],
                "camera_name": row[3],
                "channel": row[4] or 1,
                "ip": row[5],
                "port": row[6],
                "user": row[7],
                "pass": row[8],
                "start_time": row[2],
                "end_time": row[2] + timezone(minutes=1)
            }
    finally:
        conn.close()

# ---------------- Face utils ----------------
def crop_face(frame_bgr, loc, pad=40):
    top, right, bottom, left = loc
    h, w = frame_bgr.shape[:2]
    top = max(0, top - pad)
    bottom = min(h, bottom + pad)
    left = max(0, left - pad)
    right = min(w, right + pad)
    if bottom <= top or right <= left:
        return frame_bgr 
    return frame_bgr[top:bottom, left:right]

def face_to_b64(face_bgr):
    ok, buf = cv2.imencode(".jpg", face_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8") if ok else None

def recognize_on_frame(frame_bgr):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    locs = face_recognition.face_locations(rgb, model='hog')
    encs = face_recognition.face_encodings(rgb, locs)

    # load cache DB
    load_db_cache()
    known_encs = _db_cache_encodings
    known_names = _db_cache_names
    known_empids = _db_cache_empids

    results = []
    for (top, right, bottom, left), enc in zip(locs, encs):
        name, idx, empid = "Unknown", None, None
        if known_encs:
            dists = [distance.euclidean(enc, known_enc) for known_enc in known_encs]
            best_idx = int(np.argmin(dists))
            if dists[best_idx] < COMPARE_TOLERANCE:
                name = known_names[best_idx]
                idx = best_idx
                empid = known_empids[best_idx]

        results.append({
            "loc": (top, right, bottom, left),
            "encoding": enc.tolist(),
            "name": name,
            "db_idx": idx,
            "employee_id": empid,
            "person_id": empid
        })

    return results

def load_db():
    global _db_cache_encodings, _db_cache_names, _db_cache_ts
    now = time.time()
    if now - _db_cache_ts < DB_CACHE_TTL and _db_cache_encodings:
        return [{"name": n, "encoding": enc.tolist()} 
                for n, enc in zip(_db_cache_names, _db_cache_encodings)]
    raw = _load_db_raw()
    _db_cache_encodings = [np.array(r["encoding"]) for r in raw]
    _db_cache_names = [r["name"] for r in raw]
    _db_cache_ts = now
    return [{"name": n, "encoding": enc.tolist()} for n, enc in zip(_db_cache_names, _db_cache_encodings)]

def add_pending_face(frame, loc, encoding):
    now = time.time()
    enc_arr = np.array(encoding)
    with lock:
        # cleanup
        for fid in list(pending_faces.keys()):
            if now - pending_faces[fid]["ts"] > PENDING_EXPIRY:
                pending_faces.pop(fid, None)
        # dedupe
        for fid, info in pending_faces.items():
            if np.linalg.norm(np.array(info["encoding"]) - enc_arr) < PENDING_MIN_DIST:
                return None
        crop = crop_face(frame, loc)
        fid = uuid.uuid4().hex
        pending_faces[fid] = {"bbox": loc, "encoding": encoding, "image_b64": face_to_b64(crop), "ts": now}
    return fid

def delete_event_db(event_id: str):
    conn = get_conn()
    rows = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM events WHERE id = %s", (event_id,))
                rows = cur.rowcount
    except Exception as e:
        print("[DELETE EVENT DB ERROR]", e)
    finally:
        conn.close()
    return rows

def delete_all_events_db():
    conn = get_conn()
    rows = 0
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM events;")
                rows = cur.rowcount
    except Exception as e:
        print("[DELETE ALL EVENTS DB ERROR]", e)
    finally:
        conn.close()
    return rows
# ---------------- Action utils ----------------
YOLO_TO_MP = {
    0:0,1:2,2:5,3:7,4:8,5:11,6:12,7:13,8:14,
    9:15,10:16,11:23,12:24,13:25,14:26,15:27,16:28
}

def kpt2vec(k, w, h):
    vec = [0.0]*99
    for yi, mi in YOLO_TO_MP.items():
        if yi < len(k):
            x,y = k[yi][:2]
            vec[mi*3] = x / w
            vec[mi*3 + 1] = y / h
    return np.array(vec, np.float32)

def check_hand_to_mouth(kpts):
    if kpts is None or len(kpts) < 11: return False
    nose = kpts[0]; lw, rw = kpts[9], kpts[10]
    dist = lambda a,b: np.linalg.norm(a[:2]-b[:2])
    try:
        if (lw[0] or lw[1]) and dist(nose,lw) < HAND_TO_MOUTH_DIST: return True
        if (rw[0] or rw[1]) and dist(nose,rw) < HAND_TO_MOUTH_DIST: return True
    except:
        return False
    return False

def calc_iou(boxA, boxB):
    xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
    xB, yB = min(boxA[2], boxB[2]), min(boxA[3], boxB[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    if interArea <= 0: return 0.0
    boxAArea = (boxA[2]-boxA[0]) * (boxA[3]-boxA[1])
    boxBArea = (boxB[2]-boxB[0]) * (boxB[3]-boxB[1])
    return interArea / float(boxAArea + boxBArea - interArea + 1e-9)
# ---------------- Define device info struct ----------------
class NET_DVR_DEVICEINFO_V30(Structure):
    _fields_ = [
        ("sSerialNumber", c_ubyte * 48),
        ("byAlarmInPortNum", c_ubyte),
        ("byAlarmOutPortNum", c_ubyte),
        ("byDiskNum", c_ubyte),
        ("byDVRType", c_ubyte),
        ("byChanNum", c_ubyte),
        ("byStartChan", c_ubyte),
        ("byAudioChanNum", c_ubyte),
        ("byIPChanNum", c_ubyte),
        # ("byZeroChanNum", c_ubyte),
        # ("byMainProto", c_ubyte),
        # ("bySubProto", c_ubyte),
        # ("bySupport", c_ubyte),
        # ("bySupport1", c_ubyte),
        # ("bySupport2", c_ubyte),
        # ("wDevType", c_ushort),
        # ("bySupport3", c_ubyte),
        # ("byMultiStreamProto", c_ubyte),
        # ("byStartDChan", c_ubyte),
        # ("byStartDTalkChan", c_ubyte),
        # ("byHighDChanNum", c_ubyte),
        # ("bySupport4", c_ubyte),
        # ("byLanguageType", c_ubyte),
        # ("byVoiceInChanNum", c_ubyte),
        # ("byStartVoiceInChanNo", c_ubyte),
        # ("byRes2", c_ubyte * 10)
    ]

def login_nvr(ip, port, username, password):
    device_infor=NET_DVR_DEVICEINFO_V30()
    user_id=HCNetSDK.NET_DVR_Login_V30(ip.encode('utf-8'),port,username.encode('utf-8'),password.encode('utf-8'),byref(device_infor))
    if user_id < 0:
        err = HCNetSDK.NET_DVR_GetLastError()
        raise Exception(f"Login NVR failed, error code: {err}")
    return user_id
# ---------------- Drawing helpers ----------------
def draw_label_with_bg(img, text, org, color=(0,0,255), font=cv2.FONT_HERSHEY_SIMPLEX, scale=0.8, thickness=2, pad=6):
    (tw, th), bl = cv2.getTextSize(text, font, scale, thickness)
    x, y = org
    bg_tl = (x - pad, y - th - pad)
    bg_br = (x + tw + pad, y + bl + pad)
    cv2.rectangle(img, bg_tl, bg_br, (0,0,0), -1)
    cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)

# ---------------- Save worker (images & videos) ----------------
def save_violation_clip(event, current_frame):
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

def get_area_by_camera(camera_id):
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT area_id FROM cameras WHERE camera_id=%s", (camera_id,))
            row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print("[DB ERROR] get_area_by_camera:", e)
        return None
def get_area_name(area_id):
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM areas WHERE id=%s", (area_id,))
            row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None

def save_event_log(event):
    try:
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                image_url = None
                video_url = None

                if event.get("image_path"):
                    image_rel = event["image_path"].replace("\\", "/")
                    image_url = f"/static/events/{os.path.basename(image_rel)}"

                if event.get("video_path"):
                    video_rel = event["video_path"].replace("\\", "/")
                    video_url = f"/static/events/{os.path.basename(video_rel)}"

                event_id = event.get("id") or str(uuid.uuid4())

                cur.execute("""
                    INSERT INTO events (id, person_id, camera_id, label, method, time, image_url, video_url)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    event_id,
                    event.get("person_id"),
                    event.get("camera_id"),
                    event.get("label"),
                    event.get("method"),
                    datetime.now(timezone.utc),
                    image_url,
                    video_url
                ))

                event["id"] = event_id
                event["image_url"] = image_url
                event["video_url"] = video_url

        conn.close()
        EVENTS.insert(0, event)
        if len(EVENTS) > MAX_EVENTS:
            EVENTS.pop()

        json.dump(EVENTS, open(LOG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[DB] Event saved locally: {event_id} ({event.get('label')})")

    except Exception as e:
        print("[SAVE EVENT DB ERROR]", e)

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
                    save_violation_clip(data["event"], data["frames"][0])
                else:
                    print("[WARN] KhĂ´ng cĂ³ frames há»£p lá»‡ Ä‘á»ƒ lÆ°u video.")
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

def save_qr_log(camera_id, data, timestamp=None):
    try:
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO qr_logs (id, camera_id, data, time)
                    VALUES (%s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    camera_id,
                    data,
                    timestamp or datetime.now(pytz.utc)
                ))
        conn.close()
        print(f"[QR_LOG] Lưu thành công QR: {data}")
    except Exception as e:
        print("[QR_LOG ERROR]", e)

# ---------------- Camera thread ----------------
def add_camera(camera_id, src):
    global cameras, camera_queues, frame_buffers
    if camera_id in cameras:
        print(f"[CAMERA] Camera {camera_id} đã tồn tại")
        return False
    cam_thread = CameraThread(camera_id, src)
    cameras[camera_id] = cam_thread
    camera_queues[camera_id] = queue.Queue(maxsize=1)
    frame_buffers[camera_id] = deque(maxlen=VIDEO_BUFFER_SECONDS * VIDEO_FPS)
    cam_thread.start()
    print(f"[CAMERA] đã thêm và chạy camera {camera_id}")
    return True

def stop_camera(camera_id):
    global cameras
    if camera_id not in cameras:
        print(f"[CAMERA] không tìm thấy camera {camera_id}")
        return False
    cameras[camera_id].stop()
    cameras[camera_id].join(timeout=2)
    del cameras[camera_id]
    print(f"[CAMERA] Camera {camera_id}  đã dừng")
    return True

def switch_camera(camera_id):
    global active_camera_id
    if camera_id not in cameras:
        print(f"[CAMERA] Không tìm thấy camera {camera_id}")
        return False
    active_camera_id = camera_id
    print(f"[CAMERA] Chuyển sang camera {camera_id}")
    # print(f"[CAMERA]  {camera_id}")
    return True
# ---------------- Camera thread ----------------
class CameraThread(threading.Thread):
    def __init__(self, camera_id, src):
        super().__init__()
        self.camera_id = camera_id
        self.src = src
        self.cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG if hasattr(cv2,'CAP_FFMPEG') else 0)
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except:
            pass
        self.running = True
        self.latest_frame = None

    def run(self):
      global frame_buffers, camera_queues

      while self.running:
          r, f = self.cap.read()
          if not r:
              time.sleep(0.01)
              continue
          try:
              f = cv2.resize(f, TARGET_SIZE) # có thể tăng lên 2k | 4k
          except:
              pass

          self.latest_frame = f.copy()

          # 🟢 Ghi frame vào bộ nhớ đệm (cho clip trước sự kiện)
          if self.camera_id in frame_buffers:
              frame_buffers[self.camera_id].append(f.copy())

          # 🟢 Ghi frame vào hàng đợi (cho clip sau sự kiện)
          if self.camera_id in camera_queues:
              try:
                  q = camera_queues[self.camera_id]
                  if q.full():
                      q.get_nowait()
                  q.put_nowait(f.copy())
              except:
                  pass

          # 🟢 Đưa frame cho các thread nhận diện (checkin + hành vi)
          try:
              if face_queue.full():
                  face_queue.get_nowait()
              face_queue.put_nowait((self.camera_id, f.copy()))
          except:
              pass

          try:
              if pose_queue.full():
                  pose_queue.get_nowait()
              pose_queue.put_nowait((self.camera_id, f.copy()))
          except:
              pass

          try:
              if cig_queue.full():
                  cig_queue.get_nowait()
              cig_queue.put_nowait((self.camera_id, f.copy()))
          except:
              pass
          
          try:
              if person_queue.full():
                  person_queue.get_nowait()
              person_queue.put_nowait((self.camera_id, f.copy()))
          except:
              pass
          
          try: 
              if qr_queue.full():
                  qr_queue.get_nowait()
              qr_queue.put_nowait((self.camera_id, f.copy()))
          except:
              pass

          time.sleep(0.005)

    def stop(self):
        self.running = False
        try:
            self.cap.release()
        except:
            pass
    
def get_frame(self):
    return self.latest_frame

def recognition_thread():
    global face_results, last_recognition_time
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

        with lock:
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

# ---------------- Hand-to-mouth thread (light alert only) ----------------
def hand2mouth_thread(pose_model):
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
                        draw_label_with_bg(frame, "🚬 Smoking Detected", x1, y1)
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
# ---------------- Cigarette thread (main event logger) ----------------
def cigarette_thread(pose_model, cig_model=None , lstm_model=None, scaler=None, lbl_map=None):
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

                    threading.Thread(
                        target=save_violation_clip,
                        args=(event, frame.copy()),
                        daemon=True
                    ).start()
                    area_id = get_area_by_camera(event.get("camera_id"))
                    area_name = get_area_name(area_id)

                    event["area_id"] = area_id
                    event["area_name"] = area_name

                    event_broadcast_queue.put(event)
                try:
                    if camera_id:
                        area_cfg = CURRENT_CONFIG.get("areas", {}).get(str(camera_id), {})
                        linkage = area_cfg.get("linkage", {})
                        normal_linkage = linkage.get("normal", {})

                        if normal_linkage.get("audibleWarning", False):  
                            play_audio_alarm()
                            print(f"🔊 [ALERT] Phát âm thanh cảnh báo smoking tại khu vực {camera_id}")
                        # else:
                        #     print(f"🔇 [INFO] Âm thanh bị tắt tại khu vực {camera_id}")
                    else:
                        print("ℹ️ [ALERT] Bỏ qua phát âm thanh vì camera chưa gán khu vực.")
                except Exception as e:
                    print("[ALERT AUDIO ERROR]", e)

                    last_save[tid] = now
        global last_pose_result
        last_pose_result = {"alerts": []}

# log checkin - checkout
def log_checkin_checkout(r, frame, camera_id=None):
    global last_seen
    now = time.time()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    day_key = datetime.now().strftime("%Y-%m-%d")

    # === 3️⃣ CHECK-IN ===
    if name not in last_seen or last_seen[name].get("day") != day_key:
        # area_id = get_area_by_camera(camera_id)
        # area_name = get_area_name(area_id)
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
        save_event_to_db(ev)

        area_id = get_area_by_camera(camera_id)
        area_name = get_area_name(area_id)

        ev["area_id"] = area_id
        ev["area_name"] = area_name

        # --- phát realtime ---
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

#  person detection
def person_detection_thread(yolo_model):

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

# scan QR
def qr_detection_thread():
    last_qr_time = {}

    while True:
        try:
            camera_id, frame = qr_queue.get(timeout=1)
        except queue.Empty:
            continue

        # detect
        results = decode(frame)
        if not results:
            continue

        for qr in results:
            data = qr.data.decode("utf-8")
            x,y,w,h = qr.rect
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
                "bbox": [x, y, x+w, y+h],
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
            qr_crop = frame[y:y+h, x:x+w]
            cv2.imwrite(f"static/events/{filename}")

            save_event_to_db(event)
            event_broadcast_queue.put(event)

            print(f"[QR] Đã quét QR: {data} tại camera {camera_id}")

# ---------------- Flask streaming & API ----------------
app = Flask(__name__, static_url_path="/static", static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})
# ------------------ CONFIGURATION ------------------
CONFIG_FILE = "config.json"

CURRENT_CONFIG = {
    "system": {
        "recognition_interval": RECOGNITION_INTERVAL,
        "cooldown": COOLDOWN,
        "video_duration": VIDEO_DURATION,
        "compare_tolerance": COMPARE_TOLERANCE,
    },
    "events": { 
        "face_recognition": True,
        "smoking": True,
        "violence": False,
        "checkincheckout": True,
        "person_detection": True,
        "scan_qr": True
    },
    "areas": {}
}

DEFAULT_EVENTS = {
    "face_recognition": True,
    "smoking": True,
    "violence": False,
    "checkincheckout": True,
    "person_detection": True,
    "scan_qr": True
}

def load_config():
    """Đọc file config.json"""
    if not os.path.exists(CONFIG_FILE):
        # ✅ Nếu file chưa tồn tại — tạo mới với cấu hình mặc định
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(CURRENT_CONFIG, f, indent=2, ensure_ascii=False)
        return CURRENT_CONFIG

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # ✅ Nếu thiếu trường "events" thì thêm mặc định
    if "events" not in cfg:
        cfg["events"] = {
            "face_recognition": True,
            "smoking": True,
            "violence": False,
            "checkincheckout": True,
            "person_detection": True,
            "scan_qr": True

        }

    return cfg

def save_config(cfg):
    """Lưu file config.json"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def apply_all_configs():
    """Áp dụng cấu hình realtime (nếu cần)"""
    global CURRENT_CONFIG
    CURRENT_CONFIG = load_config()
    print("⚡ [CONFIG RELOADED] Realtime applied.")

CURRENT_CONFIG = load_config()
if "events" not in CURRENT_CONFIG:
    CURRENT_CONFIG["events"] = DEFAULT_EVENTS.copy()

# API/Alarm
#  lấy cấu hình alarm
@app.route("/api/alarm-config/<int:area_id>/<int:camera_id>", methods=["GET"])
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
@app.route("/api/alarm-config", methods=["POST"])
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
@app.route("/api/alarm-config/apply/<int:area_id>", methods=["POST"])
def apply_realtime_config(area_id):
    """Áp dụng toàn bộ event_schedules realtime"""
    data = request.get_json()
    schedules = data.get("schedules", [])

    CURRENT_CONFIG.setdefault("areas", {}).setdefault(str(area_id), {})
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

@app.route("/api/alarm/play-audio", methods=["POST"])
def api_play_audio_alarm():
    """Phát âm thanh cảnh báo"""
    def _play():
        try:
            playsound(AUDIO_FILE)
        except Exception as e:
            print("[AUDIO ALERT ERR]", e)

    threading.Thread(target=_play, daemon=True).start()
    return jsonify({"ok": True, "message": "Playing alarm sound"})

@app.route('/static/events/<path:filename>')
def serve_event_media(filename):
    """Phục vụ file ảnh/video trong thư mục static/events."""
    events_dir = os.path.join(os.path.dirname(__file__), "static", "events")  # <-- thay os.getcwd()
    file_path = os.path.join(events_dir, filename)
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(events_dir, filename)

@app.route("/api/events/camera/<int:camera_id>", methods=["GET"])
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

@app.route("/events", methods=["GET"])
def api_list_events():
    limit = int(request.args.get("limit",500))
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

    except OperationalError as e:
        print("[DB ERROR] Connection lost:", e)
        return jsonify({"error": "Database connection lost"}), 500
    except Exception as e:
        print("[EVENTS API ERROR]", e)
        return jsonify({"error": str(e)}), 500

@app.route('/events/stream')
@cross_origin(origin='http://localhost:4200')
def stream_events():
    @stream_with_context
    def generate():
        while True:
            try:
                event = event_broadcast_queue.get(timeout=2)
                yield f"data: {json.dumps(event)}\n\n"
            except Empty:
                yield ":\n\n"
                time.sleep(1)
    return Response(generate(), mimetype='text/event-stream')

@app.route("/events/count", methods=["GET"])
def api_events_count():
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM events")
            count = cur.fetchone()[0]
    return jsonify({"count": count})

@app.route("/events/<event_id>", methods=["DELETE"])
def api_delete_event_api(event_id):
    deleted = delete_event_db(event_id)
    return jsonify({"deleted": deleted})

@app.route("/events/deleteall", methods=["DELETE"])
def api_delete_all_events_api():
    deleted = delete_all_events_db()
    return jsonify({"deleted": deleted})

# //////
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    """Phục vụ frontend (SPA build)."""
    static_folder = app.static_folder or "frontend"
    requested = os.path.join(static_folder, path)
    if path != "" and os.path.exists(requested):
        return send_from_directory(static_folder, path)
    return send_from_directory(static_folder, "index.html")

# admin
# --- ADMIN: CRUD AREA ---
@app.route("/areas", methods=["POST"])
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

# UPDATE AREA
@app.route("/areas/<int:area_id>", methods=["PUT"])
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

# DELETE AREA
@app.route("/areas/<int:area_id>", methods=["DELETE"])
def api_delete_area(area_id):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM areas WHERE id = %s", (area_id,))
    conn.close()
    return jsonify({"message": "Area deleted successfully"})

@app.route("/areas", methods=["GET"])
def api_get_areas():
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, description FROM areas ORDER BY id")
            rows = cur.fetchall()
    return jsonify([{"id": r[0], "name": r[1], "description": r[2]} for r in rows])

@app.route("/areas/<int:area_id>/cameras", methods=["GET"])
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

@app.route("/api/config/areas/<int:area_id>", methods=["GET"])
def api_get_area_config(area_id):
    cfg = sync_current_config()
    area_cfg = cfg.get("areas", {}).get(str(area_id), {"enabled_events": []})
    return jsonify(area_cfg)

@app.route("/api/config/areas/<int:area_id>", methods=["PUT"])
def api_save_area_config(area_id):
    """Lưu và merge cấu hình khu vực (sự kiện + vùng vẽ)."""
    global CURRENT_CONFIG
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
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(CURRENT_CONFIG, f, ensure_ascii=False, indent=2)

        print(f"💾 [CONFIG SAVED] Area {area_id} updated with {len(draw_areas)} draw area(s)")
        return jsonify({"status": "ok", "area_id": area_id})

    except Exception as e:
        import traceback
        print("[SAVE CONFIG ERROR]", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

#=================  camera
@app.route("/api/cameras", methods=["POST"])
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
    global cameras, camera_queues, frame_buffers
    if cam_id not in cameras and rtsp_url:
        try:
            cam = CameraThread(camera_id=cam_id, src=rtsp_url)
            cameras[cam_id] = cam
            camera_queues[cam_id] = queue.Queue(maxsize=1)
            frame_buffers[cam_id] = deque(maxlen=VIDEO_BUFFER_SECONDS * VIDEO_FPS)
            cam.start()
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

@app.route("/api/cameras/<int:camera_id>", methods=["PUT"])
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
    global cameras
    if camera_id in cameras:
        try:
            cameras[camera_id].stop()
            cameras[camera_id].join(timeout=2)
            del cameras[camera_id]
            print(f"[RELOAD] 🔁 Stopped old camera {camera_id}")
        except Exception as e:
            print(f"[RELOAD ERROR] {e}")

    try:
        # khởi động lại camera thread mới với rtsp_url mới
        rtsp_url = data["rtsp_url"]
        new_cam = CameraThread(camera_id=camera_id, src=rtsp_url)
        cameras[camera_id] = new_cam
        camera_queues[camera_id] = queue.Queue(maxsize=1)
        frame_buffers[camera_id] = deque(maxlen=VIDEO_BUFFER_SECONDS * VIDEO_FPS)
        new_cam.start()
        print(f"[RELOAD] 🚀 Restarted camera {camera_id} with new RTSP {rtsp_url}")
    except Exception as e:
        print(f"[RELOAD ERROR] Failed to restart camera {camera_id}: {e}")

    return jsonify({"message": "Camera updated and reloaded successfully"})


@app.route("/api/cameras/<int:camera_id>", methods=["DELETE"])
def api_delete_camera(camera_id):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cameras WHERE camera_id=%s", (camera_id,))
    conn.close()
    return jsonify({"message": "Camera deleted successfully"})

@app.route("/api/cameras", methods=["GET"])
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

@app.route("/api/cameras/<int:camera_id>/status", methods=["PUT"])
def api_toggle_camera_status(camera_id):
    """
    Bật hoặc tắt camera theo trạng thái 'status' gửi từ frontend.
    """
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
    global cameras
    if new_status == "inactive":
        # 🔴 Dừng camera
        if camera_id in cameras:
            try:
                cameras[camera_id].stop()
                cameras[camera_id].join(timeout=2)
                del cameras[camera_id]
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
                cam = CameraThread(camera_id=camera_id, src=rtsp_url)
                cam.start()
                cameras[camera_id] = cam
                camera_queues[camera_id] = queue.Queue(maxsize=1)
                frame_buffers[camera_id] = deque(maxlen=VIDEO_BUFFER_SECONDS * VIDEO_FPS)
                print(f"[STARTED] 🚀 Camera {camera_id} started with {rtsp_url}")
            else:
                print(f"[ERROR] No RTSP URL for camera {camera_id}")
        except Exception as e:
            print(f"[START ERROR] {e}")

    return jsonify({"message": f"Camera {camera_id} set to {new_status}"})

# --- ADMIN: CRUD NVR ---
@app.route("/api/nvrs", methods=["POST"])
def api_create_nvr():
    data = request.json
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nvrs (name, ip_address, port, username, password)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (data["name"], data["ip_address"], data["port"], data["username"], data["password"]))
            nvr_id = cur.fetchone()[0]
    conn.close()
    return jsonify({"id": nvr_id, "message": "NVR created successfully"}), 201
@app.route("/api/nvrs/<int:nvr_id>", methods=["PUT"])
def api_update_nvr(nvr_id):
    data = request.json or {}

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            # Lấy bản ghi hiện tại
            cur.execute("SELECT name, ip_address, port, username, password FROM nvrs WHERE id=%s", (nvr_id,))
            old = cur.fetchone()
            if not old:
                conn.close()
                return jsonify({"error": "NVR not found"}), 404

            # Gán giá trị mới (nếu không có thì giữ cũ)
            name = data.get("name", old[0])
            ip_address = data.get("ip_address", old[1])
            port = data.get("port", old[2])
            username = data.get("username", old[3])
            password = data.get("password", old[4])

            # Thực hiện cập nhật
            cur.execute("""
                UPDATE nvrs
                SET name=%s, ip_address=%s, port=%s, username=%s, password=%s
                WHERE id=%s
            """, (name, ip_address, port, username, password, nvr_id))
        conn.commit()
    conn.close()
    return jsonify({"message": "NVR updated successfully"})

@app.route("/api/nvrs/<int:nvr_id>", methods=["DELETE"])
def api_delete_nvr(nvr_id):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM nvrs WHERE id=%s", (nvr_id,))
    conn.close()
    return jsonify({"message": "NVR deleted successfully"})

# ------------------ PLAYBACK ------------------
@app.route("/api/nvrs", methods=["GET"])
def api_get_nvrs():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                id,
                name,
                ip_address,
                port,
                username,
                password
            FROM nvrs
            ORDER BY id;
        """)
        rows = cur.fetchall()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "name": r[1],
            "ip_address": r[2],
            "port": r[3],
            "username": r[4],
            "password": r[5]
        } for r in rows
    ])

@app.route("/api/nvrs-with-cameras", methods=["GET"])
def api_nvrs_with_cameras():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                n.id AS nvr_id, n.name AS nvr_name, n.ip_address, n.port,
                c.camera_id, c.name AS camera_name, c.status, c.area_id
            FROM nvrs n
            LEFT JOIN cameras c ON n.id = c.nvr_id
            ORDER BY n.id, c.camera_id
        """)
        rows = cur.fetchall()
    conn.close()

    nvrs = {}
    for r in rows:
        nvr_id = r[0]
        if nvr_id not in nvrs:
            nvrs[nvr_id] = {
                "id": nvr_id,
                "name": r[1],
                "ip": r[2],
                "port": r[3],
                "cameras": []
            }
        if r[4]:
            nvrs[nvr_id]["cameras"].append({
                "id": r[4],
                "name": r[5],
                "status": r[6],
                "area_id": r[7]
            })

    return jsonify(list(nvrs.values()))

@app.route("/api/playback/<string:event_id>", methods=["GET"])
def api_get_playback(event_id):
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT video_url FROM events WHERE id = %s", (event_id,))
            row = cur.fetchone()
        conn.close()

        if not row or not row[0]:
            return jsonify({"error": "Không tìm thấy video"}), 404
        event_time= row[0]
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
    
@app.route("/api/playback_segments/<int:camera_id>", methods=["GET"])
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

# phân quyền người dùn

@app.route("/api/nvrs/<int:nvr_id>/authenticate", methods=["POST"])
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


# ==========================================================
# 🔹 QUẢN LÝ TÀI KHOẢN NHÂN VIÊN
# ==========================================================
@app.route("/api/users/<int:person_id>/account", methods=["GET", "POST", "PUT", "DELETE"])
def api_user_account(person_id):
    conn = get_conn()
    cur = conn.cursor()

    # ---------------- GET ----------------
    if request.method == "GET":
        cur.execute("SELECT username FROM user_accounts WHERE person_id=%s", (person_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            # ⚠️ Trả 404 khi chưa có tài khoản để frontend nhận biết đúng
            return jsonify({"error": "no_account"}), 404

        return jsonify({"username": row[0]}), 200

    # ---------------- POST / PUT ----------------
    if request.method in ["POST", "PUT"]:
        data = request.get_json() or {}
        username = data.get("username")
        password = data.get("password")

        # Nếu là POST thì bắt buộc đủ username và password
        if request.method == "POST":
            if not username or not password:
                return jsonify({"error": "Thiếu username hoặc password"}), 400

            hashed = generate_password_hash(password)
            cur.execute(
                "INSERT INTO user_accounts (person_id, username, password) VALUES (%s, %s, %s)",
                (person_id, username, hashed)
            )
            conn.commit()
            conn.close()
            return jsonify({"message": "Tạo tài khoản thành công"}), 201

        # Nếu là PUT thì cho phép chỉ cập nhật 1 trong 2 trường
        update_fields = []
        params = []

        if username:
            update_fields.append("username=%s")
            params.append(username)

        if password:
            hashed = generate_password_hash(password)
            update_fields.append("password=%s")
            params.append(hashed)

        if not update_fields:
            conn.close()
            return jsonify({"error": "Không có dữ liệu để cập nhật"}), 400

        params.append(person_id)
        query = f"UPDATE user_accounts SET {', '.join(update_fields)} WHERE person_id=%s"
        cur.execute(query, tuple(params))
        conn.commit()
        conn.close()
        return jsonify({"message": "Cập nhật tài khoản thành công"}), 200

    # ---------------- DELETE ----------------
    if request.method == "DELETE":
        cur.execute("DELETE FROM user_accounts WHERE person_id=%s", (person_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Đã xóa tài khoản"}), 200

@app.route("/api/user_accounts", methods=["GET"])
def api_get_user_accounts():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT person_id, username FROM user_accounts")
        rows = cur.fetchall()
    conn.close()
    return jsonify([{"person_id": r[0], "username": r[1]} for r in rows])


@app.route("/api/auth/login", methods=["POST"])
def api_user_login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Thiếu username hoặc password"}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, password FROM user_accounts WHERE username=%s", (username,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Tài khoản không tồn tại"}), 401

    user_id, hashed = row

    if not check_password_hash(hashed, password):
        conn.close()
        return jsonify({"error": "Sai mật khẩu"}), 401

    # ✅ Lấy quyền của user
    cur.execute("SELECT code FROM user_permissions WHERE user_id=%s", (user_id,))
    permissions = [r[0] for r in cur.fetchall()]
    conn.close()

    return jsonify({
        "message": "Đăng nhập thành công",
        "username": username,
        "permissions": permissions
    })

# ==========================================================
# 🔹 PHÂN QUYỀN CHO NHÂN VIÊN
# ==========================================================
@app.route("/api/users/<int:person_id>/permissions", methods=["GET", "POST"])
def api_user_permissions(person_id):
    conn = get_conn()
    cur = conn.cursor()

    # 🔹 Lấy user_id từ bảng accounts
    cur.execute("SELECT user_id FROM user_accounts WHERE person_id=%s", (person_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "User chưa có tài khoản"}), 404

    user_id = row[0]

    if request.method == "GET":
        cur.execute("SELECT code FROM user_permissions WHERE user_id=%s", (user_id,))
        codes = [r[0] for r in cur.fetchall()]
        conn.close()
        return jsonify(codes)

    if request.method == "POST":
        data = request.get_json() or {}
        codes = data.get("codes", [])

        cur.execute("DELETE FROM user_permissions WHERE user_id=%s", (user_id,))
        for code in codes:
            cur.execute(
                "INSERT INTO user_permissions (user_id, code) VALUES (%s, %s)",
                (user_id, code)
            )
        conn.commit()
        conn.close()
        return jsonify({"message": "Cập nhật quyền thành công"})
    
@app.route("/api/users/<int:user_id>/permissions", methods=["POST"])
def assign_permissions(user_id):
    data = request.get_json() or {}
    codes = data.get("codes", [])

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM role_permissions WHERE role_id IN (SELECT role_id FROM user_roles WHERE user_id=%s)", (user_id,))
            cur.execute("SELECT role_id FROM user_roles WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO roles (name) VALUES (%s) RETURNING id", (f"user_{user_id}",))
                role_id = cur.fetchone()[0]
                cur.execute("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)", (user_id, role_id))
            else:
                role_id = row[0]

            for code in codes:
                cur.execute("SELECT id FROM permissions WHERE code=%s", (code,))
                perm = cur.fetchone()
                if perm:
                    cur.execute(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (role_id, perm[0])
                    )
    return jsonify({"status": "ok"})

# ------------------ FACES ------------------
@app.route("/faces", methods=["GET"])
def api_get_faces():
    load_db_cache()
    return jsonify([
        {
            "id": fid,
            "name": name,
            "image": img,
            "person_id": pid
        }
        for fid, name, img, pid in zip(_db_cache_ids, _db_cache_names, _db_cache_images, _db_cache_empids)
    ])

@app.route("/faces/assign", methods=["POST"])
def api_assign_face():
    data = request.json or {}
    face_id = data.get("face_id")
    name = data.get("name")

    if not face_id or not name:
        return jsonify({"error": "face_id and name required"}), 400

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT image_url FROM faces WHERE id=%s", (face_id,))
            row = cur.fetchone()
            image_url = row[0] if row else None

            if not image_url:
                pf = pending_faces.get(face_id)
                if pf and pf.get("image_b64"):
                    import base64
                    tmp_path = f"/tmp/{face_id}.jpg"
                    with open(tmp_path, "wb") as f:
                        f.write(base64.b64decode(pf["image_b64"]))
                    try:
                        upload = cloudinary.uploader.upload(tmp_path, folder="faces")
                        image_url = upload.get("secure_url")
                    except Exception as e:
                        print("[UPLOAD PENDING FACE ERROR]", e)

                        cur.execute("""
                            INSERT INTO persons (name, avatar)
                            VALUES (%s, %s)
                            ON CONFLICT (name) DO UPDATE SET avatar = COALESCE(persons.avatar, EXCLUDED.avatar)
                            RETURNING person_id
                        """, (name, image_url))

            person_id = cur.fetchone()[0]

            cur.execute("""
                UPDATE faces
                SET name=%s, person_id=%s, image_url=%s
                WHERE id=%s
            """, (name, person_id, image_url, face_id))

    global _db_cache_ts
    _db_cache_ts = 0

    return jsonify({"message": "Face assigned successfully", "person_id": person_id, "avatar": image_url})

@app.route("/faces/<face_id>", methods=["PUT"])
def api_update_face(face_id):
    data = request.json or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "name required"}), 400
    try:
        updated = update_db_name(face_id, name)
        if not updated:
            return jsonify({"error": "update_failed"}), 404
        return jsonify({"updated": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500 

@app.route("/faces/<face_id>", methods=["DELETE"])
def api_delete_face(face_id):
    try:
        deleted = delete_db_entry(face_id)
        if not deleted:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"deleted": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500 
    
# ------------------ PERSONS ------------------
@app.route("/pending_faces", methods=["GET"])
def api_get_pending_faces():
    with lock:
        result = [
            {
                "id": fid,
                "image_b64": f.get("image_b64"),
                "tempName": f.get("tempName", ""),
            }
            for fid, f in pending_faces.items()
        ]
    return jsonify(result)

@app.route("/pending_faces/assign", methods=["POST"])
def api_assign_pending_face():
    data = request.json or {}
    pending_id = data.get("pending_id")
    name = data.get("name")

    if not pending_id or not name:
        return jsonify({"error": "pending_id and name required"}), 400

    with lock:
        pf = pending_faces.pop(pending_id, None)
    if not pf:
        return jsonify({"error": "pending_face not found"}), 404

    image_url = None
    if pf.get("image_b64"):
        try:
            import base64, io, cloudinary.uploader
            img_bytes = base64.b64decode(pf["image_b64"])
            tmp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(tmp_dir, f"{pending_id}.jpg")
            with open(tmp_path, "wb") as f:
                f.write(img_bytes)
            upload = cloudinary.uploader.upload(tmp_path, folder="faces")
            image_url = upload.get("secure_url")
        except Exception as e:
            print("[UPLOAD PENDING FACE ERROR]", e)

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO persons (name, avatar)
                VALUES (%s, %s)
                ON CONFLICT (name) DO UPDATE SET avatar = EXCLUDED.avatar
                RETURNING person_id
            """, (name, image_url))
            person_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO faces (id, person_id, name, encoding, image_url)
                VALUES (gen_random_uuid(), %s, %s, %s, %s)
                RETURNING id
            """, (person_id, name, json.dumps(pf["encoding"]), image_url))
            face_id = cur.fetchone()[0]

    global _db_cache_ts
    _db_cache_ts = 0
    load_db_cache(force=True)

    return jsonify({
        "message": "Pending face assigned successfully",
        "face_id": str(face_id),
        "person_id": person_id,
        "name": name,
        "image_url": image_url
    })

@app.route("/pending_faces/<face_id>", methods=["DELETE"])
def api_delete_pending_face(face_id):
    with lock:
        if face_id in pending_faces:
            pending_faces.pop(face_id, None)
            return jsonify({"status": "deleted", "id": face_id})
    return jsonify({"error": "not_found"}), 404

@app.route("/persons/<int:person_id>/avatar", methods=["PUT"])
def api_set_avatar(person_id):
    data = request.json
    image = data.get("image")
    if not image:
        return jsonify({"error": "Missing image"}), 400
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE persons SET avatar=%s WHERE person_id=%s", (image, person_id))
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/persons/manual_add", methods=["POST"])
def api_manual_add_person():
    """
    API thêm nhân viên thủ công từ frontend, có thể kèm ảnh base64.
    """
    try:
        data = request.get_json() or {}
        name = data.get("name")
        image_b64 = data.get("image")

        if not name:
            return jsonify({"error": "Thiếu tên nhân viên"}), 400

        # Nếu có ảnh thì upload Cloudinary
        image_url = None
        if image_b64:
            import base64, tempfile, cloudinary.uploader
            img_bytes = base64.b64decode(image_b64)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(img_bytes)
            tmp.close()
            upload = cloudinary.uploader.upload(tmp.name, folder="faces")
            image_url = upload.get("secure_url")
            os.remove(tmp.name)

        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO persons (name, avatar)
                    VALUES (%s, %s)
                    ON CONFLICT (name) DO UPDATE SET avatar = EXCLUDED.avatar
                    RETURNING person_id
                """, (name, image_url))
                person_id = cur.fetchone()[0]

                if image_url:
                    cur.execute("""
                        INSERT INTO faces (id, person_id, name, encoding, image_url)
                        VALUES (gen_random_uuid(), %s, %s, '[]', %s)
                        RETURNING id
                    """, (person_id, name, image_url))

        global _db_cache_ts
        _db_cache_ts = 0

        return jsonify({
            "message": "Thêm nhân viên thủ công thành công",
            "person_id": person_id,
            "image_url": image_url
        }), 201

    except Exception as e:
        print("[MANUAL ADD ERROR]", e)
        return jsonify({"error": str(e)}), 500

@app.route("/persons", methods =["GET"])
def api_get_persons():
    conn = get_conn()
    with conn: 
        with conn.cursor() as cur:
            cur.execute("SELECT person_id, name, avatar, email, phone, department, position, created_at FROM persons")
            rows = cur.fetchall()
        return jsonify([
            {
                "person_id": r[0],
                "name": r[1],
                "avatar": r[2],
                "email": r[3],
                "phone": r[4],
                "department": r[5],
                "position": r[6],
                "created_at": r[7].isoformat() if r[7] else None     
            } for r in rows
        ])

@app.route("/persons/<int:person_id>", methods=["PUT"])
def api_update_person(person_id):
    data = request.json or {}
    fields = ["name", "email", "phone", "department", "position", "avatar"]
    updates, values = [], []
    for f in fields:
        if f in data:
            updates.append(f"{f}=%s")
            values.append(data[f])
    if not updates:
        return jsonify({"error": "no fields to update"}), 400
    values.append(person_id)

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE persons SET {', '.join(updates)} WHERE person_id=%s", values)
            if cur.rowcount == 0:
                return jsonify({"error": "person not found"}), 404
    return jsonify({"updated": True})

@app.route("/persons/<int:person_id>", methods=["DELETE"])
def api_delete_person(person_id):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT person_id FROM persons WHERE person_id = %s", (person_id,))
                if not cur.fetchone():
                    return jsonify({"error": "person_not_found"}), 404

                cur.execute("DELETE FROM faces WHERE person_id = %s", (person_id,))
                cur.execute("DELETE FROM persons WHERE person_id = %s", (person_id,))

        global _db_cache_ts
        _db_cache_ts = 0

        return jsonify({"deleted": True})
    except Exception as e:
        print("[DELETE PERSON ERROR]", e)
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@app.route("/upload/avatar", methods=["POST"])
def api_upload_avatar():
    """
    Upload ảnh base64 từ frontend -> Cloudinary -> trả về URL
    """
    try:
        data = request.get_json() or {}
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "Missing image"}), 400

        # Giải mã base64 -> file tạm
        import base64, tempfile
        img_bytes = base64.b64decode(image_b64)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp_file.write(img_bytes)
        tmp_file.close()

        # Upload Cloudinary
        import cloudinary.uploader
        upload_result = cloudinary.uploader.upload(tmp_file.name, folder="faces")
        image_url = upload_result.get("secure_url")

        os.remove(tmp_file.name)
        return jsonify({"status": "ok", "image_url": image_url})
    except Exception as e:
        print("[UPLOAD AVATAR ERROR]", e)
        return jsonify({"error": str(e)}), 500

#================== CONFIG ==================
def sync_current_config():
    global CURRENT_CONFIG
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                CURRENT_CONFIG = json.load(f)
        else:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(CURRENT_CONFIG, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[CONFIG LOAD ERROR]", e)
    return CURRENT_CONFIG

@app.route("/api/config", methods=["GET"])
def api_get_config():
    return jsonify(sync_current_config())

def save_current_config():
    """Ghi lại file config.json"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CURRENT_CONFIG, f, ensure_ascii=False, indent=2)

def apply_area_config(area_id: int):
    """Áp dụng cấu hình khu vực realtime"""
    area_cfg = CURRENT_CONFIG.get("areas", {}).get(str(area_id))
    if not area_cfg:
        print(f"[⚠️ APPLY AREA] Không tìm thấy cấu hình cho khu vực {area_id}")
        return False

def apply_all_configs():
    """Áp dụng toàn bộ cấu hình cho hệ thống"""
    for area_id in CURRENT_CONFIG.get("areas", {}):
        apply_area_config(int(area_id))
    # print("✅ [APPLY ALL CONFIG] Tất cả cấu hình khu vực đã được cập nhật realtime.")
    # print(f"✅ [APPLY AREA CONFIG] Khu vực {area_id} đã được áp dụng realtime.")
    return True

@app.route("/api/config", methods=["POST"])
def api_save_config():
    global CURRENT_CONFIG
    data = request.json or {}
    CURRENT_CONFIG.update(data)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CURRENT_CONFIG, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "ok", "config": CURRENT_CONFIG})

@app.route("/api/config", methods=["POST"])
def save_camera_config():
    global CURRENT_CONFIG
    data = request.json or {}
    cid = str(data.get("camera_id"))
    CURRENT_CONFIG.setdefault("cameras", {})
    CURRENT_CONFIG["cameras"][cid] = data
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CURRENT_CONFIG, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "ok", "config": CURRENT_CONFIG["cameras"][cid]})

def is_event_allowed(area_id, event_name):
    """Kiểm tra sự kiện có được phép theo thời gian cấu hình không"""
    area_cfg = CURRENT_CONFIG.get("areas", {}).get(str(area_id), {})
    schedules = area_cfg.get("event_schedules", {})

    # Nếu chưa cấu hình thì mặc định cho phép
    if event_name not in schedules:
        return True

    cfg = schedules[event_name]
    if not cfg.get("enabled", True) or not cfg.get("allowed", True):
        return False

    # kiểm tra thời gian trong ngày
    now = datetime.now().strftime("%H:%M")
    start = cfg.get("start", "00:00")
    end = cfg.get("end", "23:59")

    return start <= now <= end

@app.route("/api/config/event_schedule", methods=["POST"])
def api_update_event_schedule():
    """Cập nhật khung giờ cho phép sự kiện theo khu vực hoặc toàn hệ thống"""
    data = request.json or {}
    event_schedules = data.get("event_schedules", {})
    area_id = data.get("area_id")
    apply_realtime = data.get("apply_realtime", False)

    cfg = load_config()
    if not area_id:
        # Nếu không có area_id, cập nhật vào system-level
        cfg.setdefault("system", {})
        cfg["system"]["event_schedules"] = event_schedules
        print("🌐 [CONFIG] Updated global event schedule.")
    else:
        area_id = str(area_id)
        cfg.setdefault("areas", {})
        cfg["areas"].setdefault(area_id, {})
        cfg["areas"][area_id]["event_schedules"] = event_schedules
        print(f"🏠 [CONFIG] Updated event schedule for area {area_id}")

    save_config(cfg)

    if apply_realtime:
        apply_all_configs()
        print("⚡ [REALTIME] Event schedule applied immediately.")

    return jsonify({"status": "ok", "applied": apply_realtime})

# ------------------ VIDEO STREAM ------------------
def gen_frames(rtsp_url):
    cap = cv2.VideoCapture(rtsp_url)
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break
        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    cap.release()

@app.route('/video_feed/<int:camera_id>')
def video_feed(camera_id):
    """API stream video MJPEG cho 1 camera"""
    if camera_id not in cameras:
        return "Camera not found", 404
    return Response(
        gen_frames_for_camera(camera_id),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

# Log-file
@app.route("/api/logs", methods=["GET"])
def get_logs():
    """
    Lấy danh sách log sự kiện, có thể lọc theo ngày hoặc tháng
    Ví dụ:
    /api/logs?date=2025-10-16
    /api/logs?month=2025-10
    """
    date = request.args.get("date")
    month = request.args.get("month")

    conn = get_conn()
    with conn.cursor(dictionary=True) as cur:
        if date:
            cur.execute("SELECT * FROM event_log WHERE DATE(created_at) = %s ORDER BY created_at DESC", (date,))
        elif month:
            cur.execute("SELECT * FROM event_log WHERE DATE_FORMAT(created_at, '%Y-%m') = %s ORDER BY created_at DESC", (month,))
        else:
            cur.execute("SELECT * FROM event_log ORDER BY created_at DESC LIMIT 500")
        rows = cur.fetchall()
    conn.close()
    return jsonify(rows)

@app.route("/api/logs/export/excel", methods=["GET"])
def export_logs_excel():
    """
    Xuất toàn bộ log theo ngày/tháng ra file Excel
    """
    import pandas as pd
    from io import BytesIO
    from flask import send_file

    date = request.args.get("date")
    month = request.args.get("month")

    conn = get_conn()
    with conn.cursor(dictionary=True) as cur:
        if date:
            cur.execute("SELECT * FROM event_log WHERE DATE(created_at) = %s ORDER BY created_at DESC", (date,))
        elif month:
            cur.execute("SELECT * FROM event_log WHERE DATE_FORMAT(created_at, '%Y-%m') = %s ORDER BY created_at DESC", (month,))
        else:
            cur.execute("SELECT * FROM event_log ORDER BY created_at DESC")
        rows = cur.fetchall()
    conn.close()

    df = pd.DataFrame(rows)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    filename = f"logs_{date or month or 'all'}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

#  log qr
@app.route("/api/qr_logs", methods=["GET"])
def api_get_qr_logs():
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, camera_id, data, time
                FROM qr_logs
                ORDER BY time DESC
            """)
            rows = cur.fetchall()

        return jsonify([
            {
                "id": r[0],
                "camera_id": r[1],
                "data": r[2],
                "time": r[3].isoformat()
            }
            for r in rows
        ])
    except Exception as e:
        print("[QR_LOG API ERROR]", e)
        return jsonify({"error": str(e)}), 500

def gen_frames_for_camera(camera_id: int):
    while True:
        if camera_id not in cameras:
            time.sleep(0.1)
            continue
        frame = cameras[camera_id].latest_frame
        if frame is None:
            time.sleep(0.01)
            continue
        yield process_and_encode_frame(frame.copy(), camera_id)

def process_and_encode_frame(frame, cam_id):
    # draw faces
    with lock:
        frs = face_results.copy()
    for r in frs:
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
    lr = globals().get("last_pose_result", None)
    if lr and lr.get("cig_boxes"):
        for (cx1, cy1, cx2, cy2) in lr["cig_boxes"]:
            cv2.rectangle(frame, (cx1, cy1), (cx2, cy2), (255, 0, 0), 2)
            cv2.putText(frame, "cigarette", (cx1, max(30, cy1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

    ok, buf = cv2.imencode('.jpg', frame)
    if ok:
        return (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                + buf.tobytes() + b'\r\n')
    return b''

# ---------------- Main ----------------
def load_event_log():
    global EVENTS
    last_seen = {}
    EVENTS = json.load(open(LOG_FILE,"r",encoding="utf-8")) if os.path.exists(LOG_FILE) else []

def main(): 

    print("🚀 Starting Flask AI Server...")

    # conn = get_conn()
    # if not conn:
    #     print("⚠️ [DB] Database connection failed. Will retry later but not stopping server.")
    # else:
    #     conn.close()

    os.makedirs("violations", exist_ok=True)    
    init_db()
    load_event_log()
    load_db_cache(force=True)
    print(f"🧠 Loaded {len(_db_cache_names)} faces from database cache.")

    # load optional models
    try:
        lstm_model = load_model(LSTM_MODEL, compile=False) if os.path.exists(LSTM_MODEL) else None
        scaler = joblib.load(SCALER_FILE) if os.path.exists(SCALER_FILE) else None
        lbl_map = joblib.load(LABEL_FILE) if os.path.exists(LABEL_FILE) else {}
    except Exception as e:
        print("[MODEL LOAD ERROR]", e)
        lstm_model = None; scaler = None; lbl_map = {}

    try:
        pose_yolo = YOLO(POSE_MODEL)
        cig_yolo = YOLO(CIG_MODEL)
    except Exception as e:
        print("[YOLO LOAD ERROR]", e)
        return
    try:
        pose_yolo = YOLO(POSE_MODEL)
    except Exception as e:
        print("[YOLO LOAD ERROR - pose]", e)
        pose_yolo = None

    try:
        cig_yolo = YOLO(CIG_MODEL)
    except Exception as e:
        print("[YOLO LOAD ERROR - cig]", e)
        cig_yolo = None
#  đang triển khai
    try:
        yolo_person_model = YOLO(YOLO_PERSON_MODEL)
    except Exception as e:
        print("[YOLO LOAD ERROR - person]", e)

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            # cur.execute("SELECT camera_id, rtsp_url FROM cameras ORDER BY camera_id")
            # for cid, rtsp in rows:
            #     if rtsp:
            #         cam = CameraThread(camera_id=cid, src=rtsp)
            #         cameras[cid] = cam
            #         camera_queues[cid] = queue.Queue(maxsize=1)
            #         frame_buffers[cid] = deque(maxlen=VIDEO_BUFFER_SECONDS * VIDEO_FPS)
            #         cam.start()
            #         print(f"[MAIN] Started camera {cid}")
            cur.execute("SELECT camera_id, rtsp_url, status FROM cameras ORDER BY camera_id")
            rows = cur.fetchall()

            for cid, rtsp, status in rows:
                if rtsp and status == "active":
                    cam = CameraThread(camera_id=cid, src=rtsp)
                    cameras[cid] = cam
                    cam.start()
                    print(f"[MAIN] Started camera {cid}")
                else:
                    print(f"[MAIN] Camera {cid} is inactive → not started")

    global active_camera_id
    if rows:
        active_camera_id = rows[0][0]

    # start worker threads
    threading.Thread(target=save_worker, daemon=True).start()
    threading.Thread(target=recognition_thread, daemon=True).start()
    # threading.Thread(target=hand2mouth_thread, args=(pose_yolo,), daemon=True).start()
    # threading.Thread(target=cigarette_thread, args=(pose_yolo, cig_yolo), daemon=True).start()
    
    if yolo_person_model:
        threading.Thread(
            target=person_detection_thread,
            args=(yolo_person_model,),
            daemon=True
        ).start()

    if pose_yolo:
        threading.Thread(target=hand2mouth_thread, args=(pose_yolo,), daemon=True).start()
    if pose_yolo and cig_yolo:
        threading.Thread(target=cigarette_thread, args=(pose_yolo, cig_yolo, lstm_model, scaler, lbl_map), daemon=True).start()

    threading.Thread(target=qr_detection_thread, daemon=True).start()

    app.run(host="0.0.0.0", port=5000, threaded=True, use_reloader=False, debug=False)


    for cam in list(cameras.values()):
        cam.stop()

if __name__ == "__main__":
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                CURRENT_CONFIG.update(json.load(f))
            print("[CONFIG] 🔄 Loaded existing config.json")
        main()
    except Exception as e:
        print(f"[FATAL] ❌ Server crashed: {e}")
        import traceback
        traceback.print_exc()

