# gm_loading.py     :   GameServer : 管理 loading 邏輯

import time
import math
import settings.context as ct


# 處理 loading 邏輯
async def handle_loading_phase():
    if ct.loading_start_time is None:
        return  # 尚未開始倒數

    now = time.time()
    elapsed_loading = now - ct.loading_start_time
    loading_time_left = max(0, math.ceil(ct.loading_time - elapsed_loading))

    if loading_time_left == 0 and ct.game_phase == "loading":
        ct.game_phase = "playing"
        ct.game_start_time = now
        # ct.current_scores = {username: 0 for username in ct.ready_players or ct.connected_players}
        active_players = ct.ready_players if ct.ready_players else ct.connected_players
        ct.current_scores = {username: 0 for username in active_players}


        if ct.ready_players:
            print("[GameServer] ready 模式 → loading 完成，進入 playing")
        else:
            print("[GameServer] 首局 loading 完成 → 進入 playing")

        print("[GameServer] loading 完成 → 進入 playing 60 秒")
        ct.phase_changed_event.set()
        print("[GameServer] phase_changed_event.set() 完成")
