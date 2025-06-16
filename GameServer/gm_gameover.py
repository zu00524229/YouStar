# GameServer : 管理 gameover 與 post_gameover 階段邏輯

import time
import asyncio
import settings.context as ct

# 遊戲結束後等待一段時間
async def handle_gameover_phase():
    now = time.time()
    elapsed_gameover = now - ct.gameover_start_time

    if elapsed_gameover >= 2:
        print("[GameServer] gameover 完成 → 準備回到 waiting")
        ct.game_phase = "post_gameover"
        ct.skip_next_status_update = True

# post_gameover 階段 → 重設變數，正式回到 waiting
async def handle_post_gameover_transition():
    ct.skip_next_status_update = False
    await asyncio.sleep(0.5)  # 小等待，避免狀態同步亂跳

    if ct.game_phase == "post_gameover":
        print("[GameServer] 正式切換到 waiting")
        ct.game_phase = "waiting"
        ct.loading_start_time = None
        ct.game_start_time = None
        ct.gameover_start_time = None
        ct.post_gameover_cooldown = True
