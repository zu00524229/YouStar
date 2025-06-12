# game_server.py → 純 WebSocket 版 + 最佳化版
import asyncio
import websockets
import json
import time
import random
import math

# 配置
CONTROL_SERVER_WS = "ws://127.0.0.1:8765"
MY_GAME_SERVER_WS = "ws://127.0.0.1:8001/ws"

# GameServer 狀態
phase_changed_event = asyncio.Event()
connected_players = set()
leaderboard = {}

loading_time = 10
loading_start_time = None

GAME_DURATION = 60
game_start_time = None
gameover_start_time = None

current_mole_id = 0
current_mole = {
    "mole_id": 0,
    "position": -1,
    "mole_type": "",
    "active": False
}

game_phase = "waiting"
player_websockets = {}
skip_next_status_update = False
post_gameover_cooldown = False

# ---------------------------------------------------
async def register_to_control():
    while True:
        try:
            async with websockets.connect(CONTROL_SERVER_WS) as ws:
                print("[GameServer] 已連線中控")
                await ws.send(json.dumps({
                    "type": "register_gameserver",
                    "server_url": MY_GAME_SERVER_WS
                }))

                # # 改成 background task
                asyncio.create_task(run_status_loop(ws))

                # 保持連線，不直接退出
                while True:
                    await asyncio.sleep(1)

        except Exception as e:
            print(f"[GameServer] 中控連線失敗或斷線，3 秒後重試: {e}")
            await asyncio.sleep(3)


async def run_status_loop(ws):
    global loading_start_time, game_start_time, game_phase, skip_next_status_update
    global gameover_start_time, post_gameover_cooldown

    loop_id = random.randint(1000, 9999)    # 每次 loop 有個 id
    print(f"[GameServer] run_status_loop 啟動！loop_id = {loop_id}")

    no_player_since = None   # 加一個變數 → 紀錄 "什麼時候開始沒玩家"

    try:
        while True:
            now = time.time()

            # --- playing 中，偵測是否要回 waiting ---
            if game_phase == "playing":
                if len(connected_players) == 0:
                    if no_player_since is None:
                        no_player_since = now
                        print("[GameServer] playing 中玩家全離線 → 開始計時回 waiting")
                    elif now - no_player_since >= 2:
                        print("[GameServer] playing 中玩家離線已超過 2 秒 → 回 waiting")
                        game_phase = "waiting"
                        loading_start_time = None
                        game_start_time = None
                        gameover_start_time = None
                        leaderboard.clear()
                        skip_next_status_update = False
                        post_gameover_cooldown = True
                        no_player_since = None
                        continue  # 這次先不發 status_update，下一輪再發 waiting
                else:
                    # 有玩家 → reset no_player_since
                    if no_player_since is not None:
                        print("[GameServer] 玩家重新連線 → 取消回 waiting 計時")
                    no_player_since = None

            # --- Auto start loading ---
            if len(connected_players) > 0 and game_phase == "waiting" and not post_gameover_cooldown:
                game_phase = "loading"
                loading_start_time = now
                print("[GameServer] 玩家已進入，開始 loading 倒數 10 秒")

            # --- loading phase ---
            if game_phase == "loading" and loading_start_time is not None:
                elapsed_loading = now - loading_start_time
                loading_time_left = max(0, math.ceil(10 - elapsed_loading))

                if loading_time_left == 0 and game_phase == "loading":
                    game_phase = "playing"
                    game_start_time = now
                    print("[GameServer] loading 完成 → 進入 playing 60 秒")
                    phase_changed_event.set()
                    print("[GameServer] phase_changed_event.set() 完成")
                    await asyncio.sleep(0)

            # --- playing phase ---
            if game_phase == "playing":
                elapsed_game = now - game_start_time
                remaining_game_time = max(0, 60 - int(elapsed_game))

                if remaining_game_time == 0 and game_phase == "playing":
                    print("[GameServer] 遊戲結束，進入 gameover")
                    game_phase = "gameover"
                    gameover_start_time = now

                    leaderboard_msg = {
                        "event": "leaderboard_update",
                        "leaderboard": [
                            {"username": u, "score": s}
                            for u, s in sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
                        ]
                    }

                    for player, ws_conn in player_websockets.items():
                        try:
                            await ws_conn.send(json.dumps(leaderboard_msg))
                        except:
                            pass

                    print("[GameServer] leaderboard_update 已發送")

            # --- gameover phase ---
            if game_phase == "gameover":
                elapsed_gameover = now - gameover_start_time
                if elapsed_gameover >= 2:
                    print("[GameServer] gameover 完成 → 準備回到 waiting")
                    game_phase = "post_gameover"
                    skip_next_status_update = True

            if skip_next_status_update:
                skip_next_status_update = False
                await asyncio.sleep(0.5)
                if game_phase == "post_gameover":
                    print("[GameServer] 正式切換到 waiting")
                    game_phase = "waiting"
                    loading_start_time = None
                    game_start_time = None
                    gameover_start_time = None
                    leaderboard.clear()
                    post_gameover_cooldown = True
                continue

            # --- 發送 status_update ---
            remaining_game_time = max(0, 60 - int(now - game_start_time)) if game_phase == "playing" else 0
            loading_time_left = max(0, math.ceil(10 - (now - loading_start_time))) if game_phase == "loading" else 0

            status_update = {
                "type": "status_update",
                "current_players": len(connected_players),
                "in_game": len(connected_players) > 0,
                "remaining_time": remaining_game_time,
                "leaderboard": [
                    {"username": u, "score": s}
                    for u, s in sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
                ],
                "game_phase": game_phase,
                "loading_time": loading_time_left
            }

            print(f"[GameServer] 發送給 ControlServer 的 game_phase = {game_phase}")
            await ws.send(json.dumps(status_update))

            for player, ws_conn in player_websockets.items():
                try:
                    await ws_conn.send(json.dumps(status_update))
                except:
                    pass

            await ws.send(json.dumps({"type": "ping"}))
            await asyncio.sleep(0.5)

    except Exception as e:
        print(f"[GameServer] run_status_loop 發生異常: {e}")

# ---------------------------------------------------
async def mole_sender():
    global current_mole_id, current_mole, game_phase
    while True:
        # 等待 phase 變成 playing
        print("[GameServer] mole_sender 等待 phase_changed_event (playing)")
        await phase_changed_event.wait()
        print("[GameServer] mole_sender 收到 phase_changed_event → 檢查 game_phase =", game_phase)

        # if game_phase != "playing":
        #     continue  # 避免被其他 phase 觸發
        if game_phase == "playing":
            phase_changed_event.clear()
            print("[GameServer] mole_sender 進入 playing loop!")

            while game_phase == "playing":
                current_mole_id += 1
                current_mole = {
                    "mole_id": current_mole_id,
                    "position": random.randint(0, 8),
                    "mole_type": random.choice(["普通地鼠", "黃金地鼠", "炸彈地鼠", "賭博地鼠"]),
                    "active": True
                }

                mole_msg = {
                    "event": "mole_update",
                    "mole": current_mole
                }

                for player, ws_conn in player_websockets.items():
                    try:
                        await ws_conn.send(json.dumps(mole_msg))
                    except:
                        pass

                print(f"[GameServer] 廣播新地鼠: {mole_msg}")

                sleep_time = random.uniform(1.0, 2.0)
                start_sleep = time.time()
                while time.time() - start_sleep < sleep_time:
                    if game_phase != "playing":
                        print("[GameServer] mole_sender 偵測到離開 playing, break inner loop")
                        break
                    await asyncio.sleep(0.05)

# ---------------------------------------------------
async def player_handler(websocket):
    global current_mole_id, current_mole
    username = await websocket.recv()
    print(f"[GameServer] 玩家 {username} 連線進來")
    connected_players.add(username)
    player_websockets[username] = websocket

    global post_gameover_cooldown
    post_gameover_cooldown = False

    try:
        async for msg in websocket:
            print(f"[GameServer] 收到玩家 {username} 訊息: {msg}")

            if msg.startswith("hit:"):
                parts = msg.split(":")
                mole_id = int(parts[1])
                player_score = int(parts[2])

                if current_mole["mole_id"] == mole_id and current_mole["active"]:
                    print(f"[GameServer] 玩家 {username} 打中地鼠 {mole_id}，分數 {player_score}")
                    current_mole["active"] = False

                    current_best = leaderboard.get(username, 0)
                    if player_score > current_best:
                        leaderboard[username] = player_score
                        print(f"[GameServer] 更新 {username} 的最高分為 {player_score}")

                    mole_msg = {
                        "event": "mole_update",
                        "mole": current_mole
                    }

                    for player, ws_conn in player_websockets.items():
                        try:
                            await ws_conn.send(json.dumps(mole_msg))
                        except:
                            pass
                else:
                    print(f"[GameServer] 玩家 {username} 嘗試打已消失地鼠 {mole_id}，忽略")

            elif msg.startswith("final:"):
                parts = msg.split(":")
                final_user = parts[1]
                final_score = int(parts[2])
                print(f"[GameServer] 玩家 {final_user} 結束遊戲，最終分數 {final_score}")

                current_best = leaderboard.get(final_user, 0)
                if final_score > current_best:
                    leaderboard[final_user] = final_score
                    print(f"[GameServer] 更新 {final_user} 的最高分為 {final_score}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[GameServer] 玩家 {username} 離線")
        connected_players.discard(username)
        player_websockets.pop(username, None)

# ---------------------------------------------------
async def main():
    asyncio.create_task(register_to_control())
    asyncio.create_task(mole_sender())

    server = await websockets.serve(player_handler, "0.0.0.0", 8001)
    print("[GameServer] 等待玩家連線 (port 8001) ...")
    await server.wait_closed()

# 啟動
asyncio.run(main())
