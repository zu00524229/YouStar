import pygame as pg
import random
import time
import requests
import websockets
import threading
import json
import asyncio

LOGIN_URL = "http://127.0.0.1:8000/login"

username = "player1"
password = "1234"

assigned_server = None
ws_conn = None  # async websockets connection
loop = asyncio.get_event_loop()

# 地鼠同步資料
current_mole_id = -1
current_mole_position = -1
current_mole_type_name = ""
mole_active = False

# 遊戲狀態資料
game_state = "waiting"
remaining_wait_time = 10
loading_time = 0
start_time = time.time()
score = 0
leaderboard_data = []

# 地鼠 receiver (async)
async def ws_receiver_async():
    global ws_conn
    global current_mole_id, current_mole_position, current_mole_type_name, mole_active

    try:
        async with websockets.connect(
            assigned_server,
            origin="http://localhost"
        ) as websocket_mole:
            ws_conn = websocket_mole
            print("[前端] WebSocket 連線成功")

            await websocket_mole.send(username)

            while True:
                msg = await websocket_mole.recv()

                try:
                    data = json.loads(msg)
                    if data.get("event") == "mole_update":
                        mole = data["mole"]
                        current_mole_id = mole["mole_id"]
                        current_mole_position = mole["position"]
                        current_mole_type_name = mole["mole_type"]
                        mole_active = mole["active"]

                        print(f"[前端] 同步地鼠 → ID: {current_mole_id}, pos: {current_mole_position}, type: {current_mole_type_name}, active: {mole_active}")

                except:
                    print(f"[前端] 收到非 json 訊息: {msg}")

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

# status_ws_receiver
async def status_ws_receiver_async():
    global game_state, start_time, remaining_wait_time, loading_time
    last_phase = ""
    last_remaining_time = -1
    last_loading_time = -1

    try:
        async with websockets.connect(
            assigned_server.replace("/ws", "/status_ws"),
            origin="http://localhost"
        ) as websocket_status:
            print("[前端] Status WebSocket 連線成功")

            while True:
                msg = await websocket_status.recv()

                data = json.loads(msg)
                game_phase = data.get("game_phase", "waiting")
                loading_time = data.get("loading_time", 0)
                remaining_wait_time = data.get("remaining_time", 0)

                if game_phase != last_phase:
                    print(f"[前端][Status WS] GameServer 進入 {game_phase} phase")
                    last_phase = game_phase

                    if game_phase == "waiting":
                        game_state = "waiting"
                        start_time = time.time()
                    elif game_phase == "loading":
                        game_state = "loading"
                        start_time = time.time()
                    elif game_phase == "ready":
                        game_state = "ready"
                        start_time = time.time()
                    elif game_phase == "playing":
                        print("[前端][Status WS] GameServer 已進入遊戲，開始 playing")
                        game_state = "playing"
                        start_time = time.time()

                # 只有 loading_time 改變時才印
                if game_phase == "loading":
                    if loading_time != last_loading_time:
                        print(f"[前端][Status WS] loading_time: {loading_time}")
                        last_loading_time = loading_time

                # 只有 playing_time_left 改變時才印
                if game_phase == "playing":
                    if remaining_wait_time != last_remaining_time:
                        print(f"[前端][Status WS] playing_time_left: {remaining_wait_time}")
                        last_remaining_time = remaining_wait_time

    except Exception as e:
        print(f"[前端][Status WS] WebSocket 錯誤: {e}")

# 包 async runner
async def run_ws_receiver():
    await ws_receiver_async()

async def run_status_ws_receiver():
    await status_ws_receiver_async()

# 自動輪詢 login
while assigned_server is None:
    response = requests.post(LOGIN_URL, json={
        "username": username,
        "password": password
    })

    if response.status_code == 200:
        data = response.json()
        if "assigned_server" in data:
            assigned_server = data["assigned_server"]
            print(f"[前端] 登入成功，分配到 GameServer: {assigned_server}")

            game_state = "waiting"

            threading.Thread(target=lambda: asyncio.run(run_ws_receiver()), daemon=True).start()
            threading.Thread(target=lambda: asyncio.run(run_status_ws_receiver()), daemon=True).start()

        else:
            print(f"[前端] 等待中... {data}")
            game_state = "waiting"
            time.sleep(3)

    else:
        print(f"[前端] Loading...{response.text}")
        game_state = "waiting"
        time.sleep(3)

# 初始化 pygame
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
    elapsed_time = time.time() - start_time
    remaining_time = max(0, int(60 - elapsed_time))

    screen.fill(black)

    if game_state == "waiting":
        waiting_surface = font.render(f"Waiting for players...", True, white)
        waiting_rect = waiting_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(waiting_surface, waiting_rect)

    elif game_state == "loading":
        loading_surface = font.render(f"Loading..{loading_time} s", True, white)
        loading_rect = loading_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(loading_surface, loading_rect)


    elif game_state == "ready":
        ready_surface = big_font.render("Ready!", True, (255, 255, 0))
        ready_rect = ready_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(ready_surface, ready_rect)

    elif game_state == "playing":
        score_surface = font.render(f"Score: {score}", True, white)
        screen.blit(score_surface, (20, 20))

        time_surface = font.render(f"Time: {remaining_time}s", True, white)
        screen.blit(time_surface, (350, 20))

        if mole_active and current_mole_position >= 0:
            x, y = grid_positions[current_mole_position]
            mole_color = next(m["color"] for m in MOLE_TYPES if m["name"] == current_mole_type_name)
            pg.draw.circle(screen, mole_color, (x, y), 50)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False

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

    # 遊戲結束
    if game_state == "playing" and remaining_time <= 0:
        game_over_surface = big_font.render("Time out", True, (255, 0, 0))
        text_rect = game_over_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(game_over_surface, text_rect)

        pg.display.flip()
        time.sleep(3)

        screen.fill(black)
        pg.display.flip()

        if ws_conn:
            try:
                future = asyncio.run_coroutine_threadsafe(send_final_score(), loop)
                future.result()  # 等它跑完（同步等待）
                time.sleep(0.5)
            except Exception as e:
                print(f"[前端] 發送 final 時出錯: {e}")

        running = False
        print("[前端] 遊戲結束，通知 player_offline")
        requests.post("http://127.0.0.1:8000/player_offline", json={"username": username})

    pg.display.flip()
    clock.tick(60)

pg.quit()
