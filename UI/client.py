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
        self.server_list = []
        self.ws_conn = None         # 當前與 GameServer 保持連線 → 用來發 hit / 收事件
        
        # self.loop = asyncio.get_event_loop()
        self.ready_offer_remaining_time = 0        # 剩餘倒數時間（伺服器提供
        self.ready_offer_started = False           # 是否已進入 ready 倒數階段（避免重複點擊 Again）
        self.ready_offer_joined_players = set()    # 有點擊 Ready 的玩家名單（你可選擇顯示）
        self.ready_offer_total_players = 0

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
            }

    def get_server_list(self):
        try:
            server_list = []
            asyncio.run(self._get_server_list_async(server_list))
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

    async def ws_receiver_async(self):

        if not self.server_url:
            print("[前端] server_url 尚未設定，取消 WebSocket 連線")
            return

        try:
            async with websockets.connect(
                self.server_url,
                origin="http://localhost"
            ) as websocket_mole:
                self.ws_conn = websocket_mole
                print("[前端] WebSocket 連線 GameServer 成功")
                await websocket_mole.send(self.username)

                while True:
                    msg = await websocket_mole.recv()
                    try:
                        data = json.loads(msg)

                        # if data.get("event") == "status_update":
                        #     phase = data.get("game_phase")
                        #     if phase:
                        #         self.game_state = phase
                        #         print(f"[前端] 狀態更新 → game_state = {self.game_state}")

                        if data.get("event") == "mole_update":
                            print(f"[前端] 收到地鼠：{data['mole']}")
                            with self.state_lock:
                                if self.game_state == "playing":
                                    mole = data["mole"]
                                    self.current_mole_id = mole["mole_id"]              # 記下當前地鼠ID
                                    self.current_mole_position = mole["position"]       # 地鼠位置
                                    self.current_mole_type_name = mole["mole_type"]     # 地鼠類型名稱
                                    self.mole_active = mole["active"]                   # 是否有效             

                        elif data.get("event") == "special_mole_update":
                            print(f"[前端] 收到特殊地鼠：{data['mole']}")
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
                                                
                            try:
                                async with websockets.connect(ct.CONTROL_SERVER_WS) as ws_offline:
                                    await ws_offline.send(json.dumps({
                                        "type": "offline",
                                        "username": self.username
                                    }))
                                    # print(f"[前端] 已主動通知 ControlServer 玩家 {self.username} offline (排行榜出現)")
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
                            # print(f"[Client] 收到遊戲狀態: remaining_time = {self.remaining_time}")
                        
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

        except Exception as e:
            print(f"[前端] WebSocket 錯誤: {e}")

    def start_ws_receiver(self):
        if self.ws_started:
            print("[前端] ws_receiver 已啟動，略過重複啟動")
            return
        self.ws_started = True
        ct.ws_receiver_start_count += 1                 # 檢查連線
        print(f"[Debug] 第 {ct.ws_receiver_start_count} 次啟動 ws_receiver")
        # 用新的 loop 並保存下來
        self.async_loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_ws_loop, daemon=True).start()

    def _run_ws_loop(self):
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_until_complete(self.ws_receiver_async())


    # 檢查  GameServer
    async def connect_to_gameserver(self, server_url):
        if self.ws_conn and not self.ws_conn.closed:
            print("[debug] 已存在連線，略過連接 GameServer")
            return

        self.server_url = server_url
        self.ws_conn = await websockets.connect(server_url)
        print(f"[前端] 已連線至 GameServer: {server_url}")


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

    async def send_hit_async(self):
        try:
            await self.ws_conn.send(f"hit:{self.current_mole_id}:{self.score}")
            print(f"[前端] 發送 hit:{self.current_mole_id}:{self.score} 給 GameServer")
            print(f"[Debug] 傳送 hit 時間：{time.time():.2f}")
        except Exception as e:
            print(f"[前端] 發送 hit 時錯誤: {e}")


    async def send_special_hit_async(self):
        try:
            await self.ws_conn.send(f"special_hit:{self.current_special_mole_id}:{self.score}")
            print(f"[前端] 發送 special_hit:{self.current_special_mole_id}:{self.score} 給 GameServer")
            print(f"[Debug] 傳送 hit 時間：{time.time():.2f}")
        except Exception as e:
            print(f"[前端] 發送 special_hit 時錯誤: {e}")

    # 遊戲前端ready按鈕
    def send_ready(self):
        try:
            print("[Debug] client.send_ready() 被呼叫")
            asyncio.run(self.ws_conn.send("ready"))
            print(f"[前端] 發送 ready 給 GameServer")
        except:
            pass

    def send_join_ready(self):
        try:
            asyncio.run(self.ws_conn.send("join_ready"))
            print("[前端] 發送 join_ready 給 GameServer")
        except:
            pass

    def reset_ready_offer(self):
        with self.state_lock:
            self.ready_offer_started = False
            self.ready_offer_joined_players.clear()
            self.ready_offer_remaining_time = 0
            # print("[client] Reset ready offer state")

