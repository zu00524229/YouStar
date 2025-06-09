import asyncio
import websockets

# 中控 Server 的 WebSocket 註冊網址
REGISTER_URL = "ws://127.0.0.1:8000/register_gameserver"

# 這個 GameServer 提供給玩家的 ws 地址（模擬）
MY_GAME_SERVER_WS = "ws://localhost:8001/ws"

async def register_to_control_server():
    async with websockets.connect(REGISTER_URL) as websocket:
        print(f"連線到中控 Server，註冊自己...")
        await websocket.send(MY_GAME_SERVER_WS)
        print(f"已送出 GameServer 位址: {MY_GAME_SERVER_WS}")

        # 模擬 GameServer 一直保持連線
        try:
            while True:
                await websocket.send("ping")
                await asyncio.sleep(10)
        except KeyboardInterrupt:
            print("GameServer 手動中斷連線")

if __name__ == "__main__":
    asyncio.run(register_to_control_server())
