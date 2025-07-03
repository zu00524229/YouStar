# gm_server.py      :   Gameserver 主程式 
import asyncio
import websockets
import json
import time
import random
# import math
import threading
import settings.context as ct
from GameServer.gm_utils import get_remaining_time
import GameServer.broadcaster as bc
from GameServer.mole_thread import mole_sender_thread
from GameServer.player_handler import player_handler, zombie_player_cleaner
# from GameServer.gm_special_mole import special_mole_sender_thread
import GameServer.gm_playing as play
import GameServer.gm_loading as load
import GameServer.gm_gameover as over
import GameServer.gm_waiting as wait

ct.load_leaderboard()
print(f"[gm_server] 成功載入 leaderboard：{ct.leaderboard}")
# ---------------------------------------------------
# 向 ControlServer 註冊自己 & 持續報 status / ping
async def register_to_control():
    while True:
        try:
            async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
                print("[GameServer] 已連線中控")
                # 註冊 GameServer　身分給中控
                await ws.send(json.dumps({
                    "type": "register_gameserver",
                    "server_url": ct.MY_GAME_SERVER_WS
                }))

                ct.control_ws = ws

                # 背景啟動：遊戲狀態迴圈與回報狀態
                # 改為 background task → run_status_loop → 狀態更新 & heartbeat
                asyncio.create_task(run_status_loop(ws))
                # 傳送伺服器狀態給 中控 (背景工作)
                asyncio.create_task(send_update_status(ws))


                while True:
                    try:
                        msg = await ws.recv()       # 接收 highlight 訊息
                        data = json.loads(msg)
                        
                         
                        # 從中控接收 highlight 資料 (破紀錄)
                        if data.get("type") == "highlight":
                            print(f"[GameServer] 收到 highlight 指令：{data.get('message')}")
                            await bc.broadcast({
                                "type": "highlight",
                                "message": data.get("message")
                            })


                        # --- 接收 ControlServer 廣播：其他伺服器有空位 ---
                        elif data.get("type") == "new_slot_available":
                            target_server = data.get("target_server")
                            player_count = data.get("current_players")
                            max_players = data.get("max_players")

                            # 不要廣播給自己，也不用存推薦清單
                            if target_server == ct.MY_GAME_SERVER_WS:
                                continue

                            print(f"[GameServer] 收到其他伺服器空位訊息：{target_server}（{player_count}/{max_players}）")

                            # 廣播給本機觀戰者
                            for username in ct.watch_players:
                                ws = ct.player_websockets.get(username)
                                if ws:
                                    try:
                                        await ws.send(json.dumps({
                                            "type": "new_slot_available",
                                            "target_server": target_server,      
                                            "current_players": player_count,    # 傳給前端     
                                            "max_players": max_players,
                                            "game_phase": data.get("game_phase", "waiting")     
                                        }))
                                        print(f"[GameServer] 已轉發給觀戰者 {username}")
                                    except:
                                        print(f"[GameServer] 傳送給觀戰者 {username} 失敗")


                        else:
                            print(f"[GameServer] 收到未知訊息類型：{data.get('type')}")
                    except Exception as e:
                        print(f"[GameServer] 接收中控訊息失敗：{e}")
                        break
                    # await asyncio.sleep(1)

        except Exception as e:
            print(f"[GameServer] 中控連線失敗或斷線，3 秒後重試: {e}")
            ct.control_ws = None  #  清空無效 ws，避免後續錯誤
            await asyncio.sleep(3)

# 定時向 ControlServer 伺服器回報 GameServer 狀態
async def send_update_status(ws):
    print("[Debug] send_update_status() 啟動")
    while True:
        try:
            # 建立要傳送的狀態資料，包含目前玩家數、觀戰人數、排行榜、剩餘時間、遊戲階段等
            await ws.send(json.dumps({
                "type": "update_status",                           # 指定訊息類型為狀態更新
                "server_url": ct.MY_GAME_SERVER_WS,                # 回報自己是誰（目前這台 GameServer 的網址）
                "current_players": len(ct.connected_players - ct.watch_players),  # 實際參與遊戲的玩家數（排除觀戰）
                "watching_players": len(ct.watch_players),         # 目前觀戰人數
                "leaderboard": ct.leaderboard,                     # 最新排行榜資料（遊戲結束後產生）
                "remaining_time": get_remaining_time(),            # 剩餘時間（僅 playing 階段才有意義）
                "game_phase": ct.game_phase                        # 當前遊戲階段：waiting/loading/playing/gameover
            }))
            # print(f"[狀態回報] 當前玩家數: {len(ct.connected_players - ct.watch_players)}")
        except Exception as e:
            print(f"[GameServer] 傳送 update_status 失敗：{e}")
        # 每 1 秒回報一次狀態
        await asyncio.sleep(1)


# (核心)遊戲主控循環:控制 game_phase 狀態機 + 發 status_update 
async def run_status_loop(ws):

    loop_id = random.randint(1000, 9999)
    print(f"[GameServer] run_status_loop 啟動！loop_id = {loop_id}")
    last_log_time = time.time()

    try:
        while True:
            now = time.time()

            # 1. 每 5 秒印出狀態 log，確認還活著
            if now - last_log_time >= 5:
                print(f"[StatusLoop-{loop_id}] still alive... phase={ct.game_phase}, players={len(ct.connected_players)}")
                last_log_time = now

            # 2. 廣播當前狀態給所有玩家
            await bc.broadcast_status_update()

            # 3. 傳送 ping 給中控，包進 try 避免中斷整個 loop
            try:
                await ws.send(json.dumps({"type": "ping"}))
            except Exception as e:
                print(f"[GameServer-{loop_id}] 傳送 ping 給中控失敗: {e}")
                break   # ping 失敗就跳出主循環


            # --- waiting -- 玩家進入遊戲、觸發進入 loading 階段
            if ct.game_phase == "waiting":
                
                await wait.check_start_waiting(now)

            # --- loading -- 倒數完轉為 playing
            elif ct.game_phase == "loading":
                print("[Debug] run_status_loop 檢測到 loading，呼叫 handle_loading_phase()")
                await load.handle_loading_phase()
                # print("[Debug]  handle_loading_phase() 被呼叫進來了")

            # --- playing -- 管理玩家離線與結束倒數
            elif ct.game_phase == "playing":
                await play.handle_playing_phase()

            # --- gameover -- 倒數完轉換
            elif ct.game_phase == "gameover":
                await over.handle_gameover_phase()

            # --- post_gameover -- 等待玩家操作，若無人在線則自動重設
            elif ct.game_phase == "post_gameover":
                if len(ct.connected_players) == 0:
                    print(f"[GameServer-{loop_id}] 無玩家在線，自動從 post_gameover reset → waiting")
                    await over.reset_game_to_waiting()

            elif ct.skip_next_status_update:
                await over.handle_post_gameover_transition()
                continue

            await asyncio.sleep(1)

    except Exception as e:
        print(f"[GameServer] run_status_loop 發生異常: {e}")

    # print(f"[STATUS UPDATE] remaining_time: {remaining_game_time}")

# ---------------------------------------------------
# 啟動主流程
async def main():
    ct.loop = asyncio.get_event_loop()
    # 特殊地鼠 async 任務
    # asyncio.create_task(special_mole_sender())  # 委派

    # 特殊地鼠產生器
    # thread2 = threading.Thread(target=special_mole_sender_thread, daemon=True)
    # thread2.start()

    # 一般地鼠 執行續 任務(同步)
    thread = threading.Thread(target=mole_sender_thread, daemon=True)
    thread.start()

    # 啟動殭屍連線清理
    asyncio.create_task(zombie_player_cleaner())
    # 啟動中控註冊 & 狀態更新
    asyncio.create_task(register_to_control())
    # 每秒廣播剩餘時間（只在 playing 階段）
    asyncio.create_task(play.broadcast_playing_timer_loop())

    # 啟動玩家連線伺服器
    server = await websockets.serve(player_handler, "0.0.0.0", ct.MY_PORT)
    print(f"[GameServer] 等待玩家連線 (port {ct.MY_PORT}) ...")
    await asyncio.Future()  # run forever

# run
asyncio.run(main())
