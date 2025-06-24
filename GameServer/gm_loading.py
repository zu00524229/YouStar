# gm_loading.py     :   GameServer : 管理 loading 邏輯

import time
import math
import settings.context as ct
import GameServer.broadcaster as bc

# 確認是否可以進入 loading 階段（通常由 ready → loading 時呼叫）
# async def check_start_loading(now):
#     if ct.ready_players:
#         ct.game_phase = "loading"
#         ct.loading_start_time = now
#         ct.last_loading_broadcast = 0  # 重設倒數廣播計時器

#         print(f"[GameServer] 準備進入 loading 階段，ready_players: {ct.ready_players}")

#         await bc.broadcast_status_update()     # loading 廣播器
#         print("[GameServer]  已送出 status_update → loading")

#         ct.phase_changed_event.set()

# 處理 loading 邏輯
async def handle_loading_phase():
    if ct.loading_start_time is None:
        return  # 尚未開始倒數

    now = time.time()
    # 更新遊戲分數資料（從 ready 或全體玩家
    elapsed_loading = now - ct.loading_start_time
    loading_time_left = max(0, math.ceil(ct.loading_time - elapsed_loading))

    # --- 新增：每秒廣播一次 loading 倒數 ---
    if not hasattr(ct, "last_loading_broadcast") or now - ct.last_loading_broadcast >= 1:
        ct.last_loading_broadcast = now


        await bc.broadcast_status_update()  # 廣播 
        print(f"[GameServer] 廣播 loading 倒數中... 剩餘 {loading_time_left}s")

    # --- 倒數完成，轉入 playing 階段 ---
    if loading_time_left == 0 and ct.game_phase == "loading":
        ct.game_phase = "playing"
        ct.game_start_time = now

        active_players = ct.ready_players if ct.ready_players else ct.connected_players
        ct.current_scores = {username: 0 for username in active_players}

        await bc.broadcast_status_update()  # 廣播進入playing 狀態
        print("[GameServer] loading 完成 → 廣播進入 playing 階段")

        # 通知地鼠 sender 開始運作
        ct.phase_changed_event.set()
        print("[GameServer] phase_changed_event.set() 完成")

        return  # 避免後面再次執行倒數

