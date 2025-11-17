import cv2, time, queue, threading
from collections import deque


class CameraThread(threading.Thread):
    def __init__(self, camera_id, src, target_size=(1280,720)):
        super().__init__()
        self.camera_id = camera_id
        self.src = src
        self.cap = cv2.VideoCapture(src)
        self.running = True
        self.latest_frame = None


    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
                continue
        self.latest_frame = frame.copy()
        time.sleep(0.01)


    def stop(self):
        self.running = False
        try:
            self.cap.release()
        except:
            pass