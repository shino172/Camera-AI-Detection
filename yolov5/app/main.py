import os
import cv2
import time
import json
import uuid
import base64
import joblib
import face_recognition
import cloudinary
import psycopg2
import tempfile
import ctypes
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

# Load environment variables
load_dotenv()

# Import global variables
from app.globals import *

# Import from our modules
from app.utils.config import load_config, CURRENT_CONFIG, CONFIG_FILE
from app.models.database import get_conn, init_db
from app.threads.camera_thread import CameraThread, add_camera, stop_camera, switch_camera
from app.threads.recognition_thread import recognition_thread
from app.threads.detection_threads import (
    hand2mouth_thread, 
    cigarette_thread, 
    person_detection_thread,
    qr_detection_thread
)
from app.threads.save_worker import save_worker

# Configuration constants
TARGET_SIZE = (1920, 1080)
FRAME_WAIT = 0.033
RECOGNITION_INTERVAL = 0.1
COMPARE_TOLERANCE = 0.45
PENDING_EXPIRY = 60.0
PENDING_MIN_DIST = 0.4
IOU_THRESHOLD = 0.50
HAND_TO_MOUTH_DIST = 30
COOLDOWN = 15
VIDEO_DURATION = 15
FPS = 20
HOLD_TIME = 5
MAX_EVENTS = 400
MIN_DIST_DB = 0.38
FACE_MATCH_MAX_AGE = 1.5

VIDEO_BUFFER_SECONDS = 5
VIDEO_AFTER_SECONDS = 25
VIDEO_TOTAL_SECONDS = VIDEO_BUFFER_SECONDS + VIDEO_AFTER_SECONDS
VIDEO_FPS = FPS

VIDEO_PATH = os.path.join(os.getcwd(), "static", "events")
PLAYBACK_DIR = os.path.join(os.getcwd(), "static", "playback")
LOCAL_IMAGE_DIR = os.path.join("static", "faces")
LOCAL_EVENT_DIR = os.path.join("static", "events")
AUDIO_FILE = os.path.join("static", "sounds", "alarm.mp3")

# Create directories
os.makedirs(VIDEO_PATH, exist_ok=True)
os.makedirs(PLAYBACK_DIR, exist_ok=True)
os.makedirs(LOCAL_IMAGE_DIR, exist_ok=True)
os.makedirs(LOCAL_EVENT_DIR, exist_ok=True)

def create_app():
    app = Flask(__name__, static_url_path="/static", static_folder="static")
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Load configuration
    global CURRENT_CONFIG
    CURRENT_CONFIG = load_config()
    
    return app

app = create_app()

# Register blueprints
from app.api.events import bp as events_bp
from app.api.cameras import bp as cameras_bp
from app.api.faces import bp as faces_bp
from app.api.persons import bp as persons_bp
from app.api.areas import bp as areas_bp
from app.api.nvrs import bp as nvrs_bp
from app.api.config import bp as config_bp
from app.api.auth import bp as auth_bp
from app.api.playback import bp as playback_bp
from app.api.alarms import bp as alarms_bp
from app.api.logs import bp as logs_bp

app.register_blueprint(events_bp)
app.register_blueprint(cameras_bp)
app.register_blueprint(faces_bp)
app.register_blueprint(persons_bp)
app.register_blueprint(areas_bp)
app.register_blueprint(nvrs_bp)
app.register_blueprint(config_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(playback_bp)
app.register_blueprint(alarms_bp)
app.register_blueprint(logs_bp)

def start_worker_threads():
    """Start all background threads"""
    
    # Load models
    try:
        pose_yolo = YOLO("yolov8n-pose.pt")
        cig_yolo = YOLO("best.pt")
        yolo_person_model = YOLO("yolo11n.pt")
    except Exception as e:
        print(f"[MODEL LOAD ERROR] {e}")
        return

    # Start worker threads
    threading.Thread(target=save_worker, daemon=True).start()
    threading.Thread(target=recognition_thread, daemon=True).start()
    threading.Thread(target=person_detection_thread, args=(yolo_person_model,), daemon=True).start()
    threading.Thread(target=hand2mouth_thread, args=(pose_yolo,), daemon=True).start()
    threading.Thread(target=cigarette_thread, args=(pose_yolo, cig_yolo, None, None, {}), daemon=True).start()
    threading.Thread(target=qr_detection_thread, daemon=True).start()

    print("✅ All worker threads started")

def load_cameras_from_db():
    """Load cameras from database and start them"""
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT camera_id, rtsp_url, status FROM cameras ORDER BY camera_id")
            rows = cur.fetchall()

            for cid, rtsp, status in rows:
                if rtsp and status == "active":
                    add_camera(cid, rtsp)
                    print(f"[MAIN] Started camera {cid}")
                else:
                    print(f"[MAIN] Camera {cid} is inactive → not started")

    global active_camera_id
    if rows:
        active_camera_id = rows[0][0]

def main():
    print("🚀 Starting Flask AI Server...")
    
    # Initialize database
    init_db()
    
    # Load cameras from database
    load_cameras_from_db()
    
    # Start worker threads
    start_worker_threads()
    
    # Start Flask app
    app.run(host="0.0.0.0", port=5000, threaded=True, use_reloader=False, debug=False)

    # Cleanup
    for cam in list(cameras.values()):
        cam.stop()

if __name__ == "__main__":
    main()