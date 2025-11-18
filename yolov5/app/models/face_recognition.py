import cv2
import face_recognition
import numpy as np
import time
import uuid
import base64
import threading
from scipy.spatial import distance
from .database import load_db_cache, _db_cache_encodings, _db_cache_names, _db_cache_empids

# Global variables
pending_faces = {}
lock = threading.Lock()
face_results = []
face_lock = threading.Lock()
last_recognition_time = 0

# Configuration
COMPARE_TOLERANCE = 0.45
PENDING_EXPIRY = 60.0
PENDING_MIN_DIST = 0.4
RECOGNITION_INTERVAL = 0.1

def crop_face(frame_bgr, loc, pad=40):
    """Crop face from frame with padding"""
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
    """Convert face image to base64"""
    ok, buf = cv2.imencode(".jpg", face_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8") if ok else None

def recognize_on_frame(frame_bgr):
    """Recognize faces in frame"""
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

def add_pending_face(frame, loc, encoding):
    """Add pending face for manual assignment"""
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