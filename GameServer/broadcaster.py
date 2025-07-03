# broadcaster.py    :   給GameServer 玩家廣播  訊息
import asyncio
import json
import time
import math
import settings.context as ct
import UI.game_gameover_ui as gou


#  廣播當前狀態 : 通用 status_update（所有階段都可使用
async def broadcast_status_update():
    now = time.time()

    # 如果目前在 loading 階段 → 計算剩餘倒數時間（固定 10 秒
    if ct.game_phase == "loading" and ct.loading_start_time is not None:
        loading_time_left = max(0, math.ceil(10 - (now - ct.loading_start_time)))
    else:
        loading_time_left = 0

    # 如果目前在 playing 階段 → 計算遊戲剩餘時間
    if ct.game_phase == "playing" and ct.game_start_time is not None:
        remaining_game_time = max(0, ct.GAME_DURATION - int(now - ct.game_start_time))
    else:
        remaining_game_time = 0

    # 印出當前分數紀錄（ct.current_scores）
    # print("[Debug] 廣播狀態前 current_scores：", ct.current_scores)

    # 將 current_scores 字典轉成排行榜 list 結構
    leaderboard_list = [
        {"username": username, "score": score}
        for username, score in ct.current_scores.items()
    ]

    # 組裝 status_update 廣播資料包
    status_update = {
        "event": "status_update",                          # 事件名稱（前端判斷用）
        "game_phase": ct.game_phase,                       # 遊戲階段（waiting / loading / playing / gameover）
        "remaining_time": remaining_game_time,             # 遊戲剩餘秒數（只有在 playing 階段有效）
        "loading_time": loading_time_left,                 # loading 階段倒數秒數（其餘階段為 0）
        "current_players": len(ct.connected_players - ct.watch_players),   # 當前已連線玩家數
        "watching_players": len(ct.watch_players),         # 當前觀戰人數
        "leaderboard": sorted(                             # 排行榜（依分數高低排序）
            leaderboard_list,
            key=lambda x: x["score"],
            reverse=True
        ),
    }
    
    # 廣播給所有已連線玩家
    await broadcast(status_update)
    

# 廣播任意訊息給所有玩家
async def broadcast(message_dict):
    try:
        msg = json.dumps(message_dict)
    except Exception as e:
        print("[Broadcast] JSON 轉換錯誤！內容如下：")
        print(message_dict)
        print("錯誤詳情：", e)
        return  # 直接跳出，不發送壞訊息
    tasks = []
    for player, ws in ct.player_websockets.items():
        tasks.append(_safe_send(player, ws, msg))
    await asyncio.gather(*tasks, return_exceptions=True)    # 用gather 防阻塞

# 單一玩家安全發送（失敗時記錄錯誤）
async def _safe_send(player, ws_conn, msg):
    try:
        await ws_conn.send(msg)
    except Exception as e:
        print(f"[Broadcast] 傳送給 {player} 失敗：{e}")
        # 可選：從連線池中移除壞掉的連線
        # ct.player_websockets.pop(player, None)


# # 廣播 leaderboard（遊戲結束）
async def broadcast_final_leaderboard():
    import json
    
    # 將 leaderboard 轉換為列表格式
    leaderboard_result = [
        {"username": username, "score": score}
        for username, score in ct.leaderboard.items()
    ]
    leaderboard_result.sort(key=lambda x: x["score"], reverse=True)
    print(f"[Broadcast] 最終 leaderboard 廣播中：{leaderboard_result}")


# === 比對歷史最高分 ===
    if ct.current_scores:
        highest_player, highest_score = max(ct.current_scores.items(), key=lambda x: x[1])

        # 撈取歷史最高分
        old_leaderboard = gou.get_sorted_leaderboard_list_from_file()
        history_highest = old_leaderboard[0]["score"] if old_leaderboard else 0

        if highest_score > history_highest:
            print(f"[GameServer] 🎉 {highest_player} 創下歷史最高分 {highest_score}！通知中控")

            if ct.control_ws:
                try:
                    await ct.control_ws.send(json.dumps({
                        "type": "highlight",
                        "message": f"NICE!! {highest_player} 破紀錄！拿下 {highest_score} 分！"
                    }))
                    print("[GameServer] highlight 已送出")
                except Exception as e:
                    print(f"[GameServer] 傳送 highlight 失敗：{e}")
            else:
                print("[GameServer] ❗ control_ws 尚未建立，無法傳送 highlight")

    ct.leaderboard = {entry["username"]: entry["score"] for entry in leaderboard_result}
    ct.save_leaderboard()     # 排行榜更新(儲存)
    
