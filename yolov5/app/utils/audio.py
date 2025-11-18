import os
import threading
from playsound import playsound

AUDIO_FILE = os.path.join("static", "sounds", "alarm.mp3")

def play_audio_alarm():
    """Phát âm thanh cảnh báo (chạy trong thread riêng để không block)."""
    if not os.path.exists(AUDIO_FILE):
        print(f"[AUDIO ALERT] ⚠️ Không tìm thấy file âm thanh: {AUDIO_FILE}")
        return
    def _play():
        try:
            playsound(AUDIO_FILE)
        except Exception as e:
            print("[AUDIO ALERT ERROR]", e)
    threading.Thread(target=_play, daemon=True).start()