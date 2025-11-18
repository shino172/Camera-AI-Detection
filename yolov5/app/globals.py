"""
File chứa tất cả các biến global để tránh circular imports
"""
import queue
import threading
from collections import deque

# Global queues
face_queue = queue.Queue(maxsize=1)
pose_queue = queue.Queue(maxsize=1)
cig_queue = queue.Queue(maxsize=1)
person_queue = queue.Queue()
qr_queue = queue.Queue(maxsize=1)
save_queue = queue.Queue()
event_broadcast_queue = queue.Queue()

# Global variables
face_results = []
face_lock = threading.Lock()
alert_frames = {}
last_pose_result = None
last_seen = {}
checkin_status = {}
pending_faces = {}
lock = threading.Lock()
last_recognition_time = 0

# Camera management
cameras = {}
camera_queues = {}
frame_buffers = {}
active_camera_id = None

# Events
EVENTS = []