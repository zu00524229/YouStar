# player_handler.py
import json
import time
import asyncio
import websockets
import settings.context as ct
import GameServer.broadcaster as bc
import GameServer.gm_ready as rad

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

# 玩家處理器 GameServer 控制
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
                # 一般地鼠接收訊號
                if msg.startswith("hit:"):
                    parts = msg.split(":")
                    mole_id = int(parts[1])
                    player_score = int(parts[2])

                    hit_time = time.time()
                    spawn_time = ct.current_mole.get("spawn_time", 0)
                    duration = ct.current_mole.get("duration", 1.2)
                    print(f"[Debug] 玩家打擊延遲 {delay:.2f}s vs 容許 {duration:.2f}s")
                    delay = hit_time - spawn_time

                    if ct.current_mole["mole_id"] != mole_id:
                        print(f"[GameServer] 玩家 {username} 打錯地鼠 {mole_id}，當前是 {ct.current_mole['mole_id']}")
                        return

                    if not ct.current_mole["active"]:
                        print(f"[GameServer] 玩家 {username} 嘗試打已失效的地鼠 {mole_id}，忽略")
                        return

                    if delay > duration + 0.2:
                        print(f"[GameServer] 玩家 {username} 打太慢了，延遲 {delay:.2f}s > {duration:.2f}s，忽略")
                        return

                    # 命中地鼠
                    print(f"[GameServer] 玩家 {username} 打中地鼠 {mole_id}，分數 {player_score}")
                    ct.current_mole["active"] = False
                    ct.current_scores[username] = ct.current_scores.get(username, 0) + player_score

                    # 更新最高分
                    if ct.current_scores[username] > ct.leaderboard.get(username, 0):
                        ct.leaderboard[username] = ct.current_scores[username]
                        print(f"[GameServer] 更新 {username} 的最高分為 {ct.current_scores[username]}")

                    # 廣播目前地鼠狀態
                    await bc.broadcast({
                        "event": "mole_update",
                        "mole": ct.current_mole
                    })
                    
                    asyncio.create_task(bc.broadcast_leaderboard())
                    print("[Debug] 廣播 leaderboard 中:", ct.current_scores)

                    # for player, ws_conn in ct.player_websockets.items():
                    #     try:
                    #         await ws_conn.send(json.dumps(mole_msg))
                    #     except:
                    #         pass

                    # 非同步更新 leaderboard
                    
                        
                # 特殊地鼠接收訊號
                elif msg.startswith("special_hit:"):
                    parts = msg.split(":")
                    mole_id = int(parts[1])
                    player_score = int(parts[2])

                    if ct.current_special_mole["mole_id"] == mole_id and ct.current_special_mole["active"]:
                        print(f"[GameServer] 玩家 {username} 打中特殊地鼠 {mole_id}，分數 {player_score}")
                        ct.current_special_mole["active"] = False
                        ct.current_scores[username] = ct.current_scores.get(username, 0) + player_score

                        if ct.current_scores[username] > ct.leaderboard.get(username, 0):
                            ct.leaderboard[username] = ct.current_scores[username]
                            print(f"[GameServer] 更新 {username} 的最高分為 {ct.current_scores[username]}")

                        await bc.broadcast({
                            "event": "special_mole_update",
                            "mole": ct.current_special_mole
                        })
                    else:
                        print(f"[GameServer] 玩家 {username} 嘗試打不存在或已消失的特殊地鼠 {mole_id}")

                # 玩家點擊「Again」→ 啟動 ready offer 倒數
                elif msg == "ready":
                    print(f"[GameServer] 玩家 {username} 發送 ready")
                    await rad.handle_ready(username)

                # 玩家選擇參與 ready 階段
                elif msg == "join_ready":
                    print(f"[GameServer] 玩家 {username} 加入 ready 隊列")
                    ct.ready_players.add(username)

                # 玩家提交最終分數：final:<username>:<score>
                elif msg.startswith("final:"):
                    parts = msg.split(":")
                    final_user = parts[1]
                    final_score = int(parts[2])
                    print(f"[GameServer] 玩家 {final_user} 結束遊戲，最終分數 {final_score}")

                    if final_score > ct.leaderboard.get(final_user, 0):
                        ct.leaderboard[final_user] = final_score
                        print(f"[GameServer] 更新 {final_user} 的最高分為 {final_score}")

                # 未知訊息
                else:
                    print(f"[GameServer] 收到未知訊息: {msg}")

            except Exception as e:
                print(f"[GameServer] 玩家 {username} 處理訊息錯誤: {e}，msg={msg}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[GameServer] 玩家 {username} 離線")
        ct.connected_players.discard(username)
        ct.player_websockets.pop(username, None)
        asyncio.create_task(notify_control_player_offline(username))
        print(f"[GameServer] 目前在線玩家: {ct.connected_players}")
