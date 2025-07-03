# player_handler.py
import json
import time
import asyncio
import websockets
import settings.context as ct
import GameServer.broadcaster as bc
import GameServer.gm_again as rep
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

# 通知 ControlServer : 觀察者加入
async def notify_control_watcher_joined(username):
    try:
        async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
            await ws.send(json.dumps({
                "type": "watcher_joined",
                "username": username,
                "server_url": ct.MY_GAME_SERVER_WS
            }))
            print(f"[GameServer] 已通知 ControlServer 觀戰者 {username} 加入 {ct.MY_GAME_SERVER_WS}")
    except Exception as e:
        print(f"[GameServer] 通知 ControlServer 觀戰者加入失敗: {e}")

# 通知 ControlServer： 觀察者離線
async def notify_control_watcher_offline(username):
    try:
        async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
            await ws.send(json.dumps({
                "type": "watcher_offline",
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
    # print("[Debug] player_handler() 開始")
    
    msg = await websocket.recv()
    # print(f"[GameServer] 接收到初始訊息：{msg}")

   # [修正點] 擋掉觀戰者錯送的訊息
    if msg.startswith('{'):
        try:
            data = json.loads(msg)
            if data.get("type") == "new_slot_available":
                # print("[忽略] 接收到非玩家的 new_slot_available 訊息 → 關閉連線")
                await websocket.close()
                return
        except:
            pass  # 忽略解析失敗

    # 如果是觀戰者
    if msg == "watch":
        username = f"watcher_{len(ct.watch_players)+1}"  # 自動命名
        if ct.game_phase in ["playing", "gameover", "post_gameover"]:
            ct.watch_players.add(username)
            ct.player_websockets[username] = websocket  # 觀戰者也要登記websocket
            print(f"[GameServer] 觀戰者加入：{username}")
            asyncio.create_task(notify_control_watcher_joined(username))
        else:
            print(f"[GameServer] 非 playing 階段，不接受觀戰者 → 關閉連線")
            await websocket.close()
            return

    # 如果是玩家
    else:
        username = msg
        ct.connected_players.add(username)      # 
        # 通知 ControlServer：玩家連線
        asyncio.create_task(notify_control_player_joined(username))
        print(f"[GameServer] 玩家加入：{username}")

    # ct.connected_players.add(username)
    ct.player_websockets[username] = websocket
    ct.post_gameover_cooldown = False


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

                # 玩家在玩一局
                elif msg == "again":
                    if not ct.again_active:
                        ct.again_active = True
                        ct.again_start_time = time.time()
                        print(f"[Replay] 玩家 {username} 觸發 Again，開始全房間倒數")
                        asyncio.create_task(rep.start_again_countdown())
                    else:
                        print(f"[Replay] 玩家 {username} 點擊 Again，但倒數已啟動，忽略")

                # 推薦有空位的 GameServer
                elif msg == "get_available_servers":
                    # 回傳目前 GameServer 知道的推薦清單
                    await websocket.send(json.dumps({
                        "type": "available_servers",
                        "servers": ct.available_servers
                    }))

                
                else:   # 未知訊息
                    pass
                    
            except Exception as e:
                print(f"[GameServer] 玩家 {username} 處理訊息錯誤: {e}，msg={msg}")
                await websocket.close()
                return

    finally:       # 
        if username:
            try:
                is_watcher = username in ct.watch_players       # 先判斷是不是觀察者

                ct.connected_players.discard(username)          # 從「目前連線玩家名單」中移除該玩家
                ct.player_websockets.pop(username, None)        # 移除 WebSocket 映射：這樣 zombie_cleaner 不會繼續嘗試 ping
                ct.watch_players.discard(username)              # 如果他是觀戰者，也從觀戰名單中移除

                if is_watcher:
                    ct.watch_players.discard(username)
                    await notify_control_watcher_offline(username)  # 觀察者離線
                else:
                    await notify_control_player_offline(username)   # 玩家離線

                print(f"[GameServer] 玩家 {username} 離線並清除狀態")
                print(f"[GameServer] 目前在線玩家: {ct.connected_players}")
            except Exception as e:
                print(f"[GameServer] finally 區段錯誤: {e}")

