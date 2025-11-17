import cv2
from pyzbar.pyzbar import decode
import time
import uuid
import os

CAMERA_SOURCE = 0   # ⚠️ đổi thành link RTSP để test camera thật

# ==============================
# TẠO FOLDER LƯU ẢNH
# ==============================

SAVE_DIR = "qr_captures"
os.makedirs(SAVE_DIR, exist_ok=True)

def main():
    cap = cv2.VideoCapture(CAMERA_SOURCE)

    if not cap.isOpened():
        print("❌ Không mở được camera:", CAMERA_SOURCE)
        return

    print("📷 Đang mở camera… Nhấn Q để thoát")

    last_scan = {}

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Không đọc được frame")
            break

        # Resize nhỏ lại cho mượt hơn
        frame = cv2.resize(frame, (960, 540))

        # ===== QUÉT QR =====
        qr_codes = decode(frame)

        for qr in qr_codes:
            (x, y, w, h) = qr.rect
            data = qr.data.decode("utf-8")

            # vẽ khung QR
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, data, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # tránh spam
            if data not in last_scan or time.time() - last_scan[data] > 3:
                print("🔍 QR DETECTED:", data)
                last_scan[data] = time.time()

                # chụp ảnh QR
                file_name = f"qr_{uuid.uuid4().hex}.jpg"
                crop = frame[y:y+h, x:x+w]
                cv2.imwrite(os.path.join(SAVE_DIR, file_name), crop)
                print(f"📸 Đã lưu ảnh QR vào: {SAVE_DIR}/{file_name}")

        # hiển thị
        cv2.imshow("QR Scanner Test", frame)

        # nhấn Q để thoát
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
