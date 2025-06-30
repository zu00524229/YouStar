# 中控 control.server.py
import asyncio
import websockets
import json
import time
import settings.control_set as set

# 假資料
fake_users = {
    "player1": {"password": "1234"},
    "player2": {"password": "5678"},
    "player3": {"password": "3333"},
    "player4": {"password": "4444"},
    "player5": {"password": "5555"}
}

# 狀態表初始化
gameserver_status = {}      # 儲存每一台已連線的 GameServer 狀態（connected / current_players / game_phase / leaderboard / last_heartbeat）
player_online_status = {}   # 儲存當前在線玩家狀態，防止重複登入
websocket_identity_map = {} # websocket: username or GameServer

# 中控 自動檢查 GameServer 是否掉線
async def heartbeat_checker():
    while True:
        now = time.time()
        # 如果 5 秒內沒收到 heartbeat 直接標記該 GameServer 斷線 ， 不會再分配玩家到這台server
        for server_url, status in list(gameserver_status.items()):
            if status["connected"] and (now - status["last_heartbeat"] > 5):
                print(f"[Heartbeat Checker] GameServer {server_url} timeout，標記為斷線")
                gameserver_status[server_url]["connected"] = False
        await asyncio.sleep(3)

# 處理每一條 websocket 連線（可能是 GameServer 或 Player Login / Player offline）
async def handle_client(websocket):
    try:
        while True:
            msg = await websocket.recv()
            data = json.loads(msg)

            # 玩家登入請求
            if data.get("type") == "login":
                username = data["username"]
                password = data["password"]
                user = fake_users.get(username)

                if user and user["password"] == password:
                    if username in player_online_status:
                        await websocket.send(json.dumps({
                            "type": "login_response",
                            "success": False,
                            "reason": "玩家已在線上"
                        }))
                    else:
                        player_online_status[username] = None
                        websocket_identity_map[websocket] = f"Player:{username}"  # 加入識別
                        print(f"[Login] 玩家 {username} 成功登入")
                        await websocket.send(json.dumps({
                            "type": "login_response",
                            "success": True
                        }))
                else:
                    await websocket.send(json.dumps({
                        "type": "login_response",
                        "success": False,
                        "reason": "帳號或密碼錯誤"
                    }))

            # --- GameServer 註冊流程 ---
            elif data.get("type") == "register_gameserver":
                server_url = data["server_url"]

                # 建立辨識表：記住這個 websocket 是哪一台 GameServer
                websocket_identity_map[websocket] = f"GameServer:{server_url}"
                print(f"[Register] GameServer 註冊: {server_url}")

                # 初始化該 GameServer 的狀態資訊（只做一次）
                gameserver_status[server_url] = {
                    "connected": True,              # 表示這台伺服器已連上
                    "current_players": 0,           # 初始人數為 0
                    "watching_players": 0,          # 觀看初始人數為 0
                    "max_players": set.DEFAULT_MAX_PLAYERS,  # 預設最大人數（可日後擴充）
                    # "in_game": False,             # 已淘汰欄位，改用 game_phase 判斷
                    "remaining_time": 0,            # 初始剩餘時間為 0（尚未開始遊戲）
                    "leaderboard": [],              # 初始排行榜為空
                    "last_heartbeat": time.time(),  # 記錄註冊時間（後續可用來偵測斷線）
                    "game_phase": "waiting"         # 初始階段為 waiting（等待中）
                }

                # 顯示目前所有已註冊的 GameServer 清單
                print(f"[Register] 目前在線 GameServer 有 {len(gameserver_status)} 台:")
                for url in gameserver_status:
                    print(f"    - {url}")

            # --- GameServer 狀態更新（每秒回報）---
            elif data.get("type") == "update_status":
                server_url = data.get("server_url")

                # 若該 server_url 有註冊過，就更新它的狀態
                if server_url in gameserver_status:
                    gameserver_status[server_url].update({
                        "current_players": data.get("current_players", 0),   # 更新目前人數
                        "watching_players": data.get("watching_players", 0),
                        "leaderboard": data.get("leaderboard", []),          # 更新排行榜
                        "remaining_time": data.get("remaining_time", 0),     # 更新剩餘遊戲時間
                        # "in_game": data.get("in_game", False),               # 這欄其實可移除（你已經不需要了）
                        "game_phase": data.get("game_phase", "waiting"),     # 更新目前遊戲階段
                        "last_heartbeat": time.time()                        # 更新心跳時間
                    })
                    # print(f"[中控] 更新 GameServer {server_url}：players = {data.get('current_players')}, watching = {data.get('watching_players')}")

            # 玩家請求 GameServer 列表
            elif data.get("type") == "get_server_list":
                websocket_identity_map[websocket] = "Temp:get_server_list"
                # print(f"[中控] 收到 get_server_list 請求")
                server_list = []
                for server_url, status in gameserver_status.items():
                    if status["connected"]:
                        server_list.append({
                            "server_url": server_url,       # 伺服器
                            "current_players": status["current_players"],       # 人數
                            "max_players": status["max_players"],               # 最大人數
                            "game_phase": status.get("game_phase", "waiting"),   # 狀態
                            "watching_players": status["watching_players"]      # 觀戰
                        })

                await websocket.send(json.dumps({
                    "type": "get_server_list_response",
                    "server_list": server_list
                }))

            # 玩家加入通知
            elif data.get("type") == "player_joined":
                username = data["username"]
                server_url = data["server_url"]
                player_online_status[username] = server_url
                print(f"[Player Join] 玩家 {username} 加入 Gameserver → {server_url}")

            # 玩家離線通知
            elif data.get("type") == "offline":
                username = data["username"]
                if username in player_online_status:
                    assigned_server = player_online_status[username]
                    print(f"[Offline] 玩家 {username} 離線 → GameServer {assigned_server}")
                    player_online_status.pop(username)
                    if assigned_server in gameserver_status:
                        gameserver_status[assigned_server]["current_players"] = max(
                            0, gameserver_status[assigned_server]["current_players"] - 1
                        )
                    await websocket.send(json.dumps({"type": "offline_response", "success": True}))
                else:
                    await websocket.send(json.dumps({
                        "type": "offline_response",
                        "success": False,
                        "reason": "玩家不在在線狀態表中"
                    }))

            # 排行榜請求
            elif data.get("type") == "get_leaderboard":
                gameserver_url = data["gameserver_url"]
                if gameserver_url in gameserver_status:
                    leaderboard = gameserver_status[gameserver_url]["leaderboard"]
                    await websocket.send(json.dumps({
                        "type": "get_leaderboard_response",
                        "leaderboard": leaderboard
                    }))
                else:
                    await websocket.send(json.dumps({
                        "type": "get_leaderboard_response",
                        "error": "GameServer 未找到"
                    }))
            
            # Heartbeat 或狀態更新 (GameServer 狀態)
            elif data.get("type") == "ping":
                server_url = None
                for url, status in gameserver_status.items():
                    if status["connected"]:
                        server_url = url
                        break
                if server_url:
                    gameserver_status[server_url]["last_heartbeat"] = time.time()


    except websockets.exceptions.ConnectionClosed:
        identity = websocket_identity_map.pop(websocket, None)
        if identity:
            if identity.startswith("Player:"):
                username = identity.split("Player:")[1]
                assigned_server = player_online_status.pop(username, "未知")
                print(f"[Disconnect] 玩家 {username} 與中控連線中斷 → 原本所在 GameServer: {assigned_server}")
                if assigned_server in gameserver_status:
                    gameserver_status[assigned_server]["current_players"] = max(
                        0, gameserver_status[assigned_server]["current_players"] - 1
                    )
            elif identity.startswith("GameServer:"):
                server_url = identity.split("GameServer:")[1]
                if server_url in gameserver_status:
                    gameserver_status[server_url]["connected"] = False
                    print(f"[Disconnect] GameServer {server_url} 與中控連線中斷")
        else:
            print("[Disconnect] 未知 websocket 連線中斷（尚未註冊身份）")


# 啟動 WebSocket Server + heartbeat_checker
async def main():
    server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    print("Control Server 已啟動，監聽 port 8765")
    # 啟動 heartbeat_checker
    asyncio.create_task(heartbeat_checker())
    await server.wait_closed()

# run
asyncio.run(main())

