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
            "connected": True,
            "current_players": 0,
            "max_players": 2,
            "in_game": False,
            "remaining_time": 0,
            "leaderboard": [],
            "last_heartbeat": time.time(),
            "loading_started": False,
            "loading_start_time": None,
            "game_start_time": None,
            "ready_started": False,
            "ready_start_time": None,
            "game_phase": "waiting"
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
                gameserver_status[data]["loading_time"] = status_update.get("loading_time", 0) or 0
                gameserver_status[data]["last_heartbeat"] = time.time()


                gs = gameserver_status[data]
                now = time.time()

                if gs["current_players"] == 0:
                    # Reset → waiting
                    gs["loading_started"] = False
                    gs["loading_start_time"] = None
                    gs["game_start_time"] = None
                    gs["ready_started"] = False
                    gs["ready_start_time"] = None
                    gs["in_game"] = False
                    gs["remaining_time"] = 0
                    gs["leaderboard"] = []
                    gs["game_phase"] = "waiting"

                elif gs["current_players"] > 0:
                    if not gs["loading_started"] and gs["game_start_time"] is None:
                        gs["loading_started"] = True
                        gs["loading_start_time"] = now
                        gs["game_phase"] = "loading"
                        print(f"[Control WS] GameServer {data} 開始 loading 倒數 10 秒")

                    if gs["loading_started"] and gs["game_start_time"] is None:
                        elapsed_loading = now - gs["loading_start_time"]
                        if elapsed_loading < 10:
                            gs["game_phase"] = "loading"
                            gs["in_game"] = False
                            gs["remaining_time"] = max(0, 10 - int(elapsed_loading))
                        elif not gs.get("ready_started", False):
                            gs["ready_started"] = True
                            gs["ready_start_time"] = now
                            gs["game_phase"] = "ready"
                            gs["in_game"] = False
                            gs["remaining_time"] = 0
                            print(f"[Control WS] GameServer {data} Ready！等待 2 秒")
                        elif gs.get("ready_started", False):
                            elapsed_ready = now - gs["ready_start_time"]
                            if elapsed_ready < 2:
                                gs["game_phase"] = "ready"
                                gs["in_game"] = False
                                gs["remaining_time"] = 0
                            else:
                                gs["game_start_time"] = now
                                gs["ready_started"] = False
                                gs["ready_start_time"] = None
                                gs["game_phase"] = "playing"
                                gs["in_game"] = True
                                gs["remaining_time"] = 60
                                print(f"[Control WS] GameServer {data} 正式進入遊戲中")

                    elif gs["game_start_time"] is not None:
                        elapsed_game = now - gs["game_start_time"]
                        remaining_game_time = max(0, 60 - int(elapsed_game))
                        gs["remaining_time"] = remaining_game_time
                        gs["in_game"] = remaining_game_time > 0
                        gs["game_phase"] = "playing"

                        if remaining_game_time == 0:
                            print(f"[Control WS] GameServer {data} 遊戲結束，重置為等待中")
                            gs["loading_started"] = False
                            gs["loading_start_time"] = None
                            gs["game_start_time"] = None
                            gs["ready_started"] = False
                            gs["ready_start_time"] = None
                            gs["in_game"] = False
                            gs["remaining_time"] = 0
                            gs["leaderboard"] = []
                            gs["game_phase"] = "waiting"

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

# 排行榜
@app.get("/get_leaderboard")
def get_leaderboard(gameserver_url: str):
    if gameserver_url in gameserver_status:
        leaderboard = gameserver_status[gameserver_url]["leaderboard"]
        return {"leaderboard": leaderboard}
    else:
        raise HTTPException(status_code=404, detail="GameServer 未找到")
    
###
@app.get("/get_gameserver_status")
def get_gameserver_status(gameserver_url: str):
    if gameserver_url in gameserver_status:
        gs = gameserver_status[gameserver_url]
        now = time.time()
        remaining_time = 0

        if gs["current_players"] == 0:
            gs["loading_started"] = False
            gs["loading_start_time"] = None
            gs["game_start_time"] = None
            gs["ready_started"] = False
            gs["ready_start_time"] = None
            gs["in_game"] = False
            gs["game_phase"] = "waiting"

            remaining_time = 0

        elif gs["current_players"] > 0:
            if gs["game_phase"] == "loading" and gs["loading_start_time"] is not None:
                remaining_time = gs.get("loading_time", 0)
                gs["remaining_time"] = remaining_time

            elif gs["game_phase"] == "ready" and gs["ready_start_time"] is not None:
                elapsed_ready = now - gs["ready_start_time"]
                remaining_time = max(0, 2 - int(elapsed_ready))
                gs["remaining_time"] = remaining_time

            elif gs["game_phase"] == "playing" and gs["game_start_time"] is not None:
                elapsed_game = now - gs["game_start_time"]
                remaining_time = max(0, 60 - int(elapsed_game))
                gs["remaining_time"] = remaining_time

            else:
                remaining_time = 0
                gs["remaining_time"] = remaining_time

        else:
            remaining_time = 0
            gs["remaining_time"] = remaining_time

        return {
            "current_players": gs["current_players"],
            "in_game": gs["in_game"],
            "remaining_time": remaining_time,
            "game_phase": gs.get("game_phase", "waiting")
        }

    else:
        raise HTTPException(status_code=404, detail="GameServer 未找到")



