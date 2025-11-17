import threading
from playsound import playsound
import os


def play_alarm(audio_file):
    if not os.path.exists(audio_file):
        print(f"[AUDIO] Missing: {audio_file}")
        return


    def _play():
        try:
          playsound(audio_file)
        except Exception as e:
            print("[AUDIO ERR]", e)

    threading.Thread(target=_play, daemon=True).start()