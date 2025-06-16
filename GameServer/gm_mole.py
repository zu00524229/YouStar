# gm_server 控制地鼠邏輯

import random
import asyncio
import json
import time
import websockets
import settings.context as context

# 一般地鼠
async def mole_sender():
    while True:
        print("[GameServer] mole_sender 等待 phase_changed_event (playing)")
        await context.phase_changed_event.wait()
        print("[GameServer] mole_sender 收到 phase_changed_event → 檢查 game_phase =", context.game_phase)

        if context.game_phase == "playing":
            context.phase_changed_event.clear()
            print("[GameServer] mole_sender 進入 playing loop!")

            while context.game_phase == "playing":
                # 生成新地鼠
                context.current_mole_id += 1
                context.current_mole = {
                    "mole_id": context.current_mole_id,
                    "position": random.randint(0, 11),
                    "mole_type": random.choice(["Mole", "Gold Mole", "Bomb Mole", "Joker Mole"]),                    
                    "active": True
                }

                mole_msg = {
                    "event": "mole_update",
                    "mole": context.current_mole
                }

                for player, ws_conn in context.player_websockets.items():
                    try:
                        await ws_conn.send(json.dumps(mole_msg))
                    except:
                        pass

                sleep_time = random.uniform(0.6, 1.5)
                start_sleep = time.time()
                while time.time() - start_sleep < sleep_time:
                    if context.game_phase != "playing":
                        print("[GameServer] mole_sender 偵測到離開 playing, break inner loop")
                        break
                    await asyncio.sleep(0.05)

# 特殊地鼠
async def special_mole_sender():
    while True:
        await context.phase_changed_event.wait()
        print("[GameServer] special_mole_sender 收到 phase_changed_event → 檢查 game_phase =", context.game_phase)

        if context.game_phase == "playing":
            print("[GameServer] special_mole_sender 進入 playing loop!")

            while context.game_phase == "playing":
                sleep_time = random.uniform(5.0, 10.0)
                await asyncio.sleep(sleep_time)

                if context.game_phase != "playing":
                    break

                context.current_special_mole_id += 1

                all_positions = set(range(12))
                occupied_position = {context.current_mole["position"]}
                available_positions = list(all_positions - occupied_position)

                if not available_positions:
                    print("[GameServer] 沒有可用位置放特殊地鼠，跳過這輪")
                    continue

                context.current_special_mole = {
                    "mole_id": context.current_special_mole_id,
                    "position": random.choice(available_positions),
                    "mole_type": "Diamond Mole",
                    "active": True
                }

                mole_msg = {
                    "event": "special_mole_update",
                    "mole": context.current_special_mole
                }

                for player, ws_conn in context.player_websockets.items():
                    try:
                        await ws_conn.send(json.dumps(mole_msg))
                    except:
                        pass

                print(f"[GameServer] 發送 Special Mole ID {context.current_special_mole_id} at pos {context.current_special_mole['position']}")

# 玩家處理器
async def player_handler(websocket):
    username = await websocket.recv()
    print(f"[GameServer] 玩家 {username} 連線進來")
    context.connected_players.add(username)
    context.player_websockets[username] = websocket
    context.post_gameover_cooldown = False

    try:
        async for msg in websocket:
            print(f"[GameServer] 收到玩家 {username} 訊息: {msg}")

            try:
                if msg.startswith("hit:"):
                    parts = msg.split(":")
                    mole_id = int(parts[1])
                    player_score = int(parts[2])

                    if context.current_mole["mole_id"] == mole_id and context.current_mole["active"]:
                        print(f"[GameServer] 玩家 {username} 打中地鼠 {mole_id}，分數 {player_score}")
                        context.current_mole["active"] = False

                        context.current_scores[username] = player_score
                        current_best = context.leaderboard.get(username, 0)
                        if player_score > current_best:
                            context.leaderboard[username] = player_score
                            print(f"[GameServer] 更新 {username} 的最高分為 {player_score}")

                        mole_msg = {
                            "event": "mole_update",
                            "mole": context.current_mole
                        }

                        for player, ws_conn in context.player_websockets.items():
                            try:
                                await ws_conn.send(json.dumps(mole_msg))
                            except:
                                pass

                elif msg.startswith("special_hit:"):
                    parts = msg.split(":")
                    mole_id = int(parts[1])
                    player_score = int(parts[2])

                    if context.current_special_mole["mole_id"] == mole_id and context.current_special_mole["active"]:
                        print(f"[GameServer] 玩家 {username} 打中 Special Mole {mole_id}，分數 {player_score}")
                        context.current_special_mole["active"] = False

                        context.current_scores[username] = player_score
                        current_best = context.leaderboard.get(username, 0)
                        if player_score > current_best:
                            context.leaderboard[username] = player_score
                            print(f"[GameServer] 更新 {username} 的最高分為 {player_score}")

                        mole_msg = {
                            "event": "special_mole_update",
                            "mole": context.current_special_mole
                        }

                        for player, ws_conn in context.player_websockets.items():
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

                    current_best = context.leaderboard.get(final_user, 0)
                    if final_score > current_best:
                        context.leaderboard[final_user] = final_score
                        print(f"[GameServer] 更新 {final_user} 的最高分為 {final_score}")

                elif msg == "replay":
                    print(f"[GameServer] 收到 replay，進入 Replay Offer 階段")
                    context.replay_offer_active = True
                    context.replay_offer_start_time = time.time()
                    context.replay_players = set()

                elif msg == "join_replay":
                    print(f"[GameServer] 玩家 {username} 選擇參加 Replay")
                    context.replay_players.add(username)

                else:
                    print(f"[GameServer] 收到未知訊息: {msg}")

            except Exception as e:
                print(f"[GameServer] 玩家 {username} 處理訊息出錯: {e}，msg={msg}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[GameServer] 玩家 {username} 離線")
        context.connected_players.discard(username)
        context.player_websockets.pop(username, None)
        print(f"[GameServer] 目前在線玩家: {context.connected_players}")

        try:
            async def notify_control_offline():
                async with websockets.connect(context.CONTROL_SERVER_WS) as ws_control:
                    await ws_control.send(json.dumps({
                        "type": "offline",
                        "username": username
                    }))
                    print(f"[GameServer] 已通知 ControlServer 玩家 {username} offline")
            asyncio.create_task(notify_control_offline())
        except Exception as e:
            print(f"[GameServer] 通知 ControlServer 玩家 {username} offline 失敗: {e}")
