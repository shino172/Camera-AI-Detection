import time
import os
from urllib.parse import urlparse
import psycopg2
from psycopg2 import OperationalError

from .config import DATABASE_URL

def get_conn(retries=3, delay=2):
    """Get a psycopg2 connection with simple retry and ssl handle for supabase/neon."""
    global DATABASE_URL
    if not DATABASE_URL:
        raise RuntimeError("Missing DATABASE_URL environment variable")


    parsed = urlparse(DATABASE_URL)
    if any(x in (parsed.hostname or "") for x in ["supabase", "neon.tech", "render"]):
        if "sslmode" not in DATABASE_URL:
            if "?" in DATABASE_URL:
                DATABASE_URL += "&sslmode=require"
            else:
                DATABASE_URL += "?sslmode=require"
    elif "localhost" in (parsed.hostname or "") or "127.0.0.1" in (parsed.hostname or ""):
        if "sslmode" not in DATABASE_URL:
            if DATABASE_URL.endswith("/"):
                DATABASE_URL = DATABASE_URL[:-1]
        DATABASE_URL += "?sslmode=disable"


    for i in range(retries):
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            conn.autocommit = True
            return conn
        except OperationalError as e:
            time.sleep(delay * (i + 1))
    return None

def init_db():
    """Create minimal tables if not exist. (copy from original)
    You can expand table creation later.
    """
    conn = get_conn()
    if not conn:
        print("[DB] Cannot connect to DB to init")
        return


    with conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
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


            cur.execute("""
            CREATE TABLE IF NOT EXISTS faces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            person_id INT,
            name TEXT,
            encoding JSONB,
            image_url TEXT
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    person_id INT,
                    camera_id INT,
                    label TEXT,
                    method TEXT,
                    time TIMESTAMPTZ DEFAULT now(),
                    image_url TEXT,
                    video_url TEXT
                    );
                    """)
        try:
            conn.close()
        except:
            pass
    # cache loader placeholder
_db_cache_encodings = []
_db_cache_names = []
_db_cache_ts = 0
DB_CACHE_TTL = 5.0
def _load_db_raw():
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id::text, person_id, name, encoding, image_url, ts FROM faces ORDER BY ts DESC")
            rows = cur.fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        result.append({
        "id": r[0],
        "person_id": r[1],
        "name": r[2],
        "encoding": r[3],
        "image_url": r[4],
        "ts": r[5]
        })
    return

def load_db_cache(force: bool = False):
    global _db_cache_encodings, _db_cache_names, _db_cache_ts
    now = time.time()
    if not force and now - _db_cache_ts < DB_CACHE_TTL and _db_cache_encodings:
        return
    raw = _load_db_raw()
    _db_cache_encodings = [r.get('encoding') for r in raw if r.get('encoding')]
    _db_cache_names = [r.get('name') for r in raw]
    _db_cache_ts = now