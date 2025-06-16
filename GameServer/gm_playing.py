# GameServer 管理 playing 邏輯
# GameServer/gm_playing.py
import time
import json
import settings.context as ct

async def handle_playing_phase():
    now = time.time()
    # --- 檢查是否所有玩家都離線 ---
    if len(ct.connected_players) == 0:
        if ct.no_player_since is None:
            ct.no_player_since = now
            print("[GameServer] playing 中玩家全離線 → 開始計時回 waiting")
        elif now - ct.no_player_since >= 2:
            print("[GameServer] playing 中玩家離線已超過 2 秒 → 回 waiting")
            ct.game_phase = "waiting"
            ct.loading_start_time = None
            ct.game_start_time = None
            ct.gameover_start_time = None
            ct.leaderboard.clear()
            ct.skip_next_status_update = False
            ct.post_gameover_cooldown = True
            ct.no_player_since = None
            return
    else:
        if ct.no_player_since is not None:
            print("[GameServer] 玩家重新連線 → 取消回 waiting 計時")
        ct.no_player_since = None

    # --- 檢查是否遊戲時間已結束 ---
    elapsed_game = now - ct.game_start_time
    remaining_game_time = max(0, 60 - int(elapsed_game))

    if remaining_game_time == 0 and ct.game_phase == "playing":
        print("[GameServer] 遊戲結束，進入 gameover")
        ct.game_phase = "gameover"
        ct.gameover_start_time = now

        leaderboard_msg = {
            "event": "leaderboard_update",
            "leaderboard": [
                {"username": u, "score": s}
                for u, s in sorted(ct.leaderboard.items(), key=lambda x: x[1], reverse=True)
            ]
        }

        for player, ws_conn in ct.player_websockets.items():
            try:
                await ws_conn.send(json.dumps(leaderboard_msg))
            except:
                pass

        print("[GameServer] leaderboard_update 已發送")
