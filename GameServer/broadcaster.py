# broadcaster.py    :   給GameServer 玩家廣播  訊息
import asyncio
import json
import settings.context as ct

async def broadcast(message_dict):
    msg = json.dumps(message_dict)
    tasks = []
    for player, ws in ct.player_websockets.items():
        tasks.append(_safe_send(player, ws, msg))
    await asyncio.gather(*tasks, return_exceptions=True)

async def _safe_send(player, ws_conn, msg):
    try:
        await ws_conn.send(msg)
    except Exception as e:
        print(f"[Broadcast] 傳送給 {player} 失敗：{e}")
        # 可選：從連線池中移除壞掉的連線
        # ct.player_websockets.pop(player, None)

# 排行榜廣播
async def broadcast_leaderboard():
    await broadcast({
        "event": "leaderboard_update",
        "leaderboard": [
            {"username": user, "score": score}
            for user, score in ct.current_scores.items()
        ]
    })