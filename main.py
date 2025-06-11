from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import json

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 假資料
fake_users = {
    "player1": {"password": "1234"},
    "player2": {"password": "5678"},
    "player3": {"password": "3333"},
    "player4": {"password": "4444"},
    "player5": {"password": "5555"}
}

# 狀態表
gameserver_status = {}
player_online_status = dict()

# /login
class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.post("/login")
def login(request: LoginRequest):
    user = fake_users.get(request.username)
    if user and user["password"] == request.password:
        if request.username in player_online_status:
            assigned_server = player_online_status[request.username]
            raise HTTPException(status_code=403, detail=f"玩家已在線上 (GameServer: {assigned_server})")

        for server_url, status in gameserver_status.items():
            if status["connected"] and not status["in_game"] and status["current_players"] < status["max_players"]:
                player_online_status[request.username] = server_url
                status["current_players"] += 1
                print(f"[Login] 分配玩家 {request.username} 到 GameServer {server_url}")
                return {"message": "登入成功", "assigned_server": server_url}

        remaining_times = [s["remaining_time"] for s in gameserver_status.values() if s["connected"] and s["in_game"]]
        wait_time = min(remaining_times) if remaining_times else 0

        return {
            "message": "目前沒有可用的 GameServer，請稍候...",
            "waiting": True,
            "remaining_time": wait_time
        }

    else:
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")

# /register_gameserver
@app.websocket("/register_gameserver")
async def register_gameserver(websocket: WebSocket):
    await websocket.accept()

    try:
        data = await websocket.receive_text()
        print(f"[Register] GameServer 註冊: {data}")

        gameserver_status[data] = {
            "connected": True,                  # GameServer 是否在線 (心跳用)
            "current_players": 0,               # 目前 GameServer 上線玩家數
            "max_players": 2,                   # 每台 GameServer 最大容納玩家數
            "in_game": False,                   # 遊戲進行狀態 → True=遊戲中 / False=loading/等待
            "remaining_time": 0,                # loading 或遊戲進行時的倒數秒數
            "leaderboard": [],                  # 當前排行榜，list of {"username":..., "score":...}
            "last_heartbeat": time.time(),      # 最近一次收到心跳的時間 → 用於判斷斷線
            "loading_started": False,           # 是否已進入 loading 倒數階段
            "loading_start_time": None,         # loading 倒數開始時間戳
            "game_start_time": None             # 正式遊戲開始時間戳
        }

        while True:
            msg = await websocket.receive_text()

            if msg == "ping":
                gameserver_status[data]["last_heartbeat"] = time.time()
                print(f"[Ping] GameServer {data} ping")
                continue

            try:
                status_update = json.loads(msg)
                gameserver_status[data]["current_players"] = status_update.get("current_players", 0)
                gameserver_status[data]["leaderboard"] = status_update.get("leaderboard", [])
                gameserver_status[data]["last_heartbeat"] = time.time()

                gs = gameserver_status[data]
                now = time.time()

                
                if gs["current_players"] > 0 and not gs["loading_started"]:
                    gs["loading_started"] = True
                    gs["loading_start_time"] = time.time()
                    print(f"[Control] GameServer {data} 開始 loading 倒數 10 秒")

                if gs["loading_started"] and gs["game_start_time"] is None:
                    elapsed_loading = now - gs["loading_start_time"]
                    if elapsed_loading < 10:
                        gs["in_game"] = False
                        gs["remaining_time"] = 10 - int(elapsed_loading)
                    else:
                        gs["in_game"] = True
                        gs["game_start_time"] = now
                        gs["remaining_time"] = 60
                        print(f"[Control] GameServer {data} 正式進入遊戲中")

                elif gs["game_start_time"] is not None:
                    elapsed_game = now - gs["game_start_time"]
                    remaining_game_time = max(0, 60 - int(elapsed_game))
                    gs["remaining_time"] = remaining_game_time
                    gs["in_game"] = remaining_game_time > 0

                    if remaining_game_time == 0:
                        print(f"[Control] GameServer {data} 遊戲結束，重置為等待中")
                        gs["loading_started"] = False
                        gs["loading_start_time"] = None
                        gs["game_start_time"] = None
                        gs["in_game"] = False
                        gs["remaining_time"] = 0
                        gs["leaderboard"] = []

                print(f"[Status] GameServer {data} 狀態更新: {status_update}")

            except Exception as e:
                print(f"[Error] 解析 GameServer 狀態失敗: {e}")

    except WebSocketDisconnect:
        print(f"[Disconnect] GameServer 離線: {data}")
        gameserver_status[data]["connected"] = False

# /player_offline
class PlayerOfflineRequest(BaseModel):
    username: str

@app.post("/player_offline")
def player_offline(request: PlayerOfflineRequest):
    if request.username in player_online_status:
        assigned_server = player_online_status[request.username]
        print(f"[Offline] 玩家 {request.username} 離線，移除在線狀態 / 更新 GameServer")
        player_online_status.pop(request.username)

        if assigned_server in gameserver_status:
            gameserver_status[assigned_server]["current_players"] = max(0, gameserver_status[assigned_server]["current_players"] - 1)

        return {"message": "玩家離線狀態已清除"}
    else:
        return {"message": "玩家不在在線狀態表中"}

# /get_leaderboard
@app.get("/get_leaderboard")
def get_leaderboard(gameserver_url: str):
    if gameserver_url in gameserver_status:
        leaderboard = gameserver_status[gameserver_url]["leaderboard"]
        return {"leaderboard": leaderboard}
    else:
        raise HTTPException(status_code=404, detail="GameServer 未找到")

# /get_gameserver_status
@app.get("/get_gameserver_status")
def get_gameserver_status(gameserver_url: str):
    if gameserver_url in gameserver_status:
        gs = gameserver_status[gameserver_url]
        now = time.time()

        if gs["loading_started"] and gs["game_start_time"] is None:
            elapsed_loading = now - gs["loading_start_time"]
            if elapsed_loading < 10:
                gs["in_game"] = False
                gs["remaining_time"] = 10 - int(elapsed_loading)
            else:
                gs["in_game"] = True
                gs["game_start_time"] = now
                gs["remaining_time"] = 60
                print(f"[Control GET] GameServer {gameserver_url} 正式進入遊戲中（GET觸發）")

        elif gs["game_start_time"] is not None:
            elapsed_game = now - gs["game_start_time"]
            remaining_game_time = max(0, 60 - int(elapsed_game))
            gs["remaining_time"] = remaining_game_time
            gs["in_game"] = remaining_game_time > 0

            if remaining_game_time == 0:
                print(f"[Control GET] GameServer {gameserver_url} 遊戲結束，重置為等待中（GET觸發）")
                gs["loading_started"] = False
                gs["loading_start_time"] = None
                gs["game_start_time"] = None
                gs["in_game"] = False
                gs["remaining_time"] = 0
                gs["leaderboard"] = []

        return {
            "current_players": gs["current_players"],
            "in_game": gs["in_game"],
            "remaining_time": gs["remaining_time"]
        }

    else:
        raise HTTPException(status_code=404, detail="GameServer 未找到")
