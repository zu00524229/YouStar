# control_server.py → 純 WebSocket 版

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

# 狀態表
gameserver_status = {}
player_online_status = {}

# 中控 heartbeat 檢查 background task
async def heartbeat_checker():
    while True:
        now = time.time()
        for server_url, status in list(gameserver_status.items()):
            if status["connected"] and (now - status["last_heartbeat"] > 5):
                print(f"[Heartbeat Checker] GameServer {server_url} timeout，標記為斷線")
                gameserver_status[server_url]["connected"] = False
        await asyncio.sleep(3)

# 處理一個 websocket 連線（可以是 GameServer 或 Player）
async def handle_client(websocket):
    try:
        first_msg = await websocket.recv()
        data = json.loads(first_msg)

        if data.get("type") == "register_gameserver":
            server_url = data["server_url"]
            print(f"[Register] GameServer 註冊: {server_url}")

            gameserver_status[server_url] = {
                "connected": True,
                "current_players": 0,           # 目前已經進入玩家數
                "max_players": 1,               # 每台 Gameserver 最大允許人數
                "in_game": False,
                "remaining_time": 0,
                "leaderboard": [],
                "last_heartbeat": time.time()
            }

            online_servers = [url for url, status in gameserver_status.items() if status["connected"]]
            print(f"[Register] 目前在線 GameServer 有 {len(online_servers)} 台:")
            for url in online_servers:
                print(f"    - {url}")
            # GameServer loop → 持續接收 heartbeat + status
            while True:
                msg = await websocket.recv()
                try:
                    status_update = json.loads(msg)
                    if status_update.get("type") == "ping":
                        gameserver_status[server_url]["last_heartbeat"] = time.time()
                        continue  # 不要改 game_phase

                    gameserver_status[server_url]["current_players"] = status_update.get("current_players", 0)
                    gameserver_status[server_url]["leaderboard"] = status_update.get("leaderboard", [])
                    gameserver_status[server_url]["remaining_time"] = status_update.get("remaining_time", 0)
                    gameserver_status[server_url]["in_game"] = status_update.get("in_game", False)
                    gameserver_status[server_url]["game_phase"] = status_update.get("game_phase", "waiting")
                    gameserver_status[server_url]["last_heartbeat"] = time.time()


                    # print(f"[Status] GameServer {server_url} 狀態更新: {status_update}")
                    # print(f"[ControlServer] 更新後 game_phase = {gameserver_status[server_url]['game_phase']}")


                except Exception as e:
                    print(f"[Error] GameServer 狀態解析失敗: {e}")

        elif data.get("type") == "login":
            username = data["username"]
            password = data["password"]

            user = fake_users.get(username)
            if user and user["password"] == password:
                if username in player_online_status:
                    assigned_server = player_online_status[username]
                    await websocket.send(json.dumps({
                        "type": "login_response",
                        "success": False,
                        "reason": f"玩家已在線上 (GameServer: {assigned_server})"
                    }))
                    return

                # 指派 GameServer
                for server_url, status in gameserver_status.items():
                    if status["connected"] and status["game_phase"] in ["waiting", "loading"] and status["current_players"] < status["max_players"]:
                        player_online_status[username] = server_url
                        status["current_players"] += 1
                        print(f"[Login] 分配玩家 {username} 到 GameServer {server_url}")

                        await websocket.send(json.dumps({
                            "type": "login_response",
                            "success": True,
                            "assigned_server": server_url
                        }))
                        return

                # 沒有可用 GameServer
                await websocket.send(json.dumps({
                    "type": "login_response",
                    "success": False,
                    "reason": "目前沒有可用的 GameServer，請稍候..."
                }))

            else:
                await websocket.send(json.dumps({
                    "type": "login_response",
                    "success": False,
                    "reason": "帳號或密碼錯誤"
                }))

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

