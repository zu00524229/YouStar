# player_handler.py
import json
import time
import asyncio
import websockets
import settings.context as ct
import GameServer.broadcaster as bc
import GameServer.gm_replay as rep
import GameServer.gm_gameover as gov
import GameServer.gm_ready as rad
import GameServer.player_message_handler as pmh

# 通知 ControlServer：玩家加入
async def notify_control_player_joined(username):
    try:
        async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
            await ws.send(json.dumps({
                "type": "player_joined",
                "username": username,
                "server_url": ct.MY_GAME_SERVER_WS
            }))
            print(f"[GameServer] 已通知 ControlServer 玩家 {username} 加入 {ct.MY_GAME_SERVER_WS}")
    except Exception as e:
        print(f"[GameServer] 通知 ControlServer 玩家加入失敗: {e}")

# 通知 ControlServer：玩家離線
async def notify_control_player_offline(username):
    try:
        async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
            await ws.send(json.dumps({
                "type": "offline",
                "username": username
            }))
            print(f"[GameServer] 已通知 ControlServer 玩家 {username} offline")
    except Exception as e:
        print(f"[GameServer] 通知 ControlServer 玩家 offline 失敗: {e}")

# 殭屍連線掃描
async def zombie_player_cleaner():
    while True:
        to_remove = []      # 要移除的殭屍玩家列表

        # 對所有玩家的 WebSocket 進行 ping 測試
        for username, ws in ct.player_websockets.items():
            try:
                # ws.ping() ➜ 傳送一個 ping 訊號
                # pong_waiter ➜ 等待對方 pong 回應
                pong_waiter = await ws.ping()   
                await asyncio.wait_for(pong_waiter, timeout=2)  # 最多等 2 秒
            except:     # 若無回應，表示該 WebSocket 可能已斷線或異常中斷
                print(f"[殭屍清理] 玩家 {username} 無回應 ➜ 移除")
                to_remove.append(username)

        # 清除所有偵測到的殭屍玩家
        for username in to_remove:
            ct.connected_players.discard(username)        # 從在線名單移除
            ct.player_websockets.pop(username, None)     # 移除 WebSocket 映射
            ct.watch_players.discard(username)           # 移除觀戰名單（如果是觀戰者）
            await notify_control_player_offline(username)  # 通知 ControlServer 該玩家 offline
        # 每 10 秒執行一次檢查   
        await asyncio.sleep(10)


# 玩家處理器 GameServer 控制
async def player_handler(websocket):
    print("[Debug] player_handler() 開始")
    
    username = await websocket.recv()       # 接收 client connect_to_server() 資料
    # print(f"[GameServer] 玩家 {username} 建立 WebSocket ID = {id(websocket)}")
    print(f"[GameServer] 玩家 {username} 連線進來")

    ct.connected_players.add(username)
    ct.player_websockets[username] = websocket
    ct.post_gameover_cooldown = False

    # 通知 ControlServer：玩家連線
    asyncio.create_task(notify_control_player_joined(username))

    # 傳送目前的 GameServer 狀態給新加入的玩家
    try:
        # 發給 前端排行榜資料
        leaderboard_list = []
        for user in ct.connected_players:
            score = ct.current_scores.get(user, 0)
            leaderboard_list.append({
                "username": user,
                "score": score
            })

        # 給前端介面資料
        status_update = {
            "event": "status_update",
            "game_phase": ct.game_phase,
            "remaining_time": 0,
            "loading_time": 0,
            "current_players": len(ct.connected_players - ct.watch_players),  # 排除觀戰者
            "watching_players": len(ct.watch_players),                        # 觀戰者
            "leaderboard": sorted(leaderboard_list, key=lambda x: x["score"], reverse=True)
        }

        await websocket.send(json.dumps(status_update))
        print(f"[GameServer] 傳送初始狀態 status_update 給 {username}: {ct.game_phase}")

    except Exception as e:
        print(f"[GameServer] 傳送初始狀態給 {username} 失敗: {e}")

    # 接收玩家資料
    try:
        async for msg in websocket:
            # print(f"[GameServer] 收到玩家 {username} 訊息: {msg}")
            try:
                # 玩家點擊 ready
                if msg == "ready":
                    print(f"[GameServer] 玩家 {username} 發送 ready")
                    await rad.handle_ready(username)    # 使用方法

                # 一般地鼠接收訊號
                elif msg.startswith("hit:"):
                    await pmh.handle_hit(msg, username)
                                            
                # 特殊地鼠接收訊號
                elif msg.startswith("special_hit:"):
                    await pmh.handle_special_hit(msg, username)

                # 玩家提交最終分數：final:<username>:<score>
                elif msg.startswith("final:"):
                    await pmh.handle_final_score(msg)

                # 玩家觀戰模式（新增）
                elif msg == "watch":
                    if ct.game_phase == "playing":
                        ct.watch_players.add(username)
                        print(f"[GameServer] 玩家 {username} 設為觀戰者，目前觀戰人數：{len(ct.watch_players)}")
                    else:
                        print(f"[GameServer] 玩家 {username} 嘗試進入觀戰，但目前不是 playing 階段 → 忽略")

                elif msg == "again":
                    await rep.start_replay_offer(username)


                    # 遊戲結束後待機，等待指令
                    if ct.game_phase == "post_gameover" and ct.ready_players.issuperset(ct.connected_players):
                        await gov.reset_game_to_waiting()

                
                else:   # 未知訊息
                    pass
                    
            except Exception as e:
                print(f"[GameServer] 玩家 {username} 處理訊息錯誤: {e}，msg={msg}")

    finally:       # 
        if username:
            ct.connected_players.discard(username)
            ct.player_websockets.pop(username, None)
            ct.watch_players.discard(username)
            await notify_control_player_offline(username)
            print(f"[GameServer] 玩家 {username} 離線並清除狀態")
            print(f"[GameServer] 目前在線玩家: {ct.connected_players}")

