import pygame as pg
import random
import time
import websockets
import threading
import json
import asyncio

CONTROL_SERVER_WS = "ws://127.0.0.1:8765"

username = "player1"
password = "1234"

assigned_server = None
ws_conn = None  # GameServer ws connection
loop = asyncio.get_event_loop()

# 地鼠同步資料
current_mole_id = -1
current_mole_position = -1
current_mole_type_name = ""
mole_active = False

# 遊戲狀態資料
game_state = "waiting"
remaining_time = 10    # 用 server 傳來的 remaining_time
loading_time = 0
start_time = time.time()
score = 0
game_over_flag = False   # 是否遊戲已結束
state_lock = threading.Lock()
leaderboard_data = []

# 發 offline
async def send_offline():
    try:
        async with websockets.connect(CONTROL_SERVER_WS) as ws:
            await ws.send(json.dumps({
                "type": "offline",
                "username": username
            }))
            print("[前端] 發送 offline 完成")
    except Exception as e:
        print(f"[前端] 發送 offline 失敗: {e}")

# 判斷gameover
def handle_gameover():
    global game_over_flag
    if not game_over_flag:
        game_over_flag = True
        print("[前端] 遊戲結束，通知 player_offline + 發送 final")

        if ws_conn:
            try:
                future = asyncio.run_coroutine_threadsafe(send_final_score(), loop)
                future.result()
                time.sleep(0.5)
            except Exception as e:
                print(f"[前端] 發送 final 時出錯: {e}")

        # 改 → 直接呼叫 handle_quit()，統一流程
        handle_quit()

        print("[前端] handle_gameover 完成，等待玩家點擊 Exit")

# 地鼠 receiver
async def ws_receiver_async():
    global ws_conn
    global current_mole_id, current_mole_position, current_mole_type_name, mole_active
    global game_state, start_time, remaining_time, loading_time, game_phase, leaderboard_data

    try:
        async with websockets.connect(
            assigned_server,
            origin="http://localhost"
        ) as websocket_mole:
            ws_conn = websocket_mole
            print("[前端] WebSocket 連線 GameServer 成功")
            await websocket_mole.send(username)

            while True:
                msg = await websocket_mole.recv()
                try:
                    data = json.loads(msg)

                    if data.get("event") == "mole_update":
                        with state_lock:
                            # 只有在 playing 才更新 mole
                            if game_state == "playing":
                                mole = data["mole"]
                                current_mole_id = mole["mole_id"]
                                current_mole_position = mole["position"]
                                current_mole_type_name = mole["mole_type"]
                                mole_active = mole["active"]

                                print(f"[前端] 地鼠 → ID: {current_mole_id}, pos: {current_mole_position}, type: {current_mole_type_name}, active: {mole_active}")
                            else:
                                # 如果不是 playing → 直接忽略 mole_update
                                pass

                    elif data.get("event") == "leaderboard_update":
                        with state_lock:
                            leaderboard_data = data.get("leaderboard", [])
                            game_state = "gameover"
                        print("[前端] Leaderboard 更新:", leaderboard_data)

                    elif data.get("type") == "status_update":
                        # print(f"[前端] 收到 status_update → game_phase = {data.get('game_phase')}")

                        # 如果 gameover，直接斷線，不收了
                        if game_state == "gameover":
                            print("[前端] 遊戲結束，斷開 WebSocket，不再收 status_update")
                            await ws_conn.close()
                            return

                        with state_lock:
                            # raw game_phase
                            game_phase = data.get("game_phase", "waiting")
                            loading_time = data.get("loading_time", 0)
                            remaining_time = data.get("remaining_time", 0)

                            # print(f"[前端][Status WS] GameServer 進入 {game_phase} phase")

                            # 用 game_phase 決定要不要更新 game_state
                            if game_phase == "waiting":
                                if game_state != "gameover":
                                    game_state = "waiting"
                                    start_time = time.time()
                            elif game_phase == "loading":
                                game_state = "loading"
                                start_time = time.time()
                            elif game_phase == "ready":
                                game_state = "ready"
                                start_time = time.time()
                            elif game_phase == "playing":
                                # 只有 state 轉 playing 才 log
                                if game_state != "playing":
                                    print("[前端][Status WS] GameServer 已進入遊戲，開始 playing")
                                game_state = "playing"
                                start_time = time.time()
                            elif game_phase == "gameover":
                                if game_state != "gameover":
                                    print("[前端][Status WS] GameServer 進入 gameover phase")
                                    handle_gameover()
                                    game_state = "gameover"

                except Exception as e:
                    print(f"[前端] 收到非 json 訊息: {msg}, error: {e}")

    except websockets.exceptions.ConnectionClosed:
        print("[前端] WebSocket 斷線，送 offline")
        await send_offline()

    except Exception as e:
        print(f"[前端] WebSocket 錯誤: {e}")

# 發 final score
async def send_final_score():
    global ws_conn
    try:
        await ws_conn.send(f"final:{username}:{score}")
        print(f"[前端] 發送 final:{username}:{score} 給 GameServer")
        await ws_conn.close()
        print("[前端] WebSocket 已關閉")
    except Exception as e:
        print(f"[前端] 發送 final 時出錯: {e}")

# 登入流程 → 先連 ControlServer login
async def login_to_control():
    global assigned_server
    try:
        async with websockets.connect(CONTROL_SERVER_WS) as ws:
            await ws.send(json.dumps({
                "type": "login",
                "username": username,
                "password": password
            }))

            response = await ws.recv()
            data = json.loads(response)
            if data.get("type") == "login_response" and data.get("success"):
                assigned_server = data["assigned_server"]
                print(f"[前端] 登入成功，分配到 GameServer: {assigned_server}")

                # 啟動 ws_receiver + status_ws_receiver
                threading.Thread(target=lambda: asyncio.run(ws_receiver_async()), daemon=True).start()

            else:
                print(f"[前端] 登入失敗: {data.get('reason')}")
                time.sleep(3)
                await login_to_control()  # 重新 login retry

    except Exception as e:
        print(f"[前端] login_to_control 錯誤: {e}")
        time.sleep(3)
        await login_to_control()  # 重新 login retry

# 包 async runner
def start_login():
    asyncio.run(login_to_control())

threading.Thread(target=start_login, daemon=True).start()

# 控制玩家關閉遊戲時斷線
def handle_quit():
    global running
    running = False
    print("[前端] 玩家關閉視窗 / 結束遊戲，發送 offline")
    try:
        future = asyncio.run_coroutine_threadsafe(send_offline(), loop)
        future.result(timeout=1)
    except Exception as e:
        print(f"[前端] 發送 offline 時出錯或 timeout: {e}")



################################################################################################
########################################### 初始化 pygame ######################################
pg.init()

white = (255, 255, 255)
black = (0, 0, 0)

width = 640
height = 480
screen = pg.display.set_mode((width, height))
pg.display.set_caption("打地鼠")

font = pg.font.SysFont(None, 48)
big_font = pg.font.SysFont(None, 96)

cell_size = 150
offset_x = (width - (cell_size * 3)) // 2
offset_y = (height - (cell_size * 3)) // 2 + 30

grid_positions = []
for row in range(3):
    for col in range(3):
        x = offset_x + col * cell_size + cell_size // 2
        y = offset_y + row * cell_size + cell_size // 2
        grid_positions.append((x, y))

MOLE_TYPES = [
    {"name": "普通地鼠", "color": (200, 100, 100), "score": +1},
    {"name": "黃金地鼠", "color": (255, 215, 0), "score": +5},
    {"name": "炸彈地鼠", "color": (92, 92, 92), "score": -3},
    {"name": "賭博地鼠", "color": (128, 0, 128), "score": 0, "score_range": (-7, 15)},
]

running = True
clock = pg.time.Clock()

# 遊戲主迴圈
while running:
    # ⭐ 用 lock 保證讀 game_state / remaining_time / loading_time
    with state_lock:
        current_game_state = game_state
        current_remaining_time = remaining_time
        current_loading_time = loading_time

    # ⭐ 直接畫 server 傳來的 remaining_time
    time_surface = font.render(f"Time: {current_remaining_time}s", True, white)

    screen.fill(black)

    if current_game_state == "waiting":
        waiting_surface = font.render(f"Waiting for players...", True, white)
        waiting_rect = waiting_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(waiting_surface, waiting_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

    elif current_game_state == "gameover":
        game_over_surface = big_font.render("Time out", True, (255, 0, 0))
        text_rect = game_over_surface.get_rect(center=(width / 2, height / 2 - 50))
        screen.blit(game_over_surface, text_rect)

        # 顯示排行榜
        leaderboard_surface = big_font.render("Leaderboard", True, white)
        leaderboard_rect = leaderboard_surface.get_rect(center=(width / 2, 50))
        screen.blit(leaderboard_surface, leaderboard_rect)

        for idx, entry in enumerate(leaderboard_data[:5]):
            text = f"{idx + 1}. {entry['username']} - {entry['score']}"
            entry_surface = font.render(text, True, white)
            screen.blit(entry_surface, (width / 2 - 150, 100 + idx * 50))

        # 畫 Exit 按鈕
        exit_surface = font.render("Exit", True, (255, 255, 255))
        exit_rect = exit_surface.get_rect(center=(width / 2, height / 2 + 50))
        pg.draw.rect(screen, (100, 100, 100), exit_rect.inflate(20, 10))  # 灰底
        screen.blit(exit_surface, exit_rect)

        # 處理按鈕點擊
        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()
            elif event.type == pg.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pg.mouse.get_pos()
                if exit_rect.collidepoint(mouse_x, mouse_y):
                    handle_quit()

    elif current_game_state == "loading":
        loading_surface = font.render(f"Loading..{current_loading_time} s", True, white)
        loading_rect = loading_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(loading_surface, loading_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

    elif current_game_state == "ready":
        ready_surface = big_font.render("Ready!", True, (255, 255, 0))
        ready_rect = ready_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(ready_surface, ready_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

    elif current_game_state == "playing":
        score_surface = font.render(f"Score: {score}", True, white)
        screen.blit(score_surface, (20, 20))
        screen.blit(time_surface, (350, 20))

        if mole_active and current_mole_position >= 0:
            x, y = grid_positions[current_mole_position]
            mole_color = next(m["color"] for m in MOLE_TYPES if m["name"] == current_mole_type_name)
            pg.draw.circle(screen, mole_color, (x, y), 50)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

            elif event.type == pg.MOUSEBUTTONDOWN and mole_active:
                mouse_x, mouse_y = pg.mouse.get_pos()
                x, y = grid_positions[current_mole_position]

                if (mouse_x - x) ** 2 + (mouse_y - y) ** 2 <= 50 ** 2:
                    print(f"打中了 {current_mole_type_name}！")

                    mole_info = next(m for m in MOLE_TYPES if m["name"] == current_mole_type_name)
                    if "score_range" in mole_info:
                        random_score = random.randint(mole_info["score_range"][0], mole_info["score_range"][1])
                        score += random_score
                        print(f"賭博地鼠獲得分數: {random_score}!")
                    else:
                        score += mole_info["score"]

                    try:
                        asyncio.run(ws_conn.send(f"hit:{current_mole_id}:{score}"))
                        print(f"[前端] 發送 hit:{current_mole_id}:{score} 給 GameServer")
                    except:
                        pass


                    mole_active = False

    pg.display.flip()
    clock.tick(60)
    # 遊戲結束
pg.quit()

# 遊戲結束，通知 offline