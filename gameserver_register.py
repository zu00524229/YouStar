import asyncio
import websockets
import json
import time

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
            current_players = 0
            in_game = False
            remaining_time = 0
            leaderboard = []

            while True:
                if in_game:
                    remaining_time -= 5
                    if remaining_time <= 0:
                        in_game = False
                        current_players = 0
                        leaderboard = [
                            {"username": "player1", "score": 55},
                            {"username": "player2", "score": 44},
                        ]
                else:
                    in_game = True
                    current_players = 1
                    remaining_time = 30
                    leaderboard = []

                status_update = {
                    "current_players": current_players,
                    "in_game": in_game,
                    "remaining_time": remaining_time,
                    "leaderboard": leaderboard
                }
                await websocket.send(json.dumps(status_update))
                print("[GameServer] 發送狀態更新", status_update)

                await websocket.send("ping")
                print("[GameServer] 發送 ping")

                await asyncio.sleep(5)

        except KeyboardInterrupt:
            print("GameServer 手動中斷連線")


if __name__ == "__main__":
    asyncio.run(register_to_control_server())
