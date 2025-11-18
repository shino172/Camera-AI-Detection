import os
import psycopg2
import uuid
import json
import time
import numpy as np
from psycopg2 import OperationalError
from psycopg2.extras import Json
from urllib.parse import urlparse
from datetime import datetime, timedelta
import pytz
from werkzeug.security import generate_password_hash, check_password_hash

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
DB_TABLE = "faces"
DB_CACHE_TTL = 5.0

# Global cache variables
_db_cache_encodings, _db_cache_names, _db_cache_ids, _db_cache_images, _db_cache_empids, _db_cache_ts = [], [], [], [], [], 0

def get_conn(retries=3, delay=2):
    """
    Kết nối PostgreSQL (Supabase / Neon / Localhost) có retry và SSL tự động.
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
            time.sleep(delay * (i + 1))

    print("❌ Không thể kết nối tới PostgreSQL sau nhiều lần thử. Server sẽ KHÔNG tắt.")
    return None

def init_db():
    """Khởi tạo database tables"""
    conn = get_conn()
    if not conn:
        return
        
    with conn:
        with conn.cursor() as cur:
            # PERSONS table
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

            # USERS table
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
            
            # AREAS table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS areas (
                    id SERIAL PRIMARY KEY,
                    code TEXT UNIQUE,
                    name TEXT,
                    description TEXT,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
            
            # NVRS table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nvrs (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    ip_address TEXT,
                    port INTEGER,
                    username TEXT,
                    password TEXT,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
            
            # CAMERAS table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cameras (
                    camera_id SERIAL PRIMARY KEY,
                    name TEXT,
                    nvr_id INTEGER REFERENCES nvrs(id),
                    area_id INTEGER REFERENCES areas(id),
                    channel INTEGER,
                    rtsp_url TEXT,
                    location TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
            
            # FACES table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS faces (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    person_id INTEGER REFERENCES persons(person_id),
                    name TEXT,
                    encoding JSONB,
                    image_url TEXT,
                    ts TIMESTAMPTZ DEFAULT now()
                );
            """)
            
            # EVENTS table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    person_id INTEGER REFERENCES persons(person_id),
                    camera_id INTEGER REFERENCES cameras(camera_id),
                    nvr_id INTEGER REFERENCES nvrs(id),
                    label TEXT,
                    method TEXT,
                    time TIMESTAMPTZ DEFAULT now(),
                    image_url TEXT,
                    video_url TEXT,
                    image_base64 TEXT
                );
            """)
            
            # QR_LOGS table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS qr_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    camera_id INTEGER REFERENCES cameras(camera_id),
                    data TEXT,
                    time TIMESTAMPTZ DEFAULT now()
                );
            """)
            
            # USER_ACCOUNTS table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_accounts (
                    user_id SERIAL PRIMARY KEY,
                    person_id INTEGER REFERENCES persons(person_id),
                    username TEXT UNIQUE,
                    password TEXT,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
            
            # USER_PERMISSIONS table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES user_accounts(user_id),
                    code TEXT,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
    conn.close()

def _load_db_raw():
    """Load raw face data from database"""
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
    """Load face encodings cache"""
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
    """Get or create person record"""
    cur.execute("SELECT person_id FROM persons WHERE LOWER(name) = LOWER(%s) LIMIT 1", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO persons (name) VALUES (%s) RETURNING person_id", (name,))
    return cur.fetchone()[0]

def append_db_entry(name, encoding, image_url=None):
    """Add new face to database"""
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
    """Delete face from database"""
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
    """Update face name in database"""
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
    """Get NVR ID by camera ID"""
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
    """Save event to database"""
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
    """Update event media"""
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
    """Get event information"""
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
                "end_time": row[2] + timedelta(minutes=1)
            }
    finally:
        conn.close()

def delete_event_db(event_id: str):
    """Delete event from database"""
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
    """Delete all events from database"""
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

def save_qr_log(camera_id, data, timestamp=None):
    """Save QR log to database"""
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

def get_area_by_camera(camera_id):
    """Get area ID by camera ID"""
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

def get_area_name(area_id):
    """Get area name by area ID"""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM areas WHERE id=%s", (area_id,))
            row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None