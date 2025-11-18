import cv2
import threading
import time
import queue
from collections import deque
from app.globals import cameras, camera_queues, frame_buffers, active_camera_id

# Configuration
TARGET_SIZE = (1920, 1080)
VIDEO_BUFFER_SECONDS = 5
VIDEO_FPS = 20

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

            # 🟢 Đưa frame cho các thread nhận diện
            self.distribute_frame_to_queues(f.copy())

            time.sleep(0.005)

    def distribute_frame_to_queues(self, frame):
        """Distribute frame to all processing queues"""
        from app.globals import face_queue, pose_queue, cig_queue, person_queue, qr_queue
        
        queues_to_feed = [
            (face_queue, "face"),
            (pose_queue, "pose"), 
            (cig_queue, "cig"),
            (person_queue, "person"),
            (qr_queue, "qr")
        ]
        
        for queue_obj, queue_name in queues_to_feed:
            try:
                if queue_obj.full():
                    queue_obj.get_nowait()
                queue_obj.put_nowait((self.camera_id, frame.copy()))
            except:
                pass

    def stop(self):
        self.running = False
        try:
            self.cap.release()
        except:
            pass
    
    def get_frame(self):
        return self.latest_frame

def add_camera(camera_id, src):
    """Add new camera to system"""
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
    """Stop camera thread"""
    global cameras
    if camera_id not in cameras:
        print(f"[CAMERA] không tìm thấy camera {camera_id}")
        return False
    cameras[camera_id].stop()
    cameras[camera_id].join(timeout=2)
    del cameras[camera_id]
    print(f"[CAMERA] Camera {camera_id} đã dừng")
    return True

def switch_camera(camera_id):
    """Switch active camera"""
    global active_camera_id
    if camera_id not in cameras:
        print(f"[CAMERA] Không tìm thấy camera {camera_id}")
        return False
    active_camera_id = camera_id
    print(f"[CAMERA] Chuyển sang camera {camera_id}")
    return True