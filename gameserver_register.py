import asyncio
import websockets
import json
# import time

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
                    remaining_time = 6
                    leaderboard = []

                status_update = {
                    "current_players": current_players,     # 目前玩家人數
                    "in_game": in_game,                     # True 正在遊戲中 / False 遊戲尚未開始
                    "remaining_time": remaining_time,       # 剩餘時間
                    "leaderboard": leaderboard              # '用戶名': '玩家1', '分數': 55
                }
                await websocket.send(json.dumps(status_update))
                print("[GameServer] 發送狀態更新", status_update)

                await websocket.send("ping")
                print("[GameServer] 發送 ping")

                await asyncio.sleep(5)

        except websockets.exceptions.ConnectionClosedError as e:
            print(f"⚠️ WebSocket 斷線 (code {e.code}): {e.reason}，3 秒後重試...")
            await asyncio.sleep(3)

        except ConnectionRefusedError:
            print(f"❌ 無法連線到 {REGISTER_URL}，3 秒後重試...")
            await asyncio.sleep(3)

        except Exception as e:
            print(f"❌ 發生錯誤：{e}，3 秒後重試...")
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(register_to_control_server())
