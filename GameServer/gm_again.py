# gm_again.py
import time
import settings.context as ct
import GameServer.broadcaster as bc
import asyncio


async def start_again_countdown():
    for sec in range(10, 0, -1):
        await bc.broadcast({
            "event": "again_timer",
            "remaining_time": sec
        })
        await asyncio.sleep(1)

    print("[Replay] 倒數結束，進入 Playing 階段")
    await start_next_round()



async def start_next_round():
    ct.current_scores.clear()           # 清理分數
    ct.current_mole = {}
    ct.again_active = False
    ct.again_start_time = None          # 預設again倒數為空
    ct.game_phase = "playing"           # 回到 playing
    ct.game_start_time = time.time()
    ct.phase_changed_event.set()        # 重設地數方法
    await bc.broadcast_status_update()
    # ct.save_leaderboard()
    # ct.leaderboard_result = []
    # ct.leaderboard.clear()              # 清理排行榜
    # ct.current_special_mole = {}
