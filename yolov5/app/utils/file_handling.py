import os
import json
import uuid
from datetime import datetime
import pytz
from app.models.database import get_conn, save_event_to_db, get_area_by_camera, get_area_name

def save_event_log(event):
    """Save event to log file and database"""
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
                    datetime.now(pytz.utc),
                    image_url,
                    video_url
                ))

                event["id"] = event_id
                event["image_url"] = image_url
                event["video_url"] = video_url

        conn.close()
        
        # Add to global events list (if exists)
        global EVENTS
        if 'EVENTS' in globals():
            EVENTS.insert(0, event)
            if len(EVENTS) > 500:  # MAX_EVENTS
                EVENTS.pop()

        # Save to JSON file
        json.dump(EVENTS, open("events.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[DB] Event saved locally: {event_id} ({event.get('label')})")

    except Exception as e:
        print("[SAVE EVENT DB ERROR]", e)