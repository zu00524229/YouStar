import asyncio
import websockets
import json
import time
import random
import math
import settings.context as context
from GameServer.gm_mole import mole_sender, special_mole_sender, player_handler

# mole_sender、special_mole_sender、player_handler 已模組化到 gm_mole.py

# ---------------------------------------------------
# 向 ControlServer 註冊自己 & 持續報 status / ping
async def register_to_control():
    while True:
        try:
            async with websockets.connect(context.CONTROL_SERVER_WS) as ws:
                print("[GameServer] 已連線中控")
                await ws.send(json.dumps({
                    "type": "register_gameserver",
                    "server_url": context.MY_GAME_SERVER_WS
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

    no_player_since = None   # 記錄 playing 中，何時開始沒玩家 → 自動回 waiting

    try:
        while True:
            now = time.time()

            # --- playing 中，偵測是否要回 waiting --- 防止連線瞬間斷開又連上時的錯誤
            if context.game_phase == "playing":
                if len(context.connected_players) == 0:
                    if no_player_since is None:
                        no_player_since = now
                        print("[GameServer] playing 中玩家全離線 → 開始計時回 waiting")
                    elif now - no_player_since >= 2:
                        print("[GameServer] playing 中玩家離線已超過 2 秒 → 回 waiting")
                        context.game_phase = "waiting"
                        context.loading_start_time = None
                        context.game_start_time = None
                        context.gameover_start_time = None
                        context.leaderboard.clear()
                        context.skip_next_status_update = False
                        context.post_gameover_cooldown = True
                        no_player_since = None
                        continue
                else:
                    if no_player_since is not None:
                        print("[GameServer] 玩家重新連線 → 取消回 waiting 計時")
                    no_player_since = None

            if len(context.connected_players) > 0 and context.game_phase == "waiting" and not context.post_gameover_cooldown:
                context.game_phase = "loading"
                context.loading_start_time = now
                print("[GameServer] 玩家已進入，開始 loading 倒數 10 秒")

            if context.game_phase == "loading" and context.loading_start_time is not None:
                elapsed_loading = now - context.loading_start_time
                loading_time_left = max(0, math.ceil(10 - elapsed_loading))

                if loading_time_left == 0 and context.game_phase == "loading":
                    context.game_phase = "playing"
                    context.game_start_time = now
                    context.current_scores = {username: 0 for username in context.replay_players or context.connected_players}
                    print("[GameServer] loading 完成 → 進入 playing 60 秒")
                    context.phase_changed_event.set()
                    print("[GameServer] phase_changed_event.set() 完成")

            if context.game_phase == "playing":
                elapsed_game = now - context.game_start_time
                remaining_game_time = max(0, 60 - int(elapsed_game))

                if remaining_game_time == 0 and context.game_phase == "playing":
                    print("[GameServer] 遊戲結束，進入 gameover")
                    context.game_phase = "gameover"
                    context.gameover_start_time = now

                    leaderboard_msg = {
                        "event": "leaderboard_update",
                        "leaderboard": [
                            {"username": u, "score": s}
                            for u, s in sorted(context.leaderboard.items(), key=lambda x: x[1], reverse=True)
                        ]
                    }

                    for player, ws_conn in context.player_websockets.items():
                        try:
                            await ws_conn.send(json.dumps(leaderboard_msg))
                        except:
                            pass

                    print("[GameServer] leaderboard_update 已發送")

            if context.game_phase == "gameover":
                elapsed_gameover = now - context.gameover_start_time
                if elapsed_gameover >= 2:
                    print("[GameServer] gameover 完成 → 準備回到 waiting")
                    context.game_phase = "post_gameover"
                    context.skip_next_status_update = True

            if context.skip_next_status_update:
                context.skip_next_status_update = False
                await asyncio.sleep(0.5)
                if context.game_phase == "post_gameover":
                    print("[GameServer] 正式切換到 waiting")
                    context.game_phase = "waiting"
                    context.loading_start_time = None
                    context.game_start_time = None
                    context.gameover_start_time = None
                    context.post_gameover_cooldown = True
                continue

            if context.game_phase == "waiting" and context.replay_offer_active:
                elapsed_replay_offer = now - context.replay_offer_start_time
                replay_offer_remaining_time = max(0, context.replay_offer_duration - int(elapsed_replay_offer))

                replay_offer_msg = {
                    "event": "replay_offer_update",
                    "remaining_time": replay_offer_remaining_time,
                    "joined_players": len(context.replay_players),
                    "total_players": len(context.connected_players)
                }
                for player, ws_conn in context.player_websockets.items():
                    try:
                        await ws_conn.send(json.dumps(replay_offer_msg))
                    except:
                        pass

                if replay_offer_remaining_time == 0:
                    print("[GameServer] Replay Offer 倒數結束，開始新局")
                    context.replay_offer_active = False
                    context.game_phase = "loading"
                    context.loading_start_time = now
                    context.current_scores = {username: 0 for username in context.replay_players}
                    context.observer_players = context.connected_players - context.replay_players

            remaining_game_time = max(0, 60 - int(now - context.game_start_time)) if context.game_phase == "playing" else 0
            loading_time_left = max(0, math.ceil(10 - (now - context.loading_start_time))) if context.game_phase == "loading" else 0

            leaderboard_list = []
            for username in context.connected_players:
                score = context.current_scores.get(username, 0)
                leaderboard_list.append({
                    "username": username,
                    "score": score
                })

            status_update = {
                "type": "status_update",
                "current_players": len(context.connected_players),
                "in_game": len(context.connected_players) > 0,
                "remaining_time": remaining_game_time,
                "leaderboard": sorted(leaderboard_list, key=lambda x: x["score"], reverse=True),
                "game_phase": context.game_phase,
                "loading_time": loading_time_left
            }

            await ws.send(json.dumps(status_update))

            for player, ws_conn in context.player_websockets.items():
                try:
                    await ws_conn.send(json.dumps(status_update))
                except:
                    pass

            await ws.send(json.dumps({"type": "ping"}))
            await asyncio.sleep(1)

    except Exception as e:
        print(f"[GameServer] run_status_loop 發生異常: {e}")

# ---------------------------------------------------
# 啟動主流程
async def main():
    asyncio.create_task(register_to_control())
    asyncio.create_task(mole_sender())
    asyncio.create_task(special_mole_sender())

    server = await websockets.serve(player_handler, "0.0.0.0", 8001)
    print("[GameServer] 等待玩家連線 (port 8001) ...")
    await server.wait_closed()

# run
asyncio.run(main())
