# utils.py
import time
import settings.context as ct

def get_remaining_time():
    now = time.time()
    if ct.game_phase == "playing" and ct.game_start_time is not None:
        return max(0, ct.GAME_DURATION - int(now - ct.game_start_time))
    elif ct.game_phase == "loading" and ct.loading_start_time is not None:
        return max(0, 10 - int(now - ct.loading_start_time))
    else:
        return 0

