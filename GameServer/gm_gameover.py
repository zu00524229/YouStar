# gm_gameover.py    :  GameServer : 管理 gameover 與 post_gameover 階段邏輯

import time
import asyncio
import settings.context as ct
import GameServer.broadcaster as bc

# 遊戲結束後等待一段時間
async def handle_gameover_phase():
    now = time.time()
    elapsed_gameover = now - ct.gameover_start_time

    if elapsed_gameover >= 2:
        print("[GameServer] gameover 完成 → 準備回到 waiting")

        # 新增：廣播 gameover 給前端
        await bc.broadcast_status_update()

        ct.game_phase = "post_gameover"
        ct.skip_next_status_update = True
        await bc.broadcast_final_leaderboard()


# 遊戲結束後 → 清除資料 → 回到 waiting
async def handle_post_gameover_transition():
    print("[GameServer] post_gameover → 重設遊戲狀態並回到 waiting")

    # 重設分數與排行榜資料
    ct.current_scores.clear()
    ct.current_mole = {}
    ct.current_special_mole = {}
    ct.leaderboard_result = []
    ct.skip_next_status_update = False
    ct.game_phase = "waiting"
    ct.ready_offer_active = False
    ct.ready_players = set()
    ct.loading_start_time = None
    ct.game_start_time = None
    ct.gameover_start_time = None
    ct.phase_changed_event.clear()
