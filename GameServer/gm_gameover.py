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
