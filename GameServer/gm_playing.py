# gm_playing.py : GameServer 管理 playing 階段邏輯

import time
import json
import asyncio
import settings.context as ct
import GameServer.broadcaster as bc

# 
async def handle_playing_phase():
    now = time.time()

    # --- 1. 檢查是否所有玩家都離線 ---
    if len(ct.connected_players) == 0:
        if ct.no_player_since is None:
            ct.no_player_since = now
            print("[GameServer] playing 中玩家全離線 → 開始計時回 waiting")
        elif now - ct.no_player_since >= 2:
            print("[GameServer] 玩家離線已超過 2 秒 → 重置為 waiting")
            reset_to_waiting()
            return
    else:
        if ct.no_player_since is not None:
            print("[GameServer] 玩家重新連線 → 取消離線計時")
        ct.no_player_since = None

    # --- 2. 檢查是否遊戲結束 ---
    elapsed = now - ct.game_start_time
    remaining_time = max(0, ct.GAME_DURATION - int(elapsed))

    if remaining_time == 0:
        print("[GameServer] 遊戲結束，進入 gameover")
        ct.game_phase = "gameover"
        ct.gameover_start_time = now
        # await bc.broadcast_leaderboard()         
        await bc.broadcast_status_update()       # 廣播 gameover 狀態
        print("[GameServer] leaderboard_update 已廣播")
        return

# --- 重置為 waiting 的共用方法 ---
def reset_to_waiting():
    ct.game_phase = "waiting"               # 預設  waiting 狀態
    ct.loading_start_time = None            # 等待時間 預設空值
    ct.game_start_time = None               
    ct.gameover_start_time = None
    ct.skip_next_status_update = False
    ct.post_gameover_cooldown = True
    ct.no_player_since = None
    ct.leaderboard.clear()
    ct.ready_players.clear()
    print("[GameServer] 所有狀態重設完成 → 等待下一局")


# 每秒廣播剩餘時間（只在 playing 階段）
async def broadcast_playing_timer_loop():
    while True:
        if ct.game_phase == "playing":
            await bc.broadcast_status_update()
        await asyncio.sleep(1)


