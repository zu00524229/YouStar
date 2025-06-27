# gm_waiting.py    :   GameServer : 管理 waiting 階段邏輯
import json
import settings.context as ct
import GameServer.broadcaster as bc
# import time

# 檢查是否可從 waiting 轉入 loading 階段
async def check_start_waiting(now):
    if len(ct.ready_players) > 0 and ct.game_phase == "waiting" and not ct.post_gameover_cooldown:
        # 當有玩家 ready，即進入 loading 階段
        ct.game_phase = "loading"
        ct.loading_start_time = now
        ct.last_loading_broadcast = 0  # reset timer

        print(f"[GameServer] {len(ct.ready_players)} 名玩家按下 Ready，開始 loading 倒數 10 秒")
        await bc.broadcast_status_update()    # 呼叫 loading 狀態
        ct.phase_changed_event.set()  # 觸發階段更動

