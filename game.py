# game.py
import pygame as pg
import random
from client import GameClient

# 啟動 GameClient
client = GameClient("player1", "1234")
client.start()

# 初始化 pygame
pg.init()

white = (255, 255, 255)
black = (0, 0, 0)

width = 960
height = 720
screen = pg.display.set_mode((width, height))
pg.display.set_caption("打地鼠")

font = pg.font.SysFont(None, 48)
big_font = pg.font.SysFont(None, 96)

cell_size = 150
offset_x = (width - (cell_size * 4)) // 2
offset_y = (height - (cell_size * 4)) // 2 + 30

grid_positions = []
for row in range(4):
    for col in range(4):
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

def handle_quit():
    global running
    running = False
    print("[前端] 玩家關閉視窗，離開遊戲。")

# 遊戲主迴圈
while running:
    # ⭐ 用 lock 保證讀 game_state / remaining_time / loading_time
    with client.state_lock:
        current_game_state = client.game_state
        current_remaining_time = client.remaining_time
        current_loading_time = client.loading_time
        current_mole_id = client.current_mole_id
        current_mole_position = client.current_mole_position
        current_mole_type_name = client.current_mole_type_name
        mole_active = client.mole_active
        leaderboard_data = client.leaderboard_data
        score = client.score

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

                    # 更新 client.score，發送 hit
                    with client.state_lock:
                        client.score = score
                    client.send_hit()

                    mole_active = False

    pg.display.flip()
    clock.tick(60)

pg.quit()
