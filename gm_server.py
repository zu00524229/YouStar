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
from GameServer.player_handler import player_handler
from GameServer.gm_special_mole import special_mole_sender
import GameServer.gm_playing as play
import GameServer.gm_loading as load
import GameServer.gm_gameover as over
import GameServer.gm_waiting as wait

# ---------------------------------------------------
# 向 ControlServer 註冊自己 & 持續報 status / ping
async def register_to_control():
    while True:
        try:
            async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
                print("[GameServer] 已連線中控")
                await ws.send(json.dumps({
                    "type": "register_gameserver",
                    "server_url": ct.MY_GAME_SERVER_WS
                }))

                # 改為 background task → run_status_loop → 狀態更新 & heartbeat
                asyncio.create_task(run_status_loop(ws))
                # 傳送伺服器狀態給 中控 (背景工作)
                asyncio.create_task(send_update_status(ws))

                # 保持 websocket 連線
                while True:
                    await asyncio.sleep(1)

        except Exception as e:
            print(f"[GameServer] 中控連線失敗或斷線，3 秒後重試: {e}")
            await asyncio.sleep(3)

async def send_update_status(ws):
    print("[Debug] send_update_status() 啟動")
    while True:
        try:
            print(f"[Debug] 傳送中控狀態：{ct.game_phase}, {len(ct.connected_players)}人")
            await ws.send(json.dumps({
                "type": "update_status",
                "server_url": ct.MY_GAME_SERVER_WS,
                "current_players": len(ct.connected_players - ct.watch_players),
                "watching_players": len(ct.watch_players),         # 當前觀戰人數
                "leaderboard": ct.leaderboard,
                "remaining_time":  get_remaining_time(),
                "game_phase": ct.game_phase
            }))
        except Exception as e:
            print(f"[GameServer] 傳送 update_status 失敗：{e}")
        await asyncio.sleep(1)


# ---------------------------------------------------
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


            # --- waiting -- 玩家進入遊戲、觸發進入 loading 階段
            if ct.game_phase == "waiting":
                # print(f"[Debug] game_phase={ct.game_phase}, ready_offer_active={ct.ready_offer_active}, loading_start_time={ct.loading_start_time}")
                await wait.check_start_waiting(now)
                if ct.ready_offer_active and ct.loading_start_time is not None:
                    await wait.handle_ready_offer(now)

            # --- loading -- 倒數完轉為 playing
            elif ct.game_phase == "loading":
                print("[Debug] run_status_loop 檢測到 loading，呼叫 handle_loading_phase()")
                await load.handle_loading_phase()
                print("[Debug]  handle_loading_phase() 被呼叫進來了")

            # --- playing -- 管理玩家離線與結束倒數
            elif ct.game_phase == "playing":
                await play.handle_playing_phase()

            # --- gameover -- 倒數完轉換(等待玩家是否下局或觀戰)
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
    # 特殊地鼠 async 任務(因為少出現 非同步就夠了)
    asyncio.create_task(special_mole_sender())  # 委派
    
    # 一般地鼠 執行續 任務(同步)
    thread = threading.Thread(target=mole_sender_thread, daemon=True)
    thread.start()

    # 啟動中控註冊 & 狀態更新
    asyncio.create_task(register_to_control())
    # 每秒廣播剩餘時間（只在 playing 階段）
    asyncio.create_task(play.broadcast_playing_timer_loop())

    # 啟動玩家連線伺服器
    server = await websockets.serve(player_handler, "0.0.0.0", 8001)
    print("[GameServer] 等待玩家連線 (port 8001) ...")
    await asyncio.Future()  # run forever

# run
asyncio.run(main())
