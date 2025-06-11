import pygame as pg
import random
import time
import requests
import websocket
import threading

LOGIN_URL = "http://127.0.0.1:8000/login"

username = "player2"
password = "5678"

assigned_server = None
ws = None  # WebSocket 全域變數

# 建立 WebSocket Receiver Thread
def ws_receiver():
    global ws
    try:
        ws = websocket.WebSocket()
        ws.connect(assigned_server)
        print("[前端] WebSocket 連線成功")
        ws.send(username)  # 傳 username

        while True:
            msg = ws.recv()
            print(f"[前端] 收到 GameServer 訊息: {msg}")

    except Exception as e:
        print(f"[前端] WebSocket 錯誤: {e}")

# 加一個同步等待 loadingTime
def wait_for_loading():
    global remaining_wait_time, game_state, start_time
    while True:
        try:
            response = requests.get("http://127.0.0.1:8000/get_gameserver_status", params={
                "gameserver_url": assigned_server
            })
            if response.status_code == 200:
                status = response.json()
                # print(f"[前端] 取得 GameServer 狀態: {status}")

                # if not status["in_game"]:
                #     remaining_wait_time = status["remaining_time"]
                #     game_state = "waiting"
                # else:
                #     print("[前端] GameServer 已進入遊戲，開始 playing")
                #     game_state = "playing"
                #     return  # 退出 thread → 讓主迴圈 playing
                game_phase = status.get("game_phase", "waiting")
                remaining_wait_time = status.get("remaining_time", 0)

                if game_phase == "waiting" or game_phase == "loading":
                    game_state = "waiting"

                elif game_phase == "ready":
                    game_state = "ready"

                elif game_phase == "playing":
                    print("[前端] GameServer 已進入遊戲，開始 playing")
                    game_state = "playing"
                    start_time = time.time()
                    return  # Ready → Playing → 開始遊戲

            else:
                print(f"[前端] 無法取得 GameServer 狀態: {response.text}")
        except Exception as e:
            print(f"[前端] 輪詢 GameServer 狀態異常: {e}")

        time.sleep(1)

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
            # game_state = "playing"

             # 一開始是 waiting，讓 wait_for_loading 自己改成 playing
            game_state = "waiting"

            # 啟動背景 WebSocket Receiver
            threading.Thread(target=ws_receiver, daemon=True).start()

             # 啟動 wait_for_loading Thread
            threading.Thread(target=wait_for_loading, daemon=True).start()

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
bomb = (92, 92, 92)

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

current_mole_type = None
mole_index = None
mole_visible = False
score = 0
start_time = time.time()
game_duration = 60
game_state = "playing"
remaining_wait_time = 10
leaderboard_data = []

next_mole_time = time.time() + 1

running = True
clock = pg.time.Clock()

# 遊戲主迴圈
while running:
    elapsed_time = time.time() - start_time
    remaining_time = max(0, int(game_duration - elapsed_time))

    screen.fill((black))

    if game_state == "waiting":
        waiting_surface = font.render(f"Loading..{remaining_wait_time} s", True, (white))
        waiting_rect = waiting_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(waiting_surface, waiting_rect)

    elif game_state == "ready":
        # 新增 Ready 畫面！
        ready_surface = big_font.render("Ready!", True, (255, 255, 0))
        ready_rect = ready_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(ready_surface, ready_rect)

    elif game_state == "playing":
        screen.fill((black))

        score_surface = font.render(f"Score: {score}", True, (white))
        screen.blit(score_surface, (20, 20))

        time_surface = font.render(f"Time: {remaining_time}s", True, (white))
        screen.blit(time_surface, (350, 20))

        if time.time() >= next_mole_time and remaining_time > 0:
            mole_index = random.randint(0, 8)
            mole_visible = True
            current_mole_type = random.choice(MOLE_TYPES)
            next_mole_time = time.time() + random.uniform(0.5, 1.5)

        if mole_visible and mole_index is not None:
            x, y = grid_positions[mole_index]
            mole_color = current_mole_type["color"]
            pg.draw.circle(screen, mole_color, (x, y), 50)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False

            elif event.type == pg.MOUSEBUTTONDOWN and mole_visible:
                mouse_x, mouse_y = pg.mouse.get_pos()
                x, y = grid_positions[mole_index]

                if (mouse_x - x) ** 2 + (mouse_y - y) ** 2 <= 50 ** 2:
                    print(f"打中了 {current_mole_type['name']}！")

                    if "score_range" in current_mole_type:
                        random_score = random.randint(current_mole_type["score_range"][0], current_mole_type["score_range"][1])
                        score += random_score
                        print(f"賭博地鼠獲得分數: {random_score}!")
                    else:
                        score += current_mole_type["score"]

                    # 回報 GameServer → 點擊地鼠
                    try:
                        ws.send(f"hit:{current_mole_type['name']}:{score}")
                        print(f"[前端] 發送 hit:{current_mole_type['name']}:{score} 給 GameServer")
                    except:
                        pass

                    mole_visible = False

        if game_state == "playing" and remaining_time <= 0:
            game_over_surface = big_font.render("Time out", True, (255, 0, 0))
            text_rect = game_over_surface.get_rect(center=(width / 2, height / 2))
            screen.blit(game_over_surface, text_rect)
            screen.fill((black))

            if ws:
                try:
                    ws.send(f"final:{username}:{score}")
                    print(f"[前端] 發送 final:{username}:{score} 給 GameServer")
                    ws.close()
                    print("[前端] WebSocket 已關閉")
                    time.sleep(0.5)
                except:
                    pass

            if assigned_server:
                print("[前端] 取得排行榜中...")
                try:
                    response = requests.get("http://127.0.0.1:8000/get_leaderboard", params={
                        "gameserver_url": assigned_server
                    })
                    if response.status_code == 200:
                        leaderboard_data = response.json()["leaderboard"]
                        print("[前端] getTop!", leaderboard_data)
                    else:
                        print("[前端] NotTop!", response.text)
                except Exception as e:
                    print("[前端] 取得排行榜異常", e)
            else:
                print("[前端] 沒有 assigned_server，略過排行榜")

            leaderboard_surface = big_font.render("Leaderboard", True, white)
            leaderboard_rect = leaderboard_surface.get_rect(center=(width / 2, 50))
            screen.blit(leaderboard_surface, leaderboard_rect)

            for idx, entry in enumerate(leaderboard_data[:5]):
                text = f"{idx + 1}. {entry['username']} - {entry['score']}"
                entry_surface = font.render(text, True, white)
                screen.blit(entry_surface, (width / 2 - 150, 100 + idx * 50))

            final_score_surface = font.render(f"Final Score: {score}", True, white)
            final_score_rect = final_score_surface.get_rect(center=(width / 2, height / 2 + 120))
            screen.blit(final_score_surface, final_score_rect)

            tip_surface = font.render("Click to exit", True, (white))
            tip_rect = tip_surface.get_rect(center=(width / 2, height / 2 + 180))
            screen.blit(tip_surface, tip_rect)
            pg.display.flip()

            waiting_for_exit = True
            while waiting_for_exit:
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        waiting_for_exit = False
                    elif event.type == pg.MOUSEBUTTONUP:
                        waiting_for_exit = False

            running = False

            print("[前端] 遊戲結束，通知 player_offline")
            requests.post("http://127.0.0.1:8000/player_offline", json={
                "username": username
            })

    pg.display.flip()
    clock.tick(60)

pg.quit()
