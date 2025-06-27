# game.py : 遊戲主程式
import time
start_time = time.time()

import pygame as pg
import asyncio
import websockets       # 用於 WebSocket 非同步通訊

# === 引入各個模組 ===
from UI.client import GameClient              # 前端用戶端管理者，包含 ws_conn、狀態更新
import settings.game_settings as gs           # 畫面設定等常數
import UI.game_lobby as lob                   # 遊戲大廳畫面
import Controllers.lobby_controller as conlob # 控制大廳行為（選擇伺服器）
import UI.login_ui as log                     # 登入畫面邏輯
import main_loop as lp                      # 遊戲主流程（目前已改為 async）

# 啟動畫面：純同步的畫面初始化，無需 async
def show_start_screen(screen):
    screen.fill(gs.BLACK)
    font = pg.font.SysFont("Arial", 48)
    title = font.render("Whack Legends", True, (255, 255, 255))
    screen.blit(title, (gs.WIDTH // 2 - 120, gs.HEIGHT // 2 - 50))
    pg.display.flip()
    pg.time.wait(1000)  # 這是同步暫停，不影響 async，因為在主程式前就執行完

# === 真正執行主流程（ async 函式）===
async def main():
    pg.init()
    screen = pg.display.set_mode((gs.WIDTH, gs.HEIGHT))
    pg.display.set_caption("Whack Legends")
    show_start_screen(screen)   # 同步執行啟動畫面

    # 非同步登入畫面（內部會建立與 ControlServer 的 WebSocket 並登入）
    # 這裡是 async 等待 login_screen 執行完成，過程中可能會有 await recv/send
    # 等待登入
    client = await log.login_screen(screen)

    # 遊戲主迴圈控制
    running = True
    clock = pg.time.Clock()

    while running:
        print(f"[Main] 執行 show_lobby()，client ID: {id(client)}")
        result = "lobby"
        while result == "lobby":
            # 非同步顯示 lobby  (可即時更新 server 狀態 & 點擊反應）
            # show_lobby 裡可能會有 WebSocket 狀態同步 → 必須 await
            result = await conlob.show_lobby(screen, client, lp.handle_quit)

        # 進入遊戲流程
        if result == "play":
            result = await lp.run_game_loop(screen, client)
            client.ready_mode = "none"      # 重設狀態供下一輪使用

        # again → 會再進入 lobby → play → loop.run_game_loop（再次執行整個流程）
        # elif result == "again":
        #     continue

        elif result == "lobby":
            await lp.handle_quit_to_lobby(screen, client)
            continue    # 回到 while result == "lobby"，重新選擇伺服器

        # 觀戰
        elif result == "watch":
            await client.send_watch()  
            return "watch"

        # 結束流程
        elif result == "quit":
            break

# 啟動程式主入口：使用 asyncio.run() 啟動 event loop
# 這是 Python 3.7+ 執行 async 程式的標準做法，會建立 asyncio event loop
if __name__ == "__main__":
    asyncio.run(main())
