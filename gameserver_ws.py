# GameServer 本體 

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import requests
import asyncio

app = FastAPI()

# 中控 Server 的 player_offline API
CONTROL_SERVER_URL = "http://127.0.0.1:8000/player_offline"

# 紀錄目前 GameServer 上線的玩家
connected_players = set()

@app.websocket("/ws")
async def player_ws(websocket: WebSocket):
    await websocket.accept()

    # 第一個訊息 → 玩家傳 username
    username = await websocket.receive_text()
    print(f"[GameServer] 玩家 {username} 連線進來")
    connected_players.add(username)

    try:
        while True:

            await websocket.send_text("地鼠出現!")
            print(f"[GameServer] 發送給玩家 {username}: 地鼠出現!")

            await asyncio.sleep(5)  # 等待五秒
            # 玩家傳來遊戲訊息
            msg = await websocket.receive_text()
            print(f"[GameServer] 收到玩家 {username} 訊息: {msg}")

            # 回傳給玩家（測試用）
            await websocket.send_text(f"收到你的訊息: {msg}")

    except WebSocketDisconnect:
        print(f"[GameServer] 玩家 {username} 離線")
        connected_players.discard(username)

        # 通知中控 Server → 玩家離線
        try:
            response = requests.post(CONTROL_SERVER_URL, json={"username": username})
            print(f"[GameServer] 通知中控 玩家 {username} 離線 → 回應: {response.json()}")
        except Exception as e:
            print(f"[GameServer] 通知中控失敗: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
