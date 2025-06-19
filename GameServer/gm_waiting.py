# gm_waiting    :   GameServer : 管理 waiting 階段邏輯
import json
import settings.context as ct
import GameServer.broadcaster as bc
# import time

def check_start_waiting(now):
    print(f"[Debug] 目前 ready_players: {ct.ready_players}")
    if len(ct.ready_players) > 0 and ct.game_phase == "waiting" and not ct.post_gameover_cooldown:
        ct.game_phase = "loading"
        ct.loading_start_time = now
        print(f"[GameServer] {len(ct.ready_players)} 名玩家按下 Ready，開始 loading 倒數 10 秒")

# 遊戲待機
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

    # 廣播 ready offer 給所有玩家
    await bc.broadcast(ready_offer_msg)
