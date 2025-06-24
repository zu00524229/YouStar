# player_message_handler.py

import time
import json
import asyncio
import settings.context as ct
import GameServer.broadcaster as bc

async def handle_hit(msg, username):
    parts = msg.split(":")
    if len(parts) < 2:
        print(f"[GameServer] hit 訊息格式錯誤：{msg}")
        return

    try:
        mole_id = int(parts[1])
    except ValueError:
        print(f"[GameServer] 無效的 mole_id：{parts[1]}")
        return

    hit_time = time.time()
    spawn_time = ct.current_mole.get("spawn_time", 0)
    duration = ct.current_mole.get("duration", 1.2)
    delay = hit_time - spawn_time
    print(f"[Debug] 玩家打擊延遲 {delay:.2f}s vs 容許 {duration:.2f}s")

    # 檢查地鼠ID是否為最新或是否還有效(活著)
    if mole_id != ct.current_mole["mole_id"] or not ct.current_mole["active"]:
        print(f"[GameServer] 玩家 {username} 打擊無效：地鼠 ID 不符或已失效")
        return
    
    # 延遲檢查(防止重複得分，只讓最快玩家得分)
    if delay > duration + 0.2:
        print(f"[GameServer] 玩家 {username} 打太慢了，延遲 {delay:.2f}s > {duration:.2f}s，忽略")
        return

    # 後端決定得分
    player_score = ct.current_mole.get("score", 0)
    print(f"[GameServer] 玩家 {username} 打中地鼠 {mole_id}，分數 {player_score}")

    # 登記分數並設為失效
    ct.current_mole["active"] = False   # 打中後地鼠失效 : 防止重複打擊
    ct.current_scores[username] = ct.current_scores.get(username, 0) + player_score

    # 更新個人排行榜最高分
    if ct.current_scores[username] > ct.leaderboard.get(username, 0):
        ct.leaderboard[username] = ct.current_scores[username]
        print(f"[GameServer] 更新 {username} 的最高分為 {ct.current_scores[username]}")

    # 廣播分數更新事件並通知前端顯示飛字提示
    await bc.broadcast({
        "event": "score_popup",
        "score": player_score,
        "mole_id": mole_id,
        "mole_name": ct.current_mole.get("mole_type", ""),
        "mole_color": ct.current_mole.get("color", (255, 255, 255))
    })

    # 廣播分數更新事件並通知前端分數顯示
    await bc.broadcast({
        "event": "score_update",  # 新的事件名稱
        "username": username,  # 玩家名稱
        "score": ct.current_scores[username]  # 更新後的分數
    })


    # 廣播目前地鼠狀態與遊戲狀態更新
    await bc.broadcast({"event": "mole_update", "mole": ct.current_mole})
    await asyncio.sleep(0.5)
    await bc.broadcast_status_update()

async def handle_special_hit(msg, username):
    parts = msg.split(":")
    mole_id = int(parts[1])
    player_score = int(parts[2])

    # 檢查是否是目前有效的特殊地鼠
    if ct.current_special_mole["mole_id"] == mole_id and ct.current_special_mole["active"]:
        print(f"[GameServer] 玩家 {username} 打中特殊地鼠 {mole_id}，分數 {player_score}")
        
        # 設置特殊地鼠為失效
        ct.current_special_mole["active"] = False

        # 更新玩家的分數
        ct.current_scores[username] = ct.current_scores.get(username, 0) + player_score

        # 更新玩家最高分
        if ct.current_scores[username] > ct.leaderboard.get(username, 0):
            ct.leaderboard[username] = ct.current_scores[username]
            print(f"[GameServer] 更新 {username} 的最高分為 {ct.current_scores[username]}")

        # 廣播分數更新事件並通知前端顯示飛字提示
        await bc.broadcast({
            "event": "score_popup",
            "score": player_score,
            "mole_id": mole_id,
            "mole_name": ct.current_mole.get("mole_type", ""),
            "mole_color": ct.current_mole.get("color", (255, 255, 255))
        })

        # 廣播分數更新事件並通知前端分數顯示
        await bc.broadcast({
            "event": "score_update",  # 新的事件名稱
            "username": username,  # 玩家名稱
            "score": ct.current_scores[username]  # 更新後的分數
        })

        # 更新特殊地鼠狀態
        await bc.broadcast({"event": "special_mole_update", "mole": ct.current_special_mole})
    else:
        print(f"[GameServer] 玩家 {username} 嘗試打不存在或已消失的特殊地鼠 {mole_id}")

async def handle_final_score(msg):
    parts = msg.split(":")
    final_user = parts[1]
    final_score = int(parts[2])
    print(f"[GameServer] 玩家 {final_user} 結束遊戲，最終分數 {final_score}")

    if final_score > ct.leaderboard.get(final_user, 0):
        ct.leaderboard[final_user] = final_score
        print(f"[GameServer] 更新 {final_user} 的最高分為 {final_score}")
