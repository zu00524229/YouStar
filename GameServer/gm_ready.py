# gm_ready.py
import time
import settings.context as ct
import GameServer.broadcaster as bc
import asyncio

# 開始遊戲
async def handle_ready(username):
    # 玩家點擊 Ready 時呼叫
    if not hasattr(ct, "ready_players") or not isinstance(ct.ready_players, set):
        ct.ready_players = set()
    
    ct.ready_offer_active = True
    ct.ready_players.add (username)
    print(f"[GameServer] 玩家 {username} 已加入 ready，目前 ready 玩家: {ct.ready_players}")

# 啟動 loading 階段，不需要等待其他玩家，直接開始倒數
    if ct.game_phase == "waiting":
        ct.game_phase = "loading"
        ct.loading_start_time = time.time()
        ct.last_loading_broadcast = 0  # reset timer
        print("[GameServer] 已進入 loading 階段，開始倒數 10 秒")
        await bc.broadcast_status_update()  # 廣播 loading 狀態
        ct.phase_changed_event.set()  # 觸發階段更動
    # 不再設定 loading_start_time，不直接切 phase

