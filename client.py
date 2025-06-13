# client.py
import asyncio
import websockets
import json
import threading
import time

CONTROL_SERVER_WS = "ws://127.0.0.1:8765"

class GameClient:
    def __init__(self, username, password):
        self.username = username    # 玩家帳號名稱
        self.password = password    # 玩家密碼
        # 分配到的 GameServer URL
        self.assigned_server = None # 當前分配到的 GameServer WebSocket URL（登入成功後才會有值）
        # 與 GameServer 的 WebSocket 連線物件
        self.ws_conn = None         # 當前與 GameServer 保持的 WebSocket 連線 → 用來發 hit / 收事件
        # 目前 asyncio 事件迴圈（主執行緒內）
        self.loop = asyncio.get_event_loop()

        # 地鼠同步資料（由 server 廣播 mole_update 更新）
        self.current_mole_id = -1               # 當前地鼠的 mole_id（唯一識別碼）
        self.current_mole_position = -1         # 地鼠目前出現在哪一格（對應 grid_positions index）
        self.current_mole_type_name = ""        # 地鼠類型名稱（普通地鼠 / 黃金地鼠 / ...）
        self.mole_active = False                # 地鼠是否還有效可打（True:可以打，False:已被打中或消失）

        # 遊戲整體狀態
        self.game_state = "waiting"             # 玩家當前遊戲狀態 → waiting / loading / ready / playing / gameover
        self.remaining_time = 10                # 遊戲剩餘秒數（GameServer 會持續更新）
        self.loading_time = 0                   # loading 倒數剩餘秒數（GameServer 會持續更新）
        self.score = 0                          # 玩家目前累積分數（本地紀錄，打中地鼠時手動累加）

        # 排行榜資料（收到 leaderboard_update 後更新）
        self.leaderboard_data = []              # 排行榜資料 → list of {"username": ..., "score": ...}

        # 狀態鎖 → 避免多執行緒/非同步操作時，資料讀寫互撞
        self.state_lock = threading.Lock()      # 讀寫上面這些狀態變數時，加鎖保護 → 確保資料一致性

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
                                self.leaderboard_data = data.get("leaderboard", [])


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
