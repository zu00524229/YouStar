# client.py
import asyncio
import websockets
import json
import threading
import time

CONTROL_SERVER_WS = "ws://127.0.0.1:8765"

class GameClient:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.assigned_server = None
        self.ws_conn = None
        self.loop = asyncio.get_event_loop()

        # 同步資料
        self.current_mole_id = -1
        self.current_mole_position = -1
        self.current_mole_type_name = ""
        self.mole_active = False

        self.game_state = "waiting"
        self.remaining_time = 10
        self.loading_time = 0
        self.score = 0
        self.leaderboard_data = []

        self.state_lock = threading.Lock()

    def start(self):
        threading.Thread(target=self._start_login, daemon=True).start()

    def _start_login(self):
        asyncio.run(self.login_to_control())

    async def login_to_control(self):
        try:
            async with websockets.connect(CONTROL_SERVER_WS) as ws:
                await ws.send(json.dumps({
                    "type": "login",
                    "username": self.username,
                    "password": self.password
                }))

                response = await ws.recv()
                data = json.loads(response)
                if data.get("type") == "login_response" and data.get("success"):
                    self.assigned_server = data["assigned_server"]
                    print(f"[前端] 登入成功，分配到 GameServer: {self.assigned_server}")

                    # 啟動 ws_receiver
                    threading.Thread(target=lambda: asyncio.run(self.ws_receiver_async()), daemon=True).start()

                else:
                    print(f"[前端] 登入失敗: {data.get('reason')}")
                    time.sleep(3)
                    await self.login_to_control()  # 重新 login retry

        except Exception as e:
            print(f"[前端] login_to_control 錯誤: {e}")
            time.sleep(3)
            await self.login_to_control()  # 重新 login retry

    async def ws_receiver_async(self):
        try:
            async with websockets.connect(
                self.assigned_server,
                origin="http://localhost"
            ) as websocket_mole:
                self.ws_conn = websocket_mole
                print("[前端] WebSocket 連線 GameServer 成功")
                await websocket_mole.send(self.username)

                while True:
                    msg = await websocket_mole.recv()
                    try:
                        data = json.loads(msg)

                        if data.get("event") == "mole_update":
                            with self.state_lock:
                                if self.game_state == "playing":
                                    mole = data["mole"]
                                    self.current_mole_id = mole["mole_id"]
                                    self.current_mole_position = mole["position"]
                                    self.current_mole_type_name = mole["mole_type"]
                                    self.mole_active = mole["active"]

                        elif data.get("event") == "leaderboard_update":
                            with self.state_lock:
                                self.leaderboard_data = data.get("leaderboard", [])
                                self.game_state = "gameover"

                            try:
                                async with websockets.connect(CONTROL_SERVER_WS) as ws_offline:
                                    await ws_offline.send(json.dumps({
                                        "type": "offline",
                                        "username": self.username
                                    }))
                                    print(f"[前端] 已主動通知 ControlServer 玩家 {self.username} offline (排行榜出現)")
                            except Exception as e:
                                print(f"[前端] 通知 ControlServer 玩家 {self.username} offline 失敗: {e}")

                        elif data.get("type") == "status_update":
                            with self.state_lock:
                                game_phase = data.get("game_phase", "waiting")
                                self.loading_time = data.get("loading_time", 0)
                                self.remaining_time = data.get("remaining_time", 0)

                                if game_phase == "waiting":
                                    if self.game_state != "gameover":
                                        self.game_state = "waiting"
                                elif game_phase == "loading":
                                    self.game_state = "loading"
                                elif game_phase == "ready":
                                    self.game_state = "ready"
                                elif game_phase == "playing":
                                    if self.game_state != "playing":
                                        print("[前端][Status WS] GameServer 已進入遊戲，開始 playing")
                                    self.game_state = "playing"
                                elif game_phase == "gameover":
                                    if self.game_state != "gameover":
                                        print("[前端][Status WS] GameServer 進入 gameover phase")
                                        self.game_state = "gameover"

                    except Exception as e:
                        print(f"[前端] 收到非 json 訊息: {msg}, error: {e}")

        except websockets.exceptions.ConnectionClosed:
            print("[前端] WebSocket 斷線")

        except Exception as e:
            print(f"[前端] WebSocket 錯誤: {e}")

    def send_hit(self):
        try:
            asyncio.run(self.ws_conn.send(f"hit:{self.current_mole_id}:{self.score}"))
            print(f"[前端] 發送 hit:{self.current_mole_id}:{self.score} 給 GameServer")
        except:
            pass
