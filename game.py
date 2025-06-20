# game.py : 遊戲主程式
import time
start_time = time.time()

import pygame as pg
import asyncio
import websockets

from UI.client import GameClient
import settings.game_settings as gs
import UI.game_lobby as lob
import UI.login_ui as log
import main_loop as loop

# 啟動畫面
def show_start_screen(screen):
    screen.fill(gs.BLACK)
    font = pg.font.SysFont("Arial", 48)
    title = font.render("Whack Legends", True, (255, 255, 255))
    screen.blit(title, (gs.WIDTH // 2 - 140, gs.HEIGHT // 2 - 50))
    pg.display.flip()
    pg.time.wait(1000)
    
# === 真正執行主流程 ===
async def main():
    pg.init()
    screen = pg.display.set_mode((gs.WIDTH, gs.HEIGHT))
    pg.display.set_caption("Whack Legends")
    show_start_screen(screen)

    # 等待登入
    client = await log.login_screen(screen)

    while not client.login_success:
        print("[大廳] 等待登入完成...")
        screen.fill(gs.BLACK)
        loading_surface = gs.FONT_SIZE.render("Logging in...", True, gs.WHITE)
        loading_rect = loading_surface.get_rect(center=(gs.WIDTH // 2, gs.HEIGHT // 2))
        screen.blit(loading_surface, loading_rect)
        pg.display.flip()
        await asyncio.sleep(0.1)

    print(f"[DEBUG] 完整啟動時間：{time.time() - start_time:.2f} 秒")

    # 遊戲主迴圈控制
    running = True
    clock = pg.time.Clock()

    while running:
        result = "lobby"
        while result == "lobby":
            result = await lob.show_lobby(screen, client, loop.handle_quit)

        if result == "play":
            result = loop.run_game_loop(screen, client)
            client.ready_mode = "none"

        elif result == "again":
            continue

        elif result == "watch":
            loop.run_watch_mode(screen, client)

        elif result == "quit":
            break

# 啟動程式
if __name__ == "__main__":
    asyncio.run(main())
