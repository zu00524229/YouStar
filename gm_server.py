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
current_scores = {}                      # 玩家當前當局分數

# 遊戲計時
loading_time = 10                        # loading 倒數秒數
loading_start_time = None                

GAME_DURATION = 60                       # 遊戲時間 60s
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

# 特殊地鼠邏輯
current_special_mole_id = 0
current_special_mole = {
    "mole_id": 0,
    "position": -1,
    "mole_type": "",
    "active": False
}


# 遊戲階段控制
game_phase = "waiting"                   # 遊戲狀態機: waiting / loading / playing / gameover / post_gameover
player_websockets = {}                   # {username: websocket} → 廣播/單發使用
skip_next_status_update = False          # 避免 post_gameover 時多發一次 status_update (waiting)
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
# 遊戲主控循環:控制 game_phase 狀態機 + 發 status_update (核心)
async def run_status_loop(ws):
    global loading_start_time, game_start_time, game_phase, skip_next_status_update
    global gameover_start_time, post_gameover_cooldown, current_scores

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
                    # 新局重設 current_scores 分數 (當前分數)
                    current_scores = {username: 0 for username in connected_players}
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
                    # leaderboard.clear()       # 跨局保留歷史高分
                    post_gameover_cooldown = True
                continue

            # --- 發送 status_update + ping ---
            remaining_game_time = max(0, 60 - int(now - game_start_time)) if game_phase == "playing" else 0
            loading_time_left = max(0, math.ceil(10 - (now - loading_start_time))) if game_phase == "loading" else 0


            leaderboard_list = []

            for username in connected_players:
                score = current_scores.get(username, 0)   # 沒有分數時給 0
                leaderboard_list.append({
                    "username": username,
                    "score": score
                })

            status_update = {
                "type": "status_update",
                "current_players": len(connected_players),
                "in_game": len(connected_players) > 0,
                "remaining_time": remaining_game_time,
                "leaderboard": sorted(leaderboard_list, key=lambda x: x["score"], reverse=True),
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
                    "mole_type": random.choice(["Mole", "Gold Mole", "Bomb Mole", "Joker Mole"]),                    
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

                # sleep 1 ~ 1.5 秒，檢查是否仍為 playing
                sleep_time = random.uniform(0.6, 1.5)
                start_sleep = time.time()
                while time.time() - start_sleep < sleep_time:
                    if game_phase != "playing":
                        print("[GameServer] mole_sender 偵測到離開 playing, break inner loop")
                        break
                    await asyncio.sleep(0.05)

async def special_mole_sender():
    global current_special_mole_id, current_special_mole, game_phase

    while True:
        await phase_changed_event.wait()
        print("[GameServer] special_mole_sender 收到 phase_changed_event → 檢查 game_phase =", game_phase)

        if game_phase == "playing":
            # phase_changed_event.clear()
            print("[GameServer] special_mole_sender 進入 playing loop!")

            while game_phase == "playing":
                # 每 5 ~ 10 秒出現一隻特殊地鼠
                sleep_time = random.uniform(5.0, 10.0)
                await asyncio.sleep(sleep_time)

                if game_phase != "playing":
                    break

                # 生成特殊地鼠
                current_special_mole_id += 1

                # 避免與普通地鼠 position 重複
                all_positions = set(range(12))  # 你 4x3 格子共 12 格
                occupied_position = {current_mole["position"]}
                available_positions = list(all_positions - occupied_position)

                if not available_positions:
                    print("[GameServer] 沒有可用位置放特殊地鼠，跳過這輪")
                    continue

                current_special_mole = {
                    "mole_id": current_special_mole_id,
                    "position": random.choice(available_positions),
                    "mole_type": "Diamond Mole",  # 鑽石地鼠
                    "active": True
                }

                mole_msg = {
                    "event": "special_mole_update",
                    "mole": current_special_mole
                }

                # 廣播特殊地鼠
                for player, ws_conn in player_websockets.items():
                    try:
                        await ws_conn.send(json.dumps(mole_msg))
                    except:
                        pass

                print(f"[GameServer] 發送 Special Mole ID {current_special_mole_id} at pos {current_special_mole['position']}")


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

            try:
                # 一般地鼠
                if msg.startswith("hit:"):
                    parts = msg.split(":")
                    if len(parts) != 3:
                        raise ValueError(f"hit 訊息格式錯誤: {msg}")

                    mole_id = int(parts[1])
                    player_score = int(parts[2])

                    if current_mole["mole_id"] == mole_id and current_mole["active"]:
                        print(f"[GameServer] 玩家 {username} 打中地鼠 {mole_id}，分數 {player_score}")
                        current_mole["active"] = False

                        current_scores[username] = player_score  # 更新目前分數 (current_scores)

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

                # 特殊地鼠
                elif msg.startswith("special_hit:"):
                    parts = msg.split(":")
                    if len(parts) != 3:
                        raise ValueError(f"special_hit 訊息格式錯誤: {msg}")

                    mole_id = int(parts[1])
                    player_score = int(parts[2])

                    if current_special_mole["mole_id"] == mole_id and current_special_mole["active"]:
                        print(f"[GameServer] 玩家 {username} 打中 Special Mole {mole_id}，分數 {player_score}")
                        current_special_mole["active"] = False

                        current_scores[username] = player_score

                        current_best = leaderboard.get(username, 0)
                        if player_score > current_best:
                            leaderboard[username] = player_score
                            print(f"[GameServer] 更新 {username} 的最高分為 {player_score}")

                        mole_msg = {
                            "event": "special_mole_update",
                            "mole": current_special_mole
                        }

                        for player, ws_conn in player_websockets.items():
                            try:
                                await ws_conn.send(json.dumps(mole_msg))
                            except:
                                pass

                    else:
                        print(f"[GameServer] 玩家 {username} 嘗試打已消失地鼠 {mole_id}，忽略")

                # 最終分數
                elif msg.startswith("final:"):
                    parts = msg.split(":")
                    if len(parts) != 3:
                        raise ValueError(f"final 訊息格式錯誤: {msg}")

                    final_user = parts[1]
                    final_score = int(parts[2])
                    print(f"[GameServer] 玩家 {final_user} 結束遊戲，最終分數 {final_score}")

                    current_best = leaderboard.get(final_user, 0)
                    if final_score > current_best:
                        leaderboard[final_user] = final_score
                        print(f"[GameServer] 更新 {final_user} 的最高分為 {final_score}")

                else:
                    print(f"[GameServer] 收到未知訊息: {msg}")

            except Exception as e:
                print(f"[GameServer] 玩家 {username} 處理訊息出錯: {e}，msg={msg}")

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
    asyncio.create_task(special_mole_sender())

    server = await websockets.serve(player_handler, "0.0.0.0", 8001)
    print("[GameServer] 等待玩家連線 (port 8001) ...")
    await server.wait_closed()

# run
asyncio.run(main())
