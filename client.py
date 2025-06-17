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
        self.assigned_server = None # 分配到的 GameServer WebSocket URL
        self.ws_conn = None         # 當前與 GameServer 保持連線 → 用來發 hit / 收事件
        self.loop = asyncio.get_event_loop()
        self.replay_offer_remaining_time = 0
        self.replay_offer_joined_players = 0
        self.replay_offer_total_players = 0

        # 狀態 flag
        self.login_success = False   # ⭐ 新增：是否已登入成功 → 等待用

        # 地鼠同步資料
        self.current_mole_id = -1
        self.current_mole_position = -1
        self.current_mole_type_name = ""
        self.mole_active = False

        # 特殊地鼠同步資料
        self.current_special_mole_id = -1
        self.current_special_mole_position = -1
        self.current_special_mole_type_name = ""
        self.special_mole_active = False

        # 遊戲整體狀態
        self.game_state = "waiting"
        self.remaining_time = 10
        self.loading_time = 0
        self.score = 0
        self.current_players = 0

        # 排行榜資料
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
                    print(f"[前端] 登入成功，準備取得 GameServer 列表")

                    # ⭐⭐⭐ 登入成功 → 設 login_success = True ⭐⭐⭐
                    self.login_success = True

                    # call get_server_list
                    await ws.send(json.dumps({
                        "type": "get_server_list"
                    }))

                    response = await ws.recv()
                    data = json.loads(response)

                    if data.get("type") == "get_server_list_response":
                        server_list = data.get("server_list", [])
                        print(f"[前端] 取得 GameServer 列表，共 {len(server_list)} 台：")
                        for i, server in enumerate(server_list):
                            print(f"  [{i}] {server['server_url']} | players: {server['current_players']}/{server['max_players']} | phase: {server['game_phase']}")

                else:
                    print(f"[前端] 登入失敗: {data.get('reason')}")
                    time.sleep(3)
                    await self.login_to_control()

        except Exception as e:
            if "received 1000" in str(e):
                print(f"[前端] login_to_control 正常結束 (code 1000)，不 retry")
            else:
                print(f"[前端] login_to_control 錯誤: {e}")
                time.sleep(3)
                await self.login_to_control()

    def get_server_list(self):
        try:
            server_list = []
            asyncio.run(self._get_server_list_async(server_list))
            return server_list
        except Exception as e:
            print(f"[前端] get_server_list 錯誤: {e}")
            return []

    async def _get_server_list_async(self, server_list):
        async with websockets.connect(CONTROL_SERVER_WS) as ws:
            await ws.send(json.dumps({
                "type": "get_server_list"
            }))
            response = await ws.recv()
            data = json.loads(response)

            if data.get("type") == "get_server_list_response":
                server_list.extend(data.get("server_list", []))

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

                        elif data.get("event") == "special_mole_update":
                            with self.state_lock:
                                if self.game_state == "playing":
                                    mole = data["mole"]
                                    self.current_special_mole_id = mole["mole_id"]
                                    self.current_special_mole_position = mole["position"]
                                    self.current_special_mole_type_name = mole["mole_type"]
                                    self.special_mole_active = mole["active"]

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
                                self.current_players = data.get("current_players", 0)

                                if self.game_state != "gameover":
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

                        elif data.get("event") == "replay_offer_update":
                            remaining_time = data.get("remaining_time", 0)
                            with self.state_lock:
                                self.replay_offer_remaining_time = remaining_time
                            print(f"[前端] 收到 Replay Offer 倒數 {remaining_time} 秒")


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

    def send_special_hit(self):
        try:
            asyncio.run(self.ws_conn.send(f"special_hit:{self.current_special_mole_id}:{self.score}"))
            print(f"[前端] 發送 special_hit:{self.current_special_mole_id}:{self.score} 給 GameServer")
        except:
            pass

    # 遊戲前端Replay按鈕
    def send_replay(self):
        try:
            asyncio.run(self.ws_conn.send("replay"))
            print(f"[前端] 發送 replay 給 GameServer")
        except:
            pass

    def send_join_replay(self):
        try:
            asyncio.run(self.ws_conn.send("join_replay"))
            print("[前端] 發送 join_replay 給 GameServer")
        except:
            pass

