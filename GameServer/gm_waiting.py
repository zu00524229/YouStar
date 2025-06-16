# GameServer : 管理 waiting 階段邏輯
import json
import settings.context as ct
import GameServer.broadcaster as bc
# import time

# 遊戲待機
async def handle_replay_offer(now):
    if ct.replay_offer_start_time is None:
        print("[GameServer] replay_offer_start_time 尚未設置，略過 replay_offer")
        return

    elapsed_replay_offer = now - ct.replay_offer_start_time
    replay_offer_remaining_time = max(0, ct.loading_time - int(elapsed_replay_offer))

    replay_offer_msg = {
        "event": "replay_offer_update",
        "remaining_time": replay_offer_remaining_time,
        "joined_players": len(ct.replay_players),
        "joined_usernames": list(ct.replay_players),
        "total_players": len(ct.connected_players),
    }

    # 廣播 replay offer 給所有玩家
    await bc.broadcast(replay_offer_msg)

    if replay_offer_remaining_time == 0:
        print("[GameServer] Replay Offer 倒數結束，開始新局")

        await bc.broadcast({
            "event": "replay_end"
        })

        ct.replay_offer_active = False
        ct.game_phase = "playing"       # 直接開始遊戲，不用再loading
        ct.game_start_time = now                # 補上這行（關鍵）
        ct.loading_start_time = None            # 確保不進入 loading
        ct.current_scores = {username: 0 for username in ct.replay_players}
        ct.observer_players = ct.connected_players - ct.replay_players
        ct.phase_changed_event.set()            # 通知 mole_sender 啟動
