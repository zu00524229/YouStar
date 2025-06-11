from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import requests
import asyncio
import websockets
import json
import time
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(register_to_control())
    yield
    print("[GameServer] 關閉中...")

app = FastAPI(lifespan=lifespan)

@app.websocket("/ws")
async def player_ws(websocket: WebSocket):
    await websocket.accept()
    username = await websocket.receive_text()
    print(f"[GameServer] 玩家 {username} 連線進來")
    connected_players.add(username)

    try:
        while True:
            await websocket.send_text("地鼠出現!")
            await asyncio.sleep(5)

            msg = await websocket.receive_text()
            print(f"[GameServer] 收到玩家 {username} 訊息: {msg}")

            # 玩家打中地鼠
            if msg.startswith("hit:"):
                parts = msg.split(":")
                mole_name = parts[1]
                player_score = int(parts[2])
                print(f"[GameServer] 玩家 {username} 打中 {mole_name}，目前分數 {player_score}")

            # 玩家遊戲結束送最終分數
            elif msg.startswith("final:"):
                parts = msg.split(":")
                final_user = parts[1]
                final_score = int(parts[2])
                print(f"[GameServer] 玩家 {final_user} 結束遊戲，最終分數 {final_score}")

                # 保留每位玩家最高分
                current_best = leaderboard.get(final_user, 0)
                if final_score > current_best:
                    leaderboard[final_user] = final_score
                    print(f"[GameServer] 更新 {final_user} 的最高分為 {final_score}")

            await websocket.send_text(f"收到你的訊息: {msg}")

    except WebSocketDisconnect:
        print(f"[GameServer] 玩家 {username} 離線")
        connected_players.discard(username)
        try:
            requests.post(CONTROL_PLAYER_OFFLINE_URL, json={"username": username})
        except Exception as e:
            print(f"[GameServer] 通知中控失敗: {e}")

# 註冊自己到中控 + 定期回報狀態
async def register_to_control():
    global loading_started, loading_start_time
    global game_start_time

    while True:
        try:
            async with websockets.connect(CONTROL_REGISTER_URL) as ws:
                print("[GameServer] 已連線中控")
                await ws.send(MY_GAME_SERVER_WS)

                while True:
                    now = time.time()

                    # 判斷目前階段
                    if loading_started and (now - loading_start_time) < loading_time:
                        # loading 倒數階段
                        remaining_time = loading_time - int(now - loading_start_time)
                        in_game = False
                    elif loading_started and game_start_time is None:
                        # loading 結束，遊戲正式開始
                        game_start_time = time.time()
                        remaining_time = GAME_DURATION
                        in_game = True
                        print("[GameServer] 正式開始遊戲！")
                    elif game_start_time is not None:
                        # 遊戲進行中
                        elapsed_game_time = int(now - game_start_time)
                        remaining_time = max(0, GAME_DURATION - elapsed_game_time)
                        in_game = remaining_time > 0
                    else:
                        # 尚未開始
                        remaining_time = 0
                        in_game = False

                    status_update = {
                        "current_players": len(connected_players),
                        "in_game": len(connected_players) > 0,
                        "remaining_time": remaining_time,
                        "leaderboard": [
                            {"username": u, "score": s}
                            for u, s in sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
                        ]
                    }
                    await ws.send(json.dumps(status_update))

                    print("[GameServer] 發送狀態更新", status_update)

                    await ws.send("ping")
                    await asyncio.sleep(5)

        except Exception as e:
            print(f"[GameServer] 中控連線失敗或斷線，3秒後重試: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
