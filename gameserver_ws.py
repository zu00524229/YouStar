from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
import asyncio
import websockets
import json
import time
import random
import math
from contextlib import asynccontextmanager


# 給中控用的網址們
CONTROL_REGISTER_URL = "ws://127.0.0.1:8000/register_gameserver"
CONTROL_PLAYER_OFFLINE_URL = "http://127.0.0.1:8000/player_offline"

# 這一台 GameServer 提供給玩家的 WebSocket 位址
MY_GAME_SERVER_WS = "ws://127.0.0.1:8001/ws"

# 紀錄目前 GameServer 上線的玩家
connected_players = set()
leaderboard = {}

# loading 倒數設定
loading_time = 10  # 倒數 10 秒
loading_started = False
loading_start_time = None

# 正式遊戲時間設定
GAME_DURATION = 60
game_start_time = None

# 地鼠同步狀態
current_mole_id = 0
current_mole = {
    "mole_id": 0,
    "position": -1,
    "mole_type": "",
    "active": False
}

# 遊戲階段
game_phase = "waiting"
player_websockets = {} # 記住每一個玩家的 websocket

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(register_to_control())
    yield
    print("[GameServer] 關閉中...")

app = FastAPI(lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def player_ws(websocket: WebSocket):
    global current_mole_id, current_mole
    await websocket.accept()
    username = await websocket.receive_text()
    print(f"[GameServer] 玩家 {username} 連線進來")
    connected_players.add(username)
    player_websockets[username] = websocket

    async def mole_sender():
        global current_mole_id, current_mole
        while True:
            try:
                # 只有在 playing phase 才出地鼠
                if game_phase == "playing":
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

                    # 廣播新地鼠，給所有玩家
                    for player, ws_conn in player_websockets.items():
                        try:
                            await ws_conn.send_text(json.dumps(mole_msg))
                        except:
                            pass
                    print(f"[GameServer] 廣播新地鼠: {mole_msg}")

                    await asyncio.sleep(random.uniform(1.0, 2.0))
                else:
                    # 如果不是 playing，稍微 sleep，避免佔用 CPU
                    await asyncio.sleep(0.1)
            except:
                break

    mole_task = asyncio.create_task(mole_sender())

    try:
        while True:
            msg = await websocket.receive_text()
            print(f"[GameServer] 收到玩家 {username} 訊息: {msg}")

            if msg.startswith("hit:"):
                parts = msg.split(":")
                mole_id = int(parts[1])
                player_score = int(parts[2])

                # 檢查是否是目前 active 地鼠
                if current_mole["mole_id"] == mole_id and current_mole["active"]:
                    print(f"[GameServer] 玩家 {username} 打中地鼠 {mole_id}，分數 {player_score}")
                    current_mole["active"] = False

                    # 更新 leaderboard
                    current_best = leaderboard.get(username, 0)
                    if player_score > current_best:
                        leaderboard[username] = player_score
                        print(f"[GameServer] 更新 {username} 的最高分為 {player_score}")

                    # 廣播地鼠消失，給所有 connected_players(玩家)
                    mole_msg = {
                        "event": "mole_update",
                        "mole": current_mole
                    }

                    for player, ws_conn in player_websockets.items():
                        try:
                            await ws_conn.send_text(json.dumps(mole_msg))
                        except:
                            pass

                    print(f"[GameServer] 廣播地鼠消失: {mole_msg}")
                else:
                    print(f"[GameServer] 玩家 {username} 嘗試打已消失地鼠 {mole_id}，忽略")

            # 玩家遊戲結束送最終分數
            elif msg.startswith("final:"):
                parts = msg.split(":")
                final_user = parts[1]
                final_score = int(parts[2])
                print(f"[GameServer] 玩家 {final_user} 結束遊戲，最終分數 {final_score}")

                # 排行榜資料
                current_best = leaderboard.get(final_user, 0)
                if final_score > current_best:
                    leaderboard[final_user] = final_score
                    print(f"[GameServer] 更新 {final_user} 的最高分為 {final_score}")

                #  log 提醒
                print(f"[GameServer] leaderboard 更新完成，等待 background 送 ping 給中控")

            
            try:
                await websocket.send_text(f"收到: {msg}")
            except:
                pass


    except WebSocketDisconnect:
        print(f"[GameServer] 玩家 {username} 離線")
        connected_players.discard(username)
        try:
            requests.post(CONTROL_PLAYER_OFFLINE_URL, json={"username": username})
        except Exception as e:
            print(f"[GameServer] 通知中控失敗: {e}")
    finally:
        mole_task.cancel()

# 註冊自己到中控 + 定期回報狀態
async def register_to_control():
    global loading_started, loading_start_time, game_start_time, game_phase
    global ready_start_time  # ⭐ 新增 ready_start_time

    loading_time_left = 0
    remaining_game_time = 0

    while True:
        try:
            async with websockets.connect(CONTROL_REGISTER_URL) as ws:
                print("[GameServer] 已連線中控")
                await ws.send(MY_GAME_SERVER_WS)

                while True:
                    now = time.time()

                    # ⭐ 自動切進入 loading
                    if len(connected_players) > 0 and game_phase == "waiting":
                        game_phase = "loading"
                        loading_start_time = now
                        print("[GameServer] 玩家已進入，開始 loading 倒數 10 秒！")

                    # ⭐ loading phase 處理
                    if game_phase == "loading" and loading_start_time is not None:
                        elapsed_loading = now - loading_start_time
                        loading_time_left = max(0, math.ceil(10 - elapsed_loading))

                        print(f"[GameServer] loading_time_left: {loading_time_left}, elapsed_loading: {elapsed_loading:.2f}")

                        # ⭐ 切換到 ready
                        if loading_time_left == 0 and game_phase == "loading":
                            game_phase = "ready"
                            ready_start_time = now
                            print("[GameServer] loading 完成，進入 ready 2 秒！")

                    # ⭐ ready phase 處理
                    if game_phase == "ready":
                        elapsed_ready = now - ready_start_time
                        if elapsed_ready >= 2:
                            game_phase = "playing"
                            game_start_time = now
                            print("[GameServer] Ready 完成，進入 Playing 60 秒！")

                    # ⭐ playing phase 處理
                    if game_phase == "playing":
                        elapsed_game = now - game_start_time
                        remaining_game_time = max(0, 60 - int(elapsed_game))

                        print(f"[GameServer] remaining_game_time: {remaining_game_time}")

                        if remaining_game_time == 0:
                            print("[GameServer] 遊戲結束，回到 waiting")
                            game_phase = "waiting"
                            loading_start_time = None
                            ready_start_time = None
                            game_start_time = None
                            loading_time_left = 0
                            remaining_game_time = 0
                            leaderboard.clear()  # 可選，重置排行榜

                    # ⭐ 發送狀態更新
                    status_update = {
                        "current_players": len(connected_players),
                        "in_game": len(connected_players) > 0,
                        "remaining_time": remaining_game_time if game_phase == "playing" else 0,  
                        "loading_time": loading_time_left if game_phase == "loading" else 0,  
                        "leaderboard": [
                            {"username": u, "score": s}
                            for u, s in sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
                        ],
                        "game_phase": game_phase
                    }

                    await ws.send(json.dumps(status_update))
                    print("[GameServer] 發送狀態更新", status_update)

                    # 發送 ping
                    await ws.send("ping")
                    await asyncio.sleep(0.5)

        except Exception as e:
            print(f"[GameServer] 中控連線失敗或斷線，3秒後重試: {e}")
            await asyncio.sleep(3)


@app.websocket("/status_ws")
async def status_ws(websocket: WebSocket):
    await websocket.accept()
    print("[GameServer] 有前端連到 status_ws！")

    try:
        while True:
            now = time.time()

            # 計算 remaining_game_time
            if game_phase == "playing":
                elapsed_game = now - game_start_time
                remaining_game_time = max(0, 60 - int(elapsed_game))
            else:
                remaining_game_time = 0

            # 計算 loading_time_left
            if game_phase == "loading" and loading_start_time is not None:
                elapsed_loading = now - loading_start_time
                loading_time_left = max(0, math.floor(10 - elapsed_loading) + 1)
            else:
                loading_time_left = 0

            # 發送 status_update
            status_update = {
                "current_players": len(connected_players),
                "in_game": len(connected_players) > 0,
                "remaining_time": remaining_game_time if game_phase == "playing" else 0,
                "loading_time": loading_time_left if game_phase == "loading" else 0,
                "leaderboard": [
                    {"username": u, "score": s}
                    for u, s in sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
                ],
                "game_phase": game_phase
            }

            await websocket.send_text(json.dumps(status_update))
            await asyncio.sleep(0.5)  # 1秒發一次，前端看起來順

    except WebSocketDisconnect:
        print("[GameServer] 有前端斷開 status_ws")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
