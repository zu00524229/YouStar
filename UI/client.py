# client.py 前端(遊戲)
import asyncio
import websockets
import json
import threading
import time
import settings.context as ct


class GameClient:
    def __init__(self, username, password):
        self.username = username    # 玩家帳號名稱
        self.password = password    # 玩家密碼
        # self.assigned_server = None 
        self.server_url = None      # 分配到的 GameServer WebSocket URL
        self.ws_receiver_started = False
        self.server_list = []
        self.ws_conn = None         # 當前與 GameServer 保持連線 → 用來發 hit / 收事件
        
        self.ready_offer_remaining_time = 0        # 剩餘倒數時間（伺服器提供
        self.ready_offer_started = False           # 是否已進入 ready 倒數階段（避免重複點擊 Again）
        self.ready_offer_joined_players = set()    # 有點擊 Ready 的玩家名單（你可選擇顯示）
        self.ready_offer_total_players = 0

        self.current_mole_duration = 1.2  # 或你預設的值
        self.current_mole_spawn_time = 0

        # 玩家選擇再玩 / 觀戰 / 回大廳的意圖
        self.ready_mode = None

        self.ws_started = False
        # self.offline_sent = False  # 防止重複通知 offline

        # 狀態 flag
        self.login_success = False   # 新增：是否已登入成功

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

        self.async_loop = asyncio.get_event_loop()

        # 遊戲整體狀態
        self.game_state = "waiting"
        self.remaining_time = 10
        self.loading_time = 0
        self.score = 0
        self.current_players = 0

        # 排行榜資料
        self.leaderboard_data = []
        self.state_lock = threading.Lock()

    # 畫面邏輯
    def sync_game_state(self):
        with self.state_lock:
            return {
                "current_players": self.current_players,
                "game_state": self.game_state,
                "remaining_time": self.remaining_time,
                "loading_time": self.loading_time,
                "current_mole_id": self.current_mole_id,
                "current_mole_position": self.current_mole_position,
                "current_mole_type_name": self.current_mole_type_name,
                "mole_active": self.mole_active,
                "current_special_mole_position": self.current_special_mole_position,
                "current_special_mole_type_name": self.current_special_mole_type_name,
                "special_mole_active": self.special_mole_active,
                "leaderboard_data": self.leaderboard_data,
                "score": self.score,
                "ready_offer_remaining_time": self.ready_offer_remaining_time,
                "ready_offer_joined_players": self.ready_offer_joined_players,
                "ready_offer_total_players": self.ready_offer_total_players,
                "current_mole_duration": self.current_mole_duration,
                "current_mole_spawn_time": self.current_mole_spawn_time,
                "current_mole_score": self.current_mole_score,
                "current_special_mole_score": getattr(self, "current_special_mole_score", 0),
            }

    async def get_server_list(self):
        try:
            server_list = []
            await self._get_server_list_async(server_list)
            return server_list
        except Exception as e:
            print(f"[前端] get_server_list 錯誤: {e}")
            return []


    async def _get_server_list_async(self, server_list):
        async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
            await ws.send(json.dumps({
                "type": "get_server_list"
            }))
            response = await ws.recv()
            data = json.loads(response)

            if data.get("type") == "get_server_list_response":
                server_list.extend(data.get("server_list", []))

    # 
    async def ws_receiver_async(self):
        try:
            # 先建立連線
            websocket_mole = await websockets.connect(
                self.server_url,
                origin="http://localhost"
            )
            self.ws_conn = websocket_mole
            print(f"[前端] ws_receiver 啟動中，使用連線 ID: {id(websocket_mole)}")
            print("[前端] WebSocket 連線 GameServer 成功")

            # 傳送登入資訊
            await websocket_mole.send(self.username)

            # 開始接收訊息
            async for msg in websocket_mole:
                try:
                    data = json.loads(msg)

                    # ========== mole_update ==========
                    if data.get("event") == "mole_update":
                        print(f"[前端] 收到地鼠：{data['mole']}")
                        with self.state_lock:
                            if self.game_state == "playing":
                                mole = data["mole"]
                                if mole["mole_id"] != self.current_mole_id:
                                    print(f"[前端] 新地鼠 ID: {mole['mole_id']} → 前一隻為 {self.current_mole_id}")
                                    self.mole_active = False
                                self.current_mole_id = mole["mole_id"]
                                self.current_mole_position = mole["position"]
                                self.current_mole_type_name = mole["mole_type"]
                                self.current_mole_score = mole.get("score", 0)
                                self.mole_active = mole["active"]
                                self.current_mole_duration = mole.get("duration", 1.2)
                                self.current_mole_spawn_time = mole.get("spawn_time", time.time())

                    # ========== special_mole_update ==========
                    elif data.get("event") == "special_mole_update":
                        print(f"[前端] 收到特殊地鼠：{data['mole']}")
                        with self.state_lock:
                            if self.game_state == "playing":
                                mole = data["mole"]
                                if mole["mole_id"] != self.current_special_mole_id:
                                    self.special_mole_active = False
                                self.current_special_mole_id = mole["mole_id"]
                                self.current_special_mole_position = mole["position"]
                                self.current_special_mole_type_name = mole["mole_type"]
                                self.current_special_mole_score = mole.get("score", 0)
                                self.special_mole_active = mole["active"]

                    # ========== leaderboard_update ==========
                    elif data.get("event") == "leaderboard_update":
                        with self.state_lock:
                            self.final_leaderboard_data = data.get("leaderboard", [])
                        try:
                            async with websockets.connect(ct.CONTROL_SERVER_WS) as ws_offline:
                                await ws_offline.send(json.dumps({
                                    "type": "offline",
                                    "username": self.username
                                }))
                        except Exception as e:
                            print(f"[前端] 通知 ControlServer 玩家 {self.username} offline 失敗: {e}")

                    # ========== status_update ==========
                    elif data.get("event") == "status_update":
                        game_phase = data.get("game_phase", "waiting")
                        with self.state_lock:
                            self.loading_time = data.get("loading_time", 0)
                            self.remaining_time = data.get("remaining_time", 0)
                            self.current_players = data.get("current_players", 0)
                            self.leaderboard = data.get("leaderboard", [])
                            if self.leaderboard:
                                self.leaderboard_data = self.leaderboard
                                print("[前端] 接收到即時 leaderboard 資料：", self.leaderboard)
                            self.game_state = game_phase

                            if game_phase == "playing":
                                print("[前端][Status WS] GameServer 已進入遊戲，開始 playing")
                            elif game_phase == "gameover":
                                print("[前端][Status WS] GameServer 進入 gameover phase")
                            elif game_phase == "waiting":
                                print("[前端][Status WS] GameServer 等待中，進入 waiting")
                            elif game_phase == "loading":
                                print("[前端][Status WS] GameServer 進入 loading")

                    # ========== ready_offer_update ==========
                    elif data.get("event") == "ready_offer_update":
                        remaining_time = data.get("remaining_time", 0)
                        joined_usernames = data.get("joined_usernames", [])
                        total_players = data.get("total_players", 0)
                        with self.state_lock:
                            self.ready_offer_remaining_time = remaining_time
                            self.ready_offer_joined_players = set(joined_usernames)
                            self.ready_offer_total_players = total_players
                            self.ready_offer_started = True
                        print(f"[前端] ready Offer 倒數 {remaining_time}s，已加入：{joined_usernames} / 全部：{total_players}")

                    elif data.get("event") == "ready_end":
                        with self.state_lock:
                            self.ready_offer_started = False
                            self.ready_offer_remaining_time = 0
                            self.ready_offer_joined_players.clear()
                        print("[前端] 收到 ready_end，重置 ready 狀態")

                except Exception as e:
                    print(f"[前端] 收到非 json 訊息: {msg}, error: {e}")

        except websockets.exceptions.ConnectionClosed:
            print("[前端] WebSocket 斷線")
            self.ws_conn = None
            self.ws_started = False  # 讓系統可以重啟 ws_receiver

        except Exception as e:
            print(f"[前端] WebSocket 錯誤: {e}")
            self.ws_conn = None
            self.ws_started = False

    async def connect_to_server(self):
        if not self.server_url:
            print("[前端] server_url 尚未設定，無法連線 GameServer")
            return

        try:
            self.ws_conn = await websockets.connect(self.server_url)
            print(f"[前端] 成功連線 GameServer：{self.server_url}")
            await self.ws_conn.send(self.username)
            asyncio.create_task(self.ws_receiver_async())  # 啟動接收 loop
        except Exception as e:
            print(f"[前端] 連線 GameServer 失敗: {e}")

    # lobby 大廳伺服器判斷
    async def start_ws_receiver(self):
        if self.ws_started:
            print("[前端] ws_receiver 已啟動，略過重複啟動")
            return
        self.ws_started = True
        ct.ws_receiver_start_count += 1
        print(f"[Debug] 第 {ct.ws_receiver_start_count} 次啟動 ws_receiver")

        # 背景執行 ws_receiver，包含自動重連邏輯
        asyncio.create_task(self.ws_receiver_with_reconnect())


    def quick_login_check(self):
        try:
            async def _check():
                async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
                    await ws.send(json.dumps({
                        "type": "login",
                        "username": self.username,
                        "password": self.password
                    }))
                    response = await ws.recv()
                    data = json.loads(response)
                    return data.get("type") == "login_response" and data.get("success")

            return asyncio.run(_check())
        except:
            return False

    # 傳送一般地鼠打擊事件
    async def send_hit(self, mole_id, score):
        if self.ws_conn and not self.ws_conn.closed:
            msg = f"hit:{mole_id}:{score}"
            try:
                await self.ws_conn.send(msg)
                print(f"[前端] 已送出 hit：{msg}")
            except Exception as e:
                print(f"[前端] 發送 hit 失敗: {e}")
        else:
            print("[前端] ws_conn 無效或已關閉，無法發送 hit")

    # 傳送特殊地鼠打擊事件
    async def send_special_hit(self, mole_id, score):
        if self.ws_conn and not self.ws_conn.closed:
            msg = f"special_hit:{mole_id}:{score}"
            try:
                await self.ws_conn.send(msg)
                print(f"[前端] 已送出 special_hit：{msg}")
            except Exception as e:
                print(f"[前端] 發送 special_hit 失敗: {e}")
        else:
            print("[前端] ws_conn 無效或已關閉，無法發送 special_hit")

    def send_ready(self):
        async def _send():
            try:
                msg = "ready"
                print(f"[Debug] client.send_ready()：嘗試送出訊息 {msg}")
                await self.ws_conn.send(msg)
                print(f"[Debug] client.send_ready()：已送出訊息 {msg}")
            except Exception as e:
                print(f"[Debug] client.send_ready() 發送錯誤：{e}")

        threading.Thread(target=lambda: asyncio.run(_send()), daemon=True).start()

        # 用 thread 強制啟動 coroutine
        # def run_async():
        #     asyncio.run(_send())

        # threading.Thread(target=run_async).start()


    # 自動重連包裝器
    async def ws_receiver_with_reconnect(self):
        max_retries = 5  # 最多重連次數
        retry_delay = 3  # 每次等待秒數
        retry_count = 0

        while retry_count < max_retries:
            try:
                await self.ws_receiver_async()
                print("[前端] ws_receiver 結束（通常是斷線）")
                break  # 若正常退出就不重連
            except Exception as e:
                print(f"[前端] 接收器錯誤（第 {retry_count+1} 次）：{e}")
                self.ws_conn = None
                self.ws_started = False
                retry_count += 1
                await asyncio.sleep(retry_delay)

        if retry_count >= max_retries:
            print("[前端] 接收器多次失敗，放棄重連")
