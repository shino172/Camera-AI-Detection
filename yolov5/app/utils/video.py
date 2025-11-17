import cv2


def encode_frame(frame):
    ok, buf = cv2.imencode('.jpg', frame)
    if ok:
        return (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
    return b''