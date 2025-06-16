# 給GameServer 玩家廣播 Ready 訊息
import json
import settings.context as ct

async def broadcast(message_dict):
    msg = json.dumps(message_dict)
    for player, ws_conn in ct.player_websockets.items():
        try:
            await ws_conn.send(msg)
        except:
            print(f"[GameServer] 傳送給玩家 {player} 失敗")
