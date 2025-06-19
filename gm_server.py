# gm_server.py      :   Gameserver 主程式 
import asyncio
import websockets
import json
import time
import random
import math
import settings.context as ct
from GameServer.player_handler import player_handler
from GameServer.gm_mole import mole_sender, special_mole_sender
import GameServer.gm_playing as play
import GameServer.gm_loading as load
import GameServer.gm_gameover as over
import GameServer.gm_waiting as wait

# ---------------------------------------------------
# 向 ControlServer 註冊自己 & 持續報 status / ping
async def register_to_control():
    while True:
        try:
            async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
                print("[GameServer] 已連線中控")
                await ws.send(json.dumps({
                    "type": "register_gameserver",
                    "server_url": ct.MY_GAME_SERVER_WS
                }))

                # 改為 background task → run_status_loop → 狀態更新 & heartbeat
                asyncio.create_task(run_status_loop(ws))

                # 保持 websocket 連線
                while True:
                    await asyncio.sleep(1)

        except Exception as e:
            print(f"[GameServer] 中控連線失敗或斷線，3 秒後重試: {e}")
            await asyncio.sleep(3)

# ---------------------------------------------------
# (核心)遊戲主控循環:控制 game_phase 狀態機 + 發 status_update 
async def run_status_loop(ws):

    loop_id = random.randint(1000, 9999)
    print(f"[GameServer] run_status_loop 啟動！loop_id = {loop_id}")

    try:
        while True:
            now = time.time()

            # --- playing -- 管理玩家離線與結束倒數
            if ct.game_phase == "playing":
                await play.handle_playing_phase()
                
            # --- waiting -- 玩家進入遊戲、觸發進入 loading 階段
            if ct.game_phase == "waiting" and not ct.post_gameover_cooldown:
                wait.check_start_waiting(now)

            # --- loading -- 倒數完轉為 playing
            if ct.game_phase == "loading":
                await load.handle_loading_phase()

            # --- gameover -- 倒數完轉換(等待玩家是否下局或觀戰)
            if ct.game_phase == "gameover":
                await over.handle_gameover_phase()

            # --- post_gameover -- 清除階段狀態並進入 waiting
            if ct.skip_next_status_update:
                await over.handle_post_gameover_transition()
                continue
        
            # --- waiting -- 遊戲待機階段
            if ct.game_phase == "waiting" and ct.ready_offer_active:
                if ct.ready_offer_start_time is not None:
                    await wait.handle_ready_offer(now)
                else:
                    print("[GameServer] ready_offer_start_time 是 None，略過 handle_ready_offer")
            
            if ct.game_phase == "playing" and ct.game_start_time is not None:
                remaining_game_time = max(0, ct.GAME_DURATION - int(now - ct.game_start_time))
            else:
                remaining_game_time = 0

            if ct.game_phase == "loading" and ct.loading_start_time is not None:
                loading_time_left = max(0, math.ceil(10 - (now - ct.loading_start_time)))
            else:
                loading_time_left = 0

            leaderboard_list = []
            for username in ct.connected_players:
                score = ct.current_scores.get(username, 0)
                leaderboard_list.append({
                    "username": username,
                    "score": score
                })

            status_update = {
                "type": "status_update",
                "current_players": len(ct.connected_players),
                "in_game": len(ct.connected_players) > 0,
                "remaining_time": remaining_game_time,
                "leaderboard": sorted(leaderboard_list, key=lambda x: x["score"], reverse=True),
                "game_phase": ct.game_phase,
                "loading_time": loading_time_left
            }

            await ws.send(json.dumps(status_update))

            for player, ws_conn in ct.player_websockets.items():
                try:
                    await ws_conn.send(json.dumps(status_update))
                except:
                    pass

            await ws.send(json.dumps({"type": "ping"}))
            await asyncio.sleep(1)

    except Exception as e:
        print(f"[GameServer] run_status_loop 發生異常: {e}")

    print(f"[STATUS UPDATE] remaining_time: {remaining_game_time}")
# ---------------------------------------------------
# 啟動主流程
async def main():
    asyncio.create_task(register_to_control())
    asyncio.create_task(mole_sender())
    asyncio.create_task(special_mole_sender())

    server = await websockets.serve(player_handler, "0.0.0.0", 8001)
    print("[GameServer] 等待玩家連線 (port 8001) ...")
    await asyncio.Future()  # run forever
    await server.wait_closed()

# run
asyncio.run(main())
