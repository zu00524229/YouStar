# player_handler.py
import json
import time
import asyncio
import websockets
import settings.context as ct

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

# 玩家處理器
async def player_handler(websocket):
    username = await websocket.recv()
    print(f"[GameServer] 玩家 {username} 連線進來")

    ct.connected_players.add(username)
    ct.player_websockets[username] = websocket
    ct.post_gameover_cooldown = False

    # 通知中控：玩家加入
    asyncio.create_task(notify_control_player_joined(username))

    try:
        async for msg in websocket:
            print(f"[GameServer] 收到玩家 {username} 訊息: {msg}")

            try:
                if msg.startswith("hit:"):
                    parts = msg.split(":")
                    mole_id = int(parts[1])
                    player_score = int(parts[2])

                    if ct.current_mole["mole_id"] == mole_id and ct.current_mole["active"]:
                        print(f"[GameServer] 玩家 {username} 打中地鼠 {mole_id}，分數 {player_score}")
                        ct.current_mole["active"] = False

                        ct.current_scores[username] = player_score
                        current_best = ct.leaderboard.get(username, 0)
                        if player_score > current_best:
                            ct.leaderboard[username] = player_score
                            print(f"[GameServer] 更新 {username} 的最高分為 {player_score}")

                        mole_msg = {
                            "event": "mole_update",
                            "mole": ct.current_mole
                        }

                        for player, ws_conn in ct.player_websockets.items():
                            try:
                                await ws_conn.send(json.dumps(mole_msg))
                            except:
                                pass

                elif msg.startswith("special_hit:"):
                    parts = msg.split(":")
                    mole_id = int(parts[1])
                    player_score = int(parts[2])

                    if ct.current_special_mole["mole_id"] == mole_id and ct.current_special_mole["active"]:
                        print(f"[GameServer] 玩家 {username} 打中 Special Mole {mole_id}，分數 {player_score}")
                        ct.current_special_mole["active"] = False

                        ct.current_scores[username] = player_score
                        current_best = ct.leaderboard.get(username, 0)
                        if player_score > current_best:
                            ct.leaderboard[username] = player_score
                            print(f"[GameServer] 更新 {username} 的最高分為 {player_score}")

                        mole_msg = {
                            "event": "special_mole_update",
                            "mole": ct.current_special_mole
                        }

                        for player, ws_conn in ct.player_websockets.items():
                            try:
                                await ws_conn.send(json.dumps(mole_msg))
                            except:
                                pass
                    else:
                        print(f"[GameServer] 玩家 {username} 嘗試打已消失地鼠 {mole_id}，忽略")

                elif msg.startswith("final:"):
                    parts = msg.split(":")
                    final_user = parts[1]
                    final_score = int(parts[2])
                    print(f"[GameServer] 玩家 {final_user} 結束遊戲，最終分數 {final_score}")

                    current_best = ct.leaderboard.get(final_user, 0)
                    if final_score > current_best:
                        ct.leaderboard[final_user] = final_score
                        print(f"[GameServer] 更新 {final_user} 的最高分為 {final_score}")

                elif msg == "ready":
                    print(f"[GameServer] 收到 ready，進入 ready Offer 階段")
                    ct.ready_offer_active = True
                    ct.ready_offer_start_time = time.time()
                    ct.ready_players = {username}

                elif msg == "join_ready":
                    print(f"[GameServer] 玩家 {username} 選擇參加 ready")
                    ct.ready_players.add(username)

                else:
                    print(f"[GameServer] 收到未知訊息: {msg}")

            except Exception as e:
                print(f"[GameServer] 玩家 {username} 處理訊息出錯: {e}，msg={msg}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[GameServer] 玩家 {username} 離線")
        ct.connected_players.discard(username)
        ct.player_websockets.pop(username, None)
        print(f"[GameServer] 目前在線玩家: {ct.connected_players}")

        # 通知中控：玩家離線
        asyncio.create_task(notify_control_player_offline(username))
