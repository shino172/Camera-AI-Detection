from pyzbar.pyzbar import decode
import cv2

def decode_qr_code(frame):
    """Decode QR codes from frame"""
    try:
        results = decode(frame)
        decoded_data = []
        for qr in results:
            data = qr.data.decode("utf-8")
            x, y, w, h = qr.rect
            decoded_data.append({
                "data": data,
                "bbox": [x, y, x + w, y + h]
            })
        return decoded_data
    except Exception as e:
        print(f"[QR DECODE ERROR] {e}")
        return []