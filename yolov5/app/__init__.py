import os
import json
from flask import Flask
from flask_cors import CORS


from .config import CONFIG_FILE, load_config, sync_current_config
from .db import init_db, load_db_cache
from .routes import register_routes

from .areas import areas_bp
from .cameras import cameras_bp
from .events import events_bp

# global container for runtime state (cameras, queues, etc.)
RUNTIME = {
    "cameras": {},
    "camera_queues": {},
    "frame_buffers": {},
    "events": [],
    "pending_faces": {},
    "event_broadcast_queue": None, # will be created by threads module
}

def create_app():
    app = Flask(__name__, static_url_path="/static", static_folder="static")
    CORS(app, resources={r"/*": {"origins": "*"}})

# load configuration file once
    if os.path.exists(CONFIG_FILE):
        cfg = load_config()
    else:
        cfg = load_config()

# register blueprints lazily (routes will import db and utils)
def register_routes(app):
    app.register_blueprint(areas_bp, url_prefix='/api/areas')
    app.register_blueprint(cameras_bp, url_prefix='/api/cameras')
    app.register_blueprint(events_bp, url_prefix='/api/events')
    # register_routes(app)
    return app




def init_threads():
    """Hàm này sẽ được gọi khi server start để khởi tạo:
    - DB
    - load cache
    - load model (sẽ implement trong models module)
    - start các worker thread (sẽ implement trong threads module)
    """
    # init db and cache
    init_db()
    load_db_cache(force=True)


    # import models & threads here to avoid circular import at module import time
    try:
        from .threads import start_all_threads
        start_all_threads(RUNTIME)
        print("[INIT] Threads started")
    except Exception as e:
        print("[INIT ERROR] Failed to start threads:", e)