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
        print("[GameServer] gameover 完成 → 準備回到 post_gameover")
        # 新增：廣播 gameover 給前端

        ct.game_phase = "post_gameover"
        ct.phase_changed_event.set()

        await bc.broadcast_status_update()
        await bc.broadcast_final_leaderboard()


# 遊戲結束後 → post_gameover 階段：由玩家操作觸發
async def handle_post_gameover_transition():
    # print("[GameServer] post_gameover：等待玩家操作（不再自動切換）")
    # await asyncio.sleep(10)
    # 不做任何事，等玩家指令
    return

async def reset_game_to_waiting():
    print("[GameServer] reset_game_to_waiting：重設遊戲資料並回到 waiting")
    ct.current_scores.clear()
    ct.current_mole = {}
    ct.current_special_mole = {}
    ct.skip_next_status_update = False
    ct.game_phase = "waiting"
    ct.loading_start_time = None
    ct.game_start_time = None
    ct.gameover_start_time = None
    ct.phase_changed_event.clear()
    ct.ready_players.clear()            # 清除 ready 事件
    # ct.save_leaderboard()
    print("[GameServer] 已成功切回 waiting，準備接收新玩家")
    await bc.broadcast_status_update()
