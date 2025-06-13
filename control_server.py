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
gameserver_status = {}      # 儲存每一台已註冊的 GameServer 狀態（connected / current_players / game_phase / leaderboard / last_heartbeat）
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
                "connected": True,              # GameServer 是否在線
                "current_players": 0,           # 目前已經進入玩家數
                "max_players": 2,               # 每台 Gameserver 最大允許人數
                "in_game": False,               # 檢查是否在遊戲中
                "remaining_time": 0,            # 遊戲剩餘秒數
                "leaderboard": [],              # 排行榜字典、查詢
                "last_heartbeat": time.time()   # 檢查 server 是否斷線
                # 最近一次 heartbeat 時間戳 → 用於判斷是否掉線
            }

            # 列出目前在線的 GameServer 列表
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
                
                    # 更新 GameServer 狀態欄位：
                    gameserver_status[server_url]["current_players"] = status_update.get("current_players", 0)
                # - current_players → 目前進入該 GameServer 的玩家數 → 用來控制是否還能分配新玩家。
                    gameserver_status[server_url]["leaderboard"] = status_update.get("leaderboard", [])
                # - leaderboard → 遊戲結束後會帶最新 leaderboard → ControlServer 儲存副本，供 get_leaderboard 查詢。
                    gameserver_status[server_url]["remaining_time"] = status_update.get("remaining_time", 0)
                # - remaining_time → 當前遊戲剩餘秒數 → 可供 UI 展示 / debug 用。
                    gameserver_status[server_url]["in_game"] = status_update.get("in_game", False)
                # - in_game → 是否正在進行遊戲 (playing phase) → 決定 ControlServer 要不要再分配新玩家。
                    gameserver_status[server_url]["game_phase"] = status_update.get("game_phase", "waiting")
                # - game_phase → GameServer 回報的遊戲階段（waiting / loading / ready / playing / gameover）。
                    gameserver_status[server_url]["last_heartbeat"] = time.time()
                # - last_heartbeat → 更新 heartbeat timestamp（就算是 status_update 也算是一次 heartbeat）。


                    # print(f"[Status] GameServer {server_url} 狀態更新: {status_update}")
                    # print(f"[ControlServer] 更新後 game_phase = {gameserver_status[server_url]['game_phase']}")

                except Exception as e:
                    print(f"[Error] GameServer 狀態解析失敗: {e}")

        # Player 登入流程
        elif data.get("type") == "login":
            username = data["username"] # 帳號
            password = data["password"] # 密碼
            user = fake_users.get(username)

            # 防止重複登入
            if user and user["password"] == password:
            # 如果該 username 已經在 player_online_status 裡 → 表示該玩家已經在線（已分配到某一台 GameServer）
                if username in player_online_status:
                    assigned_server = player_online_status[username]
                    await websocket.send(json.dumps({
                        "type": "login_response",
                        "success": False,
                        "reason": f"玩家已在線上 (GameServer: {assigned_server})"
                    }))
                    return

                # 遍歷 GameServer → 指派可用 GameServer
                for server_url, status in gameserver_status.items():
                    # connected == True → GameServer 在線
                    # game_phase 是 waiting 或 loading → 遊戲尚未進行 → 可以加新玩家
                    # current_players < max_players → 該 server 還有空位可分配
                    if status["connected"] and status["game_phase"] in ["waiting", "loading"] and status["current_players"] < status["max_players"]:
                        player_online_status[username] = server_url # 更新:記錄該玩家已被分配到哪一台 GameServer
                        status["current_players"] += 1              # 更新該 GameServer : +1 ，表示有新玩家進入
                        print(f"[Login] 分配玩家 {username} 到 GameServer {server_url}")

                    # 回應 login_response 給 client
                        await websocket.send(json.dumps({
                            "type": "login_response",       # 給 client → 通知
                            "success": True,                # client 已成功登入
                            "assigned_server": server_url   # 並分配到的 GameServer URL
                        }))
                        return

                # 沒有可用 GameServer
                await websocket.send(json.dumps({
                    "type": "login_response",       # connected == True 
                    "success": False,               # login 失敗，伺服器端資源不足
                    "reason": "目前沒有可用的 GameServer，請稍候..."
                    # current_players < max_players 代表滿員
                }))

            else:
                # 帳號或密碼錯誤 → 回應錯誤
                await websocket.send(json.dumps({
                    "type": "login_response",   
                    "success": False,       # login 失敗，伺服器端資源不足
                    "reason": "帳號或密碼錯誤"
                }))

        # Player 離線流程
        elif data.get("type") == "offline":
            username = data["username"]

            # 如果玩家在線，處理離線流程
            # 該玩家存在於 player_online_status
            if username in player_online_status:
                assigned_server = player_online_status[username]                       # 取得 玩家資料
                print(f"[Offline] 玩家 {username} 離線 → GameServer {assigned_server}") # 用來debug
                
                # 將該玩家從 player_online_status 中移除
                player_online_status.pop(username) 

                # 回收 GameServer 當前玩家數
                if assigned_server in gameserver_status:
                    gameserver_status[assigned_server]["current_players"] = max(0, gameserver_status[assigned_server]["current_players"] - 1)

                # 回應client
                await websocket.send(json.dumps({
                    "type": "offline_response",
                    "success": True
                }))
            else: # 錯誤回應(如果不再線)
                await websocket.send(json.dumps({
                    "type": "offline_response",
                    "success": False,
                    "reason": "玩家不在在線狀態表中"
                }))

        # 當收到 get_leaderboard 代表client 要查詢 leaderboard(排行榜)
        elif data.get("type") == "get_leaderboard":
            gameserver_url = data["gameserver_url"] # client 提供 url:查詢 GameServer 的 leaderboard
            
            # 如果 GameServer 存在
            if gameserver_url in gameserver_status:
                # 代表該 GameServer 有註冊，且 ControlServer 有同步它的 leaderboard。
                # 取的該server的leaderboard欄位
                leaderboard = gameserver_status[gameserver_url]["leaderboard"]

                # 回傳給 client
                await websocket.send(json.dumps({
                    "type": "get_leaderboard_response",
                    "leaderboard": leaderboard
                }))
            else:
                # 回應錯誤
                await websocket.send(json.dumps({
                    "type": "get_leaderboard_response",
                    "error": "GameServer 未找到"
                }))

    # 如果斷線 直接log輸出
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

