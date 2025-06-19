# broadcaster.py    :   給GameServer 玩家廣播  訊息
import asyncio
import json
import time
import math
import settings.context as ct

# 廣播任意訊息給所有玩家
async def broadcast(message_dict):
    msg = json.dumps(message_dict)
    tasks = []
    for player, ws in ct.player_websockets.items():
        tasks.append(_safe_send(player, ws, msg))
    await asyncio.gather(*tasks, return_exceptions=True)

# 單一玩家安全發送（失敗時記錄錯誤）
async def _safe_send(player, ws_conn, msg):
    try:
        await ws_conn.send(msg)
    except Exception as e:
        print(f"[Broadcast] 傳送給 {player} 失敗：{e}")
        # 可選：從連線池中移除壞掉的連線
        # ct.player_websockets.pop(player, None)

# 廣播 loading 狀態 : 進入 10 秒倒數階段時使用
async def broadcast_loading_status():
    status_msg = {
        "event": "status_update",
        "game_phase": "loading",
        "remaining_time": 0,
        "loading_time": ct.loading_time,
        "current_players": len(ct.connected_players),
        "leaderboard": [
            {"username": u, "score": s}
            for u, s in sorted(ct.current_scores.items(), key=lambda x: x[1], reverse=True)
        ]
    }
    await broadcast(status_msg)
    print("[Broadcast] 已送出 status_update：game_phase = loading")


# 排行榜廣播
async def broadcast_leaderboard():
    await broadcast({
        "event": "leaderboard_update",
        "leaderboard": [
            {"username": user, "score": score}
            for user, score in ct.current_scores.items()
        ]
    })

# #  廣播當前狀態 : 通用 status_update（所有階段都可使用
async def broadcast_status_update():
    now = time.time()

    if ct.game_phase == "loading" and ct.loading_start_time is not None:
        loading_time_left = max(0, math.ceil(10 - (now - ct.loading_start_time)))
    else:
        loading_time_left = 0

    if ct.game_phase == "playing" and ct.game_start_time is not None:
        remaining_game_time = max(0, ct.GAME_DURATION - int(now - ct.game_start_time))
    else:
        remaining_game_time = 0

    leaderboard_list = [
        {"username": u, "score": ct.current_scores.get(u, 0)}
        for u in ct.connected_players
    ]

    status_update = {
        "event": "status_update",
        "game_phase": ct.game_phase,
        "remaining_time": remaining_game_time,
        "loading_time": loading_time_left,
        "current_players": len(ct.connected_players),
        "leaderboard": sorted(leaderboard_list, key=lambda x: x["score"], reverse=True),
    }

    await broadcast(status_update)

