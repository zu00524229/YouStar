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
phase_changed_event = asyncio.Event()    # 等待進入 playing → mole_sender 才啟動
connected_players = set()                # 目前在線玩家 username 集合
leaderboard = {}                         # 玩家最高分字典 {username: score}

# 遊戲計時
loading_time = 10
loading_start_time = None

GAME_DURATION = 60
game_start_time = None
gameover_start_time = None

# 當前地鼠資訊
current_mole_id = 0
current_mole = {
    "mole_id": 0,
    "position": -1,
    "mole_type": "",
    "active": False
}

# 遊戲階段控制
game_phase = "waiting"                   # waiting / loading / playing / gameover / post_gameover
player_websockets = {}                   # {username: websocket} → 廣播/單發使用
skip_next_status_update = False          # 避免 post_gameover 時多發一次 status_update
post_gameover_cooldown = False           # 是否剛結束過一場 → 防止立即進 loading

# ---------------------------------------------------
# 向 ControlServer 註冊自己 & 持續報 status / ping
async def register_to_control():
    while True:
        try:
            async with websockets.connect(CONTROL_SERVER_WS) as ws:
                print("[GameServer] 已連線中控")
                await ws.send(json.dumps({
                    "type": "register_gameserver",
                    "server_url": MY_GAME_SERVER_WS
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
# 遊戲主控循環 → 控制 game_phase 狀態機 + 發 status_update
async def run_status_loop(ws):
    global loading_start_time, game_start_time, game_phase, skip_next_status_update
    global gameover_start_time, post_gameover_cooldown

    loop_id = random.randint(1000, 9999)
    print(f"[GameServer] run_status_loop 啟動！loop_id = {loop_id}")

    no_player_since = None   # 記錄 playing 中，何時開始沒玩家 → 自動回 waiting

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
                        # 若玩家離線超過 2 秒 → 強制回 waiting，重置遊戲狀態
                        print("[GameServer] playing 中玩家離線已超過 2 秒 → 回 waiting")
                        game_phase = "waiting"
                        loading_start_time = None
                        game_start_time = None
                        gameover_start_time = None
                        leaderboard.clear()
                        skip_next_status_update = False
                        post_gameover_cooldown = True
                        no_player_since = None
                        continue
                else:
                    # 有玩家 → 取消回 waiting 計時
                    if no_player_since is not None:
                        print("[GameServer] 玩家重新連線 → 取消回 waiting 計時")
                    no_player_since = None

            # --- Auto start loading ---
            if len(connected_players) > 0 and game_phase == "waiting" and not post_gameover_cooldown:
                # 有玩家進入 → 自動切入 loading 倒數
                game_phase = "loading"
                loading_start_time = now
                print("[GameServer] 玩家已進入，開始 loading 倒數 10 秒")

            # --- loading phase ---
            if game_phase == "loading" and loading_start_time is not None:
                elapsed_loading = now - loading_start_time
                loading_time_left = max(0, math.ceil(10 - elapsed_loading))

                if loading_time_left == 0 and game_phase == "loading":
                    # loading 結束 → 進入 playing → 觸發 mole_sender
                    game_phase = "playing"
                    game_start_time = now
                    print("[GameServer] loading 完成 → 進入 playing 60 秒")
                    phase_changed_event.set()   # 通知 mole_sender 開始發地鼠
                    print("[GameServer] phase_changed_event.set() 完成")
                    await asyncio.sleep(0)

            # --- playing phase ---
            if game_phase == "playing":
                elapsed_game = now - game_start_time
                remaining_game_time = max(0, 60 - int(elapsed_game))

                if remaining_game_time == 0 and game_phase == "playing":
                    # 遊戲結束 → 進入 gameover，廣播 leaderboard_update
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
                    # 等 2 秒 → 切 post_gameover
                    print("[GameServer] gameover 完成 → 準備回到 waiting")
                    game_phase = "post_gameover"
                    skip_next_status_update = True

            # --- post_gameover 處理 ---
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

            # --- 發送 status_update + ping ---
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

            await ws.send(json.dumps(status_update))

            # 同時也 broadcast status_update 給所有玩家
            for player, ws_conn in player_websockets.items():
                try:
                    await ws_conn.send(json.dumps(status_update))
                except:
                    pass

            # heartbeat
            await ws.send(json.dumps({"type": "ping"}))
            await asyncio.sleep(1)

    except Exception as e:
        print(f"[GameServer] run_status_loop 發生異常: {e}")

# ---------------------------------------------------
# 發送地鼠 mole_update → 只在 playing 中觸發
async def mole_sender():

    global current_mole_id, current_mole, game_phase
    while True:
        print("[GameServer] mole_sender 等待 phase_changed_event (playing)")
        await phase_changed_event.wait()
        print("[GameServer] mole_sender 收到 phase_changed_event → 檢查 game_phase =", game_phase)

        if game_phase == "playing":
            phase_changed_event.clear()
            print("[GameServer] mole_sender 進入 playing loop!")

            while game_phase == "playing":
                # 生成新地鼠
                current_mole_id += 1
                current_mole = {
                    "mole_id": current_mole_id,
                    "position": random.randint(0, 11),
                    "mole_type": random.choice(["普通地鼠", "黃金地鼠", "炸彈地鼠", "賭博地鼠"]),
                    "active": True
                }

                mole_msg = {
                    "event": "mole_update",
                    "mole": current_mole
                }

                # 廣播給所有玩家
                for player, ws_conn in player_websockets.items():
                    try:
                        await ws_conn.send(json.dumps(mole_msg))
                    except:
                        pass

                # sleep 1~2 秒，檢查是否仍為 playing
                sleep_time = random.uniform(1.0, 2.0)
                start_sleep = time.time()
                while time.time() - start_sleep < sleep_time:
                    if game_phase != "playing":
                        print("[GameServer] mole_sender 偵測到離開 playing, break inner loop")
                        break
                    await asyncio.sleep(0.05)

# ---------------------------------------------------
# 處理單個玩家 WebSocket
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

        # 通知 ControlServer Offline
        try:
            async def notify_control_offline():
                async with websockets.connect(CONTROL_SERVER_WS) as ws_control:
                    await ws_control.send(json.dumps({
                        "type": "offline",
                        "username": username
                    }))
                    print(f"[GameServer] 已通知 ControlServer 玩家 {username} offline")
            asyncio.create_task(notify_control_offline())
        except Exception as e:
            print(f"[GameServer] 通知 ControlServer 玩家 {username} offline 失敗: {e}")

# ---------------------------------------------------
# 啟動主流程
async def main():
    asyncio.create_task(register_to_control())
    asyncio.create_task(mole_sender())

    server = await websockets.serve(player_handler, "0.0.0.0", 8001)
    print("[GameServer] 等待玩家連線 (port 8001) ...")
    await server.wait_closed()

# run
asyncio.run(main())
