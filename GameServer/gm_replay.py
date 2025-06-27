# gm_replay.py
import time
import settings.context as ct
import GameServer.broadcaster as bc
import asyncio

async def start_replay_offer(username):
    if ct.game_phase != "gameover":
        print(f"[GameServer] 無法在 {ct.game_phase} 階段啟動 Again 流程")
        return

    if ct.replay_offer_active:
        print(f"[GameServer] 已啟動 Again 倒數，忽略 {username} 的重複請求")
        return

    print(f"[GameServer] 玩家 {username} 發起 Again ➜ 進入 replay_offer 階段")
    ct.replay_offer_active = True
    ct.replay_start_time = time.time()
    ct.game_phase = "replay_offer"

    await bc.broadcast({
        "event": "replay_offer",
        "message": "10 秒後自動開始下一局，想離開請按 Lobby。",
        "remaining_time": 10
    })

    # 倒數 10 秒（每秒更新一次）
    for remaining in range(9, -1, -1):
        await asyncio.sleep(1)
        await bc.broadcast({
            "event": "replay_again",
            "remaining_time": remaining
        })

    # 切換為 playing 階段
    print("[GameServer] Replay 倒數結束，開始新一輪遊戲")
    ct.game_phase = "playing"
    ct.replay_offer_active = False
    ct.playing_start_time = time.time()
    ct.current_scores = {}
    await bc.broadcast_status_update()
    ct.phase_changed_event.set()
