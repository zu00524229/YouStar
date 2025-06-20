# gm_waiting.py    :   GameServer : 管理 waiting 階段邏輯
import json
import settings.context as ct
import GameServer.broadcaster as bc
# import time

# 檢查是否可從 waiting 轉入 loading 階段
async def check_start_waiting(now):
    # print(f"[Debug] 目前 ready_players: {ct.ready_players}")
    if len(ct.ready_players) > 0 and ct.game_phase == "waiting" and not ct.post_gameover_cooldown:
        ct.game_phase = "loading"
        ct.loading_start_time = now
        print(f"[GameServer] {len(ct.ready_players)} 名玩家按下 Ready，開始 loading 倒數 10 秒")
        print("[GameServer] 已成功進入 loading 階段，準備廣播")
        await bc.broadcast_loading_status()    # 呼叫 loading 狀態

# 每秒由主迴圈呼叫：綜合處理 waiting 階段邏輯
async def handle_waiting_phase(now):
    if not ct.post_gameover_cooldown:
        await check_start_waiting(now)

    if ct.ready_offer_active:
        if ct.loading_start_time is not None:
            await handle_ready_offer(now)
        else:
            print("[GameServer] loading_start_time 是 None，略過 handle_ready_offer")

# 廣播 Ready 倒數進度（ready_offer_update）
async def handle_ready_offer(now):
    if ct.loading_start_time is None:
        print("[GameServer] loading_start_time 尚未設置，略過 ready_offer")
        return

    elapsed = now - ct.loading_start_time
    remaining_time = max(0, ct.loading_time - int(elapsed))

    ready_offer_msg = {
        "event": "ready_offer_update",
        "remaining_time": remaining_time,
        "joined_players": len(ct.ready_players),
        "joined_usernames": list(ct.ready_players),
        "total_players": len(ct.connected_players),
    }

    await bc.broadcast(ready_offer_msg)
    print(f"[GameServer] 廣播 ready_offer 倒數中... 剩餘 {remaining_time}s")
