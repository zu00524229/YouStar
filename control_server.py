# 中控 control.server.py
import asyncio
import websockets
import json
import time

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

            # GameServer 註冊流程（這台會進入自己的 loop）
            if data.get("type") == "register_gameserver":
                server_url = data["server_url"]
                print(f"[Register] GameServer 註冊: {server_url}")

                gameserver_status[server_url] = {
                    "connected": True,
                    "current_players": 0,
                    "max_players": 3,
                    "in_game": False,
                    "remaining_time": 0,
                    "leaderboard": [],
                    "last_heartbeat": time.time(),
                    "game_phase": "waiting"
                }

                print(f"[Register] 目前在線 GameServer 有 {len(gameserver_status)} 台:")
                for url in gameserver_status:
                    print(f"    - {url}")

            # Heartbeat 或狀態更新
            elif data.get("type") == "ping":
                server_url = None
                for url, status in gameserver_status.items():
                    if status["connected"]:
                        server_url = url
                        break
                if server_url:
                    gameserver_status[server_url]["last_heartbeat"] = time.time()

            elif data.get("type") == "update_status":
                server_url = data.get("server_url")
                if server_url in gameserver_status:
                    gameserver_status[server_url].update({
                        "current_players": data.get("current_players", 0),
                        "leaderboard": data.get("leaderboard", []),
                        "remaining_time": data.get("remaining_time", 0),
                        "in_game": data.get("in_game", False),
                        "game_phase": data.get("game_phase", "waiting"),
                        "last_heartbeat": time.time()
                    })

            # 玩家登入
            elif data.get("type") == "login":
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

            # get_server_list：✅這段現在才會被處理到
            elif data.get("type") == "get_server_list":
                print(f"[中控] 收到 get_server_list 請求")
                server_list = []
                for server_url, status in gameserver_status.items():
                    if status["connected"]:
                        server_list.append({
                            "server_url": server_url,
                            "current_players": status["current_players"],
                            "max_players": status["max_players"],
                            "game_phase": status.get("game_phase", "waiting")
                        })

                await websocket.send(json.dumps({
                    "type": "get_server_list_response",
                    "server_list": server_list
                }))

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

    except websockets.exceptions.ConnectionClosed:
        print(f"[Disconnect] 有 client 斷線")

# 啟動 WebSocket Server + heartbeat_checker
async def main():
    server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    print("Control Server 已啟動，監聽 port 8765")
    # 啟動 heartbeat_checker
    asyncio.create_task(heartbeat_checker())
    await server.wait_closed()

# run
asyncio.run(main())

