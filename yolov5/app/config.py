import os
import cloudinary
from dotenv import load_dotenv

load_dotenv()

CONFIG_FILE = "config.json"
DATABASE_URL = os.getenv("DATABASE_URL")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")


if not DATABASE_URL:
    print("[WARN] DATABASE_URL is not set in environment")
# Configure cloudinary if keys present
if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

# Models & files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSE_MODEL = os.getenv("POSE_MODEL", "yolov8n-pose.pt")
CIG_MODEL = os.getenv("CIG_MODEL", os.path.join(BASE_DIR, "..", "runs", "train", "smoking_detector", "weights", "best.pt"))


TARGET_SIZE = (1920, 1080)
FPS = int(os.getenv("FPS", 20))
VIDEO_BUFFER_SECONDS = int(os.getenv("VIDEO_BUFFER_SECONDS", 5))
VIDEO_AFTER_SECONDS = int(os.getenv("VIDEO_AFTER_SECONDS", 25))


AUDIO_FILE = os.path.join(os.path.dirname(BASE_DIR), "static", "sounds", "alarm.mp3")


# Face settings (defaults copied)
RECOGNITION_INTERVAL = float(os.getenv("RECOGNITION_INTERVAL", 0.1))
COMPARE_TOLERANCE = float(os.getenv("COMPARE_TOLERANCE", 0.45))


# default current config
CURRENT_CONFIG = {
    "system": {
    "recognition_interval": RECOGNITION_INTERVAL,
    "compare_tolerance": COMPARE_TOLERANCE,
    },
    "events": {
    "face_recognition": True,
    "smoking": True,
    "violence": False,
    "checkincheckout": True
    },
    "areas": {}
}

def load_config():
    import json
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg
        except Exception:
            return CURRENT_CONFIG
    else:
    # create default config
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(CURRENT_CONFIG, f, ensure_ascii=False, indent=2)
    return CURRENT_CONFIG

def sync_current_config():
    cfg = load_config()
    return cfg