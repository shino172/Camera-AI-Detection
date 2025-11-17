import threading, time, queue


class RecognitionThread(threading.Thread):
    def __init__(self, face_queue, recognize_fn):
        super().__init__(daemon=True)
        self.face_queue = face_queue
        self.recognize_fn = recognize_fn


    def run(self):
        while True:
            try:
                frame = self.face_queue.get(timeout=1)
                results = self.recognize_fn(frame)
                if results:
                    print(f"[RECOG] Found {len(results)} faces")
            except queue.Empty:
                continue