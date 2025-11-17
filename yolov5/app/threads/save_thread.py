import threading, queue, cv2, os, base64

save_queue = queue.Queue()
def save_worker():
    while True:
        job = save_queue.get()
        if job is None:
            break
        kind, data = job
        if kind == 'image':
            path = os.path.join('static/events', data['path'])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            frame = data['frame']
            cv2.imwrite(path, frame)
            print(f"[SAVE] Image saved: {path}")
        elif kind == 'video':
            print("[TODO] Implement video saving")