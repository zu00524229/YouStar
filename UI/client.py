# client.py 前端(遊戲)
import asyncio
import websockets
import json
import threading
import time
import settings.context as ct
import settings.game_settings as gs
import settings.animation as ani


class GameClient:
    def __init__(self, username, password, loop):
        if not loop:
            raise ValueError("GameClient 建立時必須提供 asyncio event loop！")
        self.loop = loop
        # self.async_loop = loop
        self.highlight_message = ""       # 最新 highlight 訊息字串
        self.highlight_time = 0           # 收到訊息的時間戳（用於顯示幾秒後清除）


        self.username = username    # 玩家帳號名稱
        self.password = password    # 玩家密碼
        # print(f"[Debug] 建立 GameClient 實體 ID: {id(self)}，帳號: {self.username}") # 要放後面 不然會error
        self.server_url = None      # 分配到的 GameServer WebSocket URL
        self.server_list = []
        self.ws_conn = None         # 當前與 GameServer 保持連線 → 用來發 hit / 收事件
        
        self.ready_offer_remaining_time = 0      # 剩餘倒數時間（伺服器提供
        self.ready_offer_started = False           # 是否已進入 ready 倒數階段（避免重複點擊 Again）
        self.ready_offer_joined_players = set()    # 有點擊 Ready 的玩家名單（你可選擇顯示）
        self.ready_offer_total_players = 0


        # 觀戰模式
        self.is_watching = False

        # self.ws_receiver_started = False
        self.ws_started = False         

        # 狀態 flag
        self.login_success = False   # 新增：是否已登入成功

        # 地鼠同步資料
        self.current_mole_id = -1
        self.current_mole_position = -1
        self.current_mole_type_name = ""
        self.mole_active = False
        self.current_mole_score = 0
        self.current_mole_spawn_time = 0
        self.current_mole_duration = 1.2  # 

        # 特殊地鼠同步資料
        self.current_special_mole_id = -1
        self.current_special_mole_position = -1
        self.current_special_mole_type_name = ""
        self.special_mole_active = False
        self.current_special_mole_score = 0
        self.current_special_mole_duration = 3
        self.current_special_mole_spawn_time = 0
        

        # 遊戲整體狀態
        self.game_state = "waiting"
        self.remaining_time = 10        # 遊戲剩餘時間
        self.loading_time = 0           # 遊戲等待時間
        self.score = 0                  # 遊戲分數
        self.current_players = 0        # 當前伺服器人數
        self.watching_players = 0       # 當前觀戰人數
        self.hit_effects = []           # 打擊動畫
        self.again_timer = 0            # again 倒數秒數預設為0
        self.final_sent = False
        self.highlight_message = ""
        self.highlight_timer = 0


        # 排行榜資料
        self.leaderboard_data = []      # 當局排行榜
        self.state_lock = threading.Lock()

    # 回傳前端畫面需要同步的遊戲狀態（顯示地鼠、分數、倒數時間等）
    def sync_game_state(self):
        with self.state_lock:
            return {
                "highlight_message": self.highlight_message,          # 最新 highlight 訊息字串
                "highlight_time":self.highlight_time,                 # 收到訊息的時間戳（用於顯示幾秒後清除
                "current_players": self.current_players,              # 當前伺服器人數
                "watching_players": self.watching_players,            # 當前觀戰人數
                "game_state": self.game_state,                        # 遊戲狀態（waiting / loading / playing / gameover 等）
                "remaining_time": self.remaining_time,                # 遊戲剩餘時間（playing 階段）
                "loading_time": self.loading_time,                    # 等待倒數時間（loading 階段）
                "leaderboard_data": self.leaderboard_data,            # 排行榜資料（遊戲結束後顯示）
                "hit_effects": self.hit_effects,                      # 初始化打擊動畫效果
                "ready_offer_remaining_time": self.ready_offer_remaining_time,      # 剩餘倒數時間（伺服器提供

                # 一般地鼠資料
                "current_mole_id": self.current_mole_id,              # 地鼠唯一 ID，用於避免重複得分
                "current_mole_position": self.current_mole_position,  # 地鼠位置（0~11）
                "current_mole_type_name": self.current_mole_type_name,# 地鼠種類名稱（對應顏色與分數）
                "current_mole_score": self.current_mole_score,        # 該地鼠被打中時的得分
                "mole_active": self.mole_active,                      # 地鼠是否還有效（是否能得分）
                "current_mole_duration": self.current_mole_duration,        # 地鼠出現的持續時間
                "current_mole_spawn_time": self.current_mole_spawn_time,    # 地鼠出現時間戳，用於同步飛字消失時間

                # 特殊地鼠資料（例如：鑽石地鼠）
                "current_special_mole_id": self.current_special_mole_id,               # 特殊地鼠id
                "current_special_mole_position": self.current_special_mole_position,   # 特殊地鼠位置
                "current_special_mole_type_name": self.current_special_mole_type_name, # 特殊地鼠名稱
                "current_special_mole_score": self.current_special_mole_score,         # 特殊地鼠分數
                "special_mole_active": self.special_mole_active,                       # 特殊地鼠是否有效
                "current_special_mole_spawn_time": self.current_special_mole_spawn_time,
                "current_special_mole_duration": self.current_special_mole_duration,

                "score": self.score,                                   # 玩家當前分數（僅給自己看用）

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

    # 建立 GameServer 的 WebSocket 連線 + 啟動接收機制任務 (watch)
    async def connect_to_server(self):
        if not self.server_url:
            print("[前端] server_url 尚未設定，無法連線 GameServer")
            return

        try:
            # === 若已有連線，先安全關閉 ===
            if self.ws_conn and not self.ws_conn.closed:
                print("[前端] 發現已有舊 ws_conn → 嘗試關閉")
                await self.ws_conn.close()
                self.ws_conn = None
                self.ws_started = False

            # 建立 websockets 連線至 GameServer 
            self.ws_conn = await websockets.connect(self.server_url)
            print(f"[前端] 成功連線 GameServer：{self.server_url}")
                        
            # === 發送觀戰或玩家登入訊息 ===
            if self.ws_conn:
                if self.is_watching:
                    await self.ws_conn.send("watch")
                    print("[client.py] 發送 watch 給 GameServer")
                else:
                    await self.ws_conn.send(str(self.username))
                    print("[client.py] 發送 username 給 GameServer")


            # 負責監聽後端所有訊息（地鼠、狀態更新、排行等）
            asyncio.create_task(self.ws_receiver_async())  # 啟動接收 loo (用 create_task() 跑背景）
            self.ws_started = True

        except Exception as e:
            print(f"[前端] 連線 GameServer 失敗: {e}")

    # 接收 GameServer 廣播來的訊息 (背景持續接收地鼠、排行榜與遊戲狀態更新，用於及時同步畫面)
    async def ws_receiver_async(self):
        try:
            websocket_mole = self.ws_conn  # 使用現有連線，不再重新連線

            print(f"[前端] ws_receiver 啟動中，使用連線 web ID: {id(websocket_mole)}")
            print("[前端] WebSocket 連線 GameServer 成功")


            # 接收 GameServer 發來的訊息
            async for msg in websocket_mole:
                try:
                    data = json.loads(msg)

                    # ----------  地鼠事件 ----------
                    if data.get("event") == "mole_update":
                        # print(f"[前端] 收到地鼠：{data['mole']}")
                        with self.state_lock:
                            if self.game_state == "playing":
                                mole = data["mole"]
                                # 若新地鼠 ID 與目前地鼠不同，將舊地鼠設為失效
                                if mole["mole_id"] != self.current_mole_id:
                                    # print(f"[前端] 新地鼠 ID: {mole['mole_id']} → 前一隻為 {self.current_mole_id}")
                                    self.mole_active = False    # 停止前一隻顯示
                                # 更新當前地鼠資訊
                                self.current_mole_id = mole["mole_id"]
                                self.current_mole_position = mole["position"]
                                self.current_mole_type_name = mole["mole_type"]
                                self.current_mole_score = mole.get("score", 0)          # 地鼠本身價值(分數)
                                self.mole_active = mole["active"]
                                self.current_mole_duration = mole.get("duration", 1.2)
                                self.current_mole_spawn_time = mole.get("spawn_time", time.time())

                                # 如果地鼠被標記為失效，將其從畫面中隱藏
                                if not mole["active"]:
                                    self.mole_active = False
         
                    # ----------  特殊地鼠事件 ----------
                    elif data.get("event") == "special_mole_update":
                        print(f"[前端] 收到特殊地鼠：{data['mole']}")
                        with self.state_lock:
                            if self.game_state == "playing":
                                mole = data["mole"]
                                if mole["mole_id"] != self.current_special_mole_id:
                                    self.special_mole_active = False    # 停止上一隻特殊地鼠
                                # 更新特殊地鼠資訊
                                self.current_special_mole_id = mole["mole_id"]
                                self.current_special_mole_position = mole["position"]
                                self.current_special_mole_type_name = mole["mole_type"]
                                self.current_special_mole_score = mole.get("score", 0)  # 地鼠本身價值(分數)
                                self.special_mole_active = mole["active"]
                                self.current_special_mole_duration = mole.get("duration", 3)
                                self.current_special_mole_spawn_time = mole.get("spawn_time", time.time())

                    # ---------- 自己的分數更新 ---------
                    elif data.get("event") == "score_update":
                        score_username = data.get("username")
                        score = data.get("score", 0)
                        if score_username == self.username:
                            self.score = score  # 更新自己的分數
                            print(f"[前端] 自己分數更新：{score}")

                    # ---------- 分數飛字提示 ----------
                    elif data.get("event") == "score_popup":
                        # print("[前端] 收到 score_popup 飛字事件！")
                        score = data.get("score", 0)
                        mole_id = data.get("mole_id")
                        mole_name = data.get("mole_name", "Mole")
                        hit_user = data.get("username")
                        if hit_user == self.username:   # 只顯示個人
                            # print(f"[前端] 飛字提示：{mole_name} +{score}")
                            self.show_score_popup(score, mole_id, mole_name)

                    # ----------  (當局)最終排行榜 ----------
                    elif data.get("event") == "final_leaderboard":
                        print("[前端] 收到最終排行榜資料")
                        with self.state_lock:
                            self.leaderboard_data = data.get("leaderboard", [])

                    # -------- again 按鈕 --------
                    elif data.get("event") == "again_timer":
                        self.again_timer = data.get("remaining_time", 0)
                        print(f"[Client] 接收到 again 倒數 : {self.again_timer} 秒")

                    elif data.get("type") == "highlight":
                        self.highlight_message = data["message"]
                        self.highlight_time = time.time()
                        print(f"[Client] 收到 highlight：{self.highlight_message}")
                
                    
                    # ----------  遊戲狀態更新（最常收到 ----------
                    elif data.get("event") == "status_update":
                        # print(f"[前端] 收到 status_update：{data}")
                        game_phase = data.get("game_phase", "waiting")
                        # print(f"[前端] 接收到 status_update, game_phase = {game_phase}")
                        with self.state_lock:
                            self.loading_time = data.get("loading_time", 0)
                            self.remaining_time = data.get("remaining_time", 0)
                            self.current_players = data.get("current_players", 0)
                            self.watching_players = data.get("watching_players", 0)     # 觀戰
                            self.leaderboard = data.get("leaderboard", [])

                            # 若狀態從非 playing ➜ playing，要清空飛字殘留
                            if self.game_state != "playing" and game_phase == "playing":
                                print("[Client] 狀態切換為 playing，清空 score_popups")
                                gs.score_popups.clear() # 清除上局飛字殘留
                                # print("[Client] 狀態切換為 playing，清空 score")
                                self.score = 0   # 清除分數

                            # 更新即時排行榜資料
                            # if self.leaderboard:
                            self.leaderboard_data = self.leaderboard
                                # print("[前端] 接收到即時 leaderboard 資料：", self.leaderboard)
                            
                            # 更新 client 狀態（會影響畫面顯示）    
                            self.game_state = game_phase
                            # print(f"[前端] 更新 client.game_state = {self.game_state}")

                except Exception as e:
                    print(f"[前端] 收到非 json 訊息: {msg}, error: {e}")

        # ---------- 連線錯誤與斷線處理 ----------
        except websockets.exceptions.ConnectionClosed:
            print("[前端] WebSocket 斷線，考慮觸發自動重連？")
            self.ws_conn = None
            self.ws_started = False  # 讓系統可以重啟 ws_receiver
            if self.ws_conn:
                try:
                    asyncio.create_task(self.ws_conn.send(f"logout:{self.username}"))
                    print(f"[前端] 通知 GameServer 玩家 {self.username} 已斷線")
                except Exception as e:
                    print(f"[前端] 通知斷線時失敗：{e}")
        except Exception as e:
            print(f"[前端] WebSocket 錯誤: {e}")
            self.ws_conn = None
            self.ws_started = False


    # 啟動接收 GameServer 訊息監聽
    # 檢查是否已啟動 ws_receiver，避免重複啟動
    async def start_ws_receiver(self):
        # 確保 server_url 格式正確（前面已透過大廳點擊設定）
        assert isinstance(self.server_url, str), "server_url 應為字串！"

        # 若 ws_receiver 已啟動過，避免重複啟動
        if self.ws_started:
            print("[前端] ws_receiver 已啟動，略過重複啟動")
            return
        
        # 若否則用 create_task() 非同步背景啟動
        asyncio.create_task(self.ws_receiver_with_reconnect())

        # 記錄已啟動 + 印出訊息
        self.ws_started = True
        ct.ws_receiver_start_count += 1
        print(f"[Debug] 第 {ct.ws_receiver_start_count} 次啟動 ws_receiver")


    # ---------- Lobby 切換與連線重置 ----------
    def disconnect_from_server(self):
        # 關閉與 GameServer 的 WebSocket
        try:
            if self.ws_conn:
                loop = self.ws_conn.loop    # 取得該連線的 asyncio event loop
                loop.call_soon_threadsafe(asyncio.create_task, self.ws_conn.close())
                print("[Client] 已要求關閉 WebSocket 連線")
        except Exception as e:
            print(f"[Client] 關閉 WebSocket 發生錯誤: {e}")
        finally:
            self.ws_conn = None         # 清除 WebSocket
            self.ws_started = False     # 標記為未啟動狀態

        # 重設 client 狀態，切換回 lobby 畫面
        self.game_state = "lobby"         # 切換狀態為大廳
        self.current_mole_id = -1         # 清除當前地鼠 ID（避免誤判打擊）
        self.ready_offer = None           # 清除 ready 倒數資訊
        self.joined_ready = False         # 標記玩家未加入 ready
        self.leaderboard_data = []        # 清除排行榜資料
        print("[Client] 已斷開與 GameServer 的連線並重設狀態")


    # 帳號驗證將資料傳給中控
    def quick_login_check(self):
        try:
            async def _check():
                # 與中控伺服器建立 WebSocket 連線
                async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
                    # 傳送登入請求
                    await ws.send(json.dumps({
                        "type": "login",
                        "username": self.username,
                        "password": self.password
                    }))
                    # 接收伺服器回應
                    response = await ws.recv()
                    data = json.loads(response)
                    return data.get("type") == "login_response" and data.get("success")

            return asyncio.run(_check())
        except:
            return False

    # 遊戲開始前 Ready 按鈕 
    def send_ready(self):
        async def _send():
            print("[Debug] send_ready() 被呼叫（內層 async）")
            try:
                msg = "ready"
                # 嘗試使用 open 屬性判斷是否連線中（新版本支持）
                if not getattr(self.ws_conn, "open", True):  # fallback 為 True，保險
                    print("[Debug] ws_conn 未開啟，無法送出 ready")
                    return
                
                is_open = getattr(self.ws_conn, "open", None)
                print(f"[Debug] ws_conn = {self.ws_conn}, open = {is_open if is_open is not None else '未知或不支援'}")

                # print(f"[Debug] ws_conn = {self.ws_conn}, open = {getattr(self.ws_conn, 'open', '未知')}")
                await self.ws_conn.send(msg)
                print(f"[Debug] client.send_ready()：已送出訊息 {msg}")
            except Exception as e:
                print(f"[Debug] client.send_ready() 發送錯誤：{e}")

        self.loop.call_soon_threadsafe(lambda: asyncio.create_task(_send()))
        print("[Debug] create_task 已被呼叫")

    # 傳送一般地鼠打擊事件給後端 GameServerD
    async def send_hit(self, mole_id):
        if self.ws_conn:
            msg = f"hit:{mole_id}"              # 只送打擊判定D
            try:
                await self.ws_conn.send(msg)    # 透過 await
                print(f"[前端] 已送出 hit：{msg}")
            except Exception as e:
                print(f"[前端] 發送 hit 失敗: {e}")
        else:
            print("[前端] ws_conn 無效或已關閉，無法發送 hit")

    # 傳送特殊地鼠打擊事件給後端 GameServer (已關閉)
    async def send_special_hit(self, mole_id):
        if self.ws_conn:
            msg = f"special_hit:{mole_id}"      # 只送打擊判定
            try:
                await self.ws_conn.send(msg)    # 透過 await
                print(f"[前端] 已送出 special_hit：{msg}")
            except Exception as e:
                print(f"[前端] 發送 special_hit 失敗: {e}")
        else:
            print("[前端] ws_conn 無效或已關閉，無法發送 special_hit")


    # WebSocket 重連處理器
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


        # === 新增同步封裝方法（提供 threading 版本用） ===

    # 飛字提示器
    def show_score_popup(self, score, mole_id, mole_name):
        if score != 0:
            if mole_id not in [popup["mole_id"] for popup in gs.score_popups]:
                popup_text = f"{mole_name} {'+' if score > 0 else ''}{score}"

                # 查找對應地鼠顏色
                color = next((m["color"] for m in gs.MOLE_TYPES + gs.SPMOLE_TYPES if m["name"] == mole_name), (255, 215, 0))

                popup = {
                    "text": popup_text,
                    "y_pos": gs.HEIGHT - 120,
                    "alpha": 255,
                    "mole_id": mole_id,
                    "color": color  # 加上這行，給前端用來畫字色
                }
                gs.score_popups.append(popup)

    # again 按鈕 傳給後端
    def send_again(self):
        try:
            asyncio.create_task(self.ws_conn.send("again"))
            print("[Client] 發送 again 給後端")
        except Exception as e:
            print(f"[Client] 發送 again 發生錯誤：{e}")

    # 破紀錄
    # async def send_final_score(self):
    #     if self.ws_conn:
    #         await self.ws_conn.send(f"final:{self.username}:{self.score}")
    #         # print(f"[Client] 已送出 final 分數：{self.username} / {self.score}")

        