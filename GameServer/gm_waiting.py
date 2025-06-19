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
    if ct.ready_offer_start_time is None:
        print("[GameServer] ready_offer_start_time 尚未設置，略過 ready_offer")
        return

    elapsed_ready_offer = now - ct.ready_offer_start_time
    ready_offer_remaining_time = max(0, ct.loading_time - int(elapsed_ready_offer))

    ready_offer_msg = {
        "event": "ready_offer_update",
        "remaining_time": ready_offer_remaining_time,
        "joined_players": len(ct.ready_players),
        "joined_usernames": list(ct.ready_players),
        "total_players": len(ct.connected_players),
    }

    # 廣播 ready offer 給所有玩家
    await bc.broadcast(ready_offer_msg)

    if ready_offer_remaining_time == 0:
        print("[GameServer] ready Offer 倒數結束，開始新局")

        await bc.broadcast({
            "event": "ready_end"
        })

        ct.ready_offer_active = False
        ct.game_phase = "playing"       # 直接開始遊戲，不用再loading
        ct.game_start_time = now                # 補上這行（關鍵）
        ct.loading_start_time = None            # 確保不進入 loading
        ct.current_scores = {username: 0 for username in ct.ready_players}
        ct.observer_players = ct.connected_players - ct.ready_players
        ct.phase_changed_event.set()            # 通知 mole_sender 啟動
