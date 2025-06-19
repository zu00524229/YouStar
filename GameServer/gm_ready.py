# gm_ready.py
import time
import settings.context as ct
import GameServer.broadcaster as bc
import GameServer.gm_waiting as waiting

async def handle_ready(username):
    now = time.time()

    # 註冊 ready 狀態
    ct.ready_offer_active = True
    ct.ready_players = {username}
    ct.loading_start_time = now

    print(f"[GameServer] 玩家 {username} 已加入 ready，檢查是否要進入 loading 階段")

    # 嘗試進入 loading 階段（→ 若 ready 玩家足夠）
    await waiting.check_start_waiting(now)
