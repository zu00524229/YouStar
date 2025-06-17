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
        first_msg = await websocket.recv()
        data = json.loads(first_msg)

        # GameServer 註冊流程
        if data.get("type") == "register_gameserver":
            server_url = data["server_url"]
            print(f"[Register] GameServer 註冊: {server_url}")

            # 初始化 GameServer 狀態欄位
            gameserver_status[server_url] = {
                "connected": True,
                "current_players": 0,
                "max_players": 3,
                "in_game": False,
                "remaining_time": 0,
                "leaderboard": [],
                "last_heartbeat": time.time()
            }

            # 列出目前在線 GameServer
            online_servers = [url for url, status in gameserver_status.items() if status["connected"]]
            print(f"[Register] 目前在線 GameServer 有 {len(online_servers)} 台:")
            for url in online_servers:
                print(f"    - {url}")

            # GameServer loop
            while True:
                msg = await websocket.recv()
                try:
                    status_update = json.loads(msg)
                    if status_update.get("type") == "ping":
                        gameserver_status[server_url]["last_heartbeat"] = time.time()
                        continue

                    # 更新 GameServer 狀態
                    gameserver_status[server_url]["current_players"] = status_update.get("current_players", 0)
                    gameserver_status[server_url]["leaderboard"] = status_update.get("leaderboard", [])
                    gameserver_status[server_url]["remaining_time"] = status_update.get("remaining_time", 0)
                    gameserver_status[server_url]["in_game"] = status_update.get("in_game", False)
                    gameserver_status[server_url]["game_phase"] = status_update.get("game_phase", "waiting")
                    gameserver_status[server_url]["last_heartbeat"] = time.time()

                except Exception as e:
                    print(f"[Error] GameServer 狀態解析失敗: {e}")

        # Player 登入流程
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
                    return

                # 只回 login success
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

        # 獨立處理 get_server_list
        elif data.get("type") == "get_server_list":
            server_list = []

            for server_url, status in gameserver_status.items():
                if status["connected"]:
                    server_list.append({
                        "server_url": server_url,
                        "current_players": status["current_players"],
                        "max_players": status["max_players"],
                        "game_phase": status["game_phase"]
                    })

            await websocket.send(json.dumps({
                "type": "get_server_list_response",
                "server_list": server_list
            }))

        # Player 離線流程
        elif data.get("type") == "offline":
            username = data["username"]

            if username in player_online_status:
                assigned_server = player_online_status[username]
                print(f"[Offline] 玩家 {username} 離線 → GameServer {assigned_server}")

                player_online_status.pop(username)

                if assigned_server in gameserver_status:
                    gameserver_status[assigned_server]["current_players"] = max(0, gameserver_status[assigned_server]["current_players"] - 1)

                await websocket.send(json.dumps({
                    "type": "offline_response",
                    "success": True
                }))
            else:
                await websocket.send(json.dumps({
                    "type": "offline_response",
                    "success": False,
                    "reason": "玩家不在在線狀態表中"
                }))

        # get_leaderboard
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

