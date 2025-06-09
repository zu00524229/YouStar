from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
import json

app = FastAPI()

# CORS Middleware 允許其他來源
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
    "player2": {"password": "5678"}
}

# 狀態表
gameserver_status = {}

player_online_status = dict()  # key: username, value: assigned_server

# LoginRequest
class LoginRequest(BaseModel):
    username: str
    password: str

# /login
@app.post("/login")
def login(request: LoginRequest):
    user = fake_users.get(request.username)
    if user and user["password"] == request.password:
        # 檢查是否已在線上
        if request.username in player_online_status:
            assigned_server = player_online_status[request.username]
            raise HTTPException(status_code=403, detail=f"玩家已在線上 (GameServer: {assigned_server})")

        # 遍歷 gameserver_status 找一台可用的
        for server_url, status in gameserver_status.items():
            if status["connected"] and not status["in_game"] and status["current_players"] < status["max_players"]:
                # 找到可用 → 分配
                player_online_status[request.username] = server_url
                # 更新 GameServer 的 current_players
                status["current_players"] += 1
                print(f"[Login] 分配玩家 {request.username} 到 GameServer {server_url}")
                return {"message": "登入成功", "assigned_server": server_url}

        # 如果沒有可用的 → 回 waiting + 最小 remaining_time
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

        # 初始化該 GameServer 狀態
        gameserver_status[data] = {
            "connected": True,
            "current_players": 0,
            "max_players": 2,
            "in_game": False,
            "remaining_time": 0,
            "leaderboard": [],
            "last_heartbeat": time.time()
        }

        while True:
            msg = await websocket.receive_text()

            if msg == "ping":
                # 更新
                gameserver_status[data]["last_heartbeat"] = time.time()
                print(f"[Ping] GameServer {data} ping")
                continue  

            # 假設 GameServer 傳 JSON 格式 status_update
            try:
                status_update = json.loads(msg)
                gameserver_status[data]["current_players"] = status_update.get("current_players", 0)
                gameserver_status[data]["in_game"] = status_update.get("in_game", False)
                gameserver_status[data]["remaining_time"] = status_update.get("remaining_time", 0)
                gameserver_status[data]["leaderboard"] = status_update.get("leaderboard", [])
                gameserver_status[data]["last_heartbeat"] = time.time()

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

        # 減少 GameServer current_players
        if assigned_server in gameserver_status:
            gameserver_status[assigned_server]["current_players"] = max(0, gameserver_status[assigned_server]["current_players"] - 1)

        return {"message": "玩家離線狀態已清除"}
    else:
        return {"message": "玩家不在在線狀態表中"}

@app.get("/get_leaderboard")
def get_leaderboard(gameserver_url: str):
    if gameserver_url in gameserver_status:
        leaderboard = gameserver_status[gameserver_url]["leaderboard"]
        return {"leaderboard": leaderboard}
    else:
        raise HTTPException(status_code=404, detail="GameServer 未找到")
