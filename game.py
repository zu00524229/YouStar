# game.py : 遊戲主程式

import time
start_time = time.time()  # 放最前面，記錄「啟動時刻」

import pygame as pg
import asyncio
import websockets

from UI.client import GameClient
import settings.game_settings as gs
import UI.game_lobby as lob
import UI.login_ui as log
import main_loop as loop


# 啟動遊戲過渡畫面
def show_start_screen(screen):
    screen.fill(gs.BLACK)
    font = pg.font.SysFont("Arial", 48)
    title = font.render("Whack Legends", True, (255, 255, 255))
    screen.blit(title, (gs.WIDTH // 2 - 140, gs.HEIGHT // 2 - 50))
    pg.display.flip()
    pg.time.wait(1000)


# === 初始化 ===
pg.init()

screen = pg.display.set_mode((gs.WIDTH, gs.HEIGHT))
pg.display.set_caption("Whack Legends")
show_start_screen(screen)
# === login ===
client = log.login_screen(screen)
client.start_ws_receiver()
print("[Debug] login_screen 已完成並返回 client")

# 過渡畫面
while not client.login_success:
    print("[大廳] 等待登入完成...")
    screen.fill(gs.BLACK)
    loading_surface = gs.FONT_SIZE.render("Logging in...", True, gs.WHITE)
    loading_rect = loading_surface.get_rect(center=(gs.WIDTH // 2, gs.HEIGHT // 2))
    screen.blit(loading_surface, loading_rect)
    pg.display.flip()
    pg.time.wait(100)  # 等 100ms，避免吃 CPU

print(f"[DEBUG] 完整啟動時間：{time.time() - start_time:.2f} 秒")
# _original_connect = websockets.connect

# def debug_connect(uri, *args, **kwargs):
#     print(f"[debug patch] websockets.connect 被呼叫，URI = {uri!r}")
#     return _original_connect(uri, *args, **kwargs)

# websockets.connect = debug_connect

# 印出「完整載入並顯示畫面」的時間


# === 控制主迴圈變數 ===
running = True
clock = pg.time.Clock()


# 遊戲主迴圈
while running:
    # === 顯示大廳 ===
    result = "lobby"

    while result == "lobby":
        result = lob.show_lobby(screen, client, loop.handle_quit)

    if result == "play":
        result = loop.run_game_loop(screen, client)
        client.ready_mode = "none"

    elif result == "again":
        continue  # 直接下一輪

    elif result == "watch":
        loop.run_watch_mode(screen, client)

    elif result == "lobby":
        # 重新登入流程
        client = log.login_screen(screen)
        print("[Debug] login_screen 已完成並返回 client")
        client.start_ws_receiver()
        continue
    elif result == "quit":
        break

