# lobby_controller.py : 控制大廳邏輯整合
import pygame as pg
import settings.game_settings as gs
import asyncio
import time
from UI.game_lobby import render_server_status_ui, draw_lobby_title_and_hint


# 處理玩家選擇 GameServer 的事件（滑鼠點擊
async def handle_server_selection(event, server_buttons, client):
    mouse_x, mouse_y = event.pos

    for box_rect, watch_button_rect, url in server_buttons:
        if box_rect.collidepoint(mouse_x, mouse_y):
            print(f"[Lobby] 玩家選擇連線到 GameServer: {url}")
            client.server_url = url
            await client.connect_to_server()
            await client.start_ws_receiver()
            print(f"[Lobby] 玩家點選 GameServer，呼叫 start_ws_receiver()，client ID: {id(client)}")
            client.sync_game_state()

            
            # 只允許在 waiting/loading 狀態下加入遊戲，否則自動觀戰
            if client.game_state in ["waiting", "loading"]:
                print(f"[Lobby] 成功連線至 {url}，伺服器處於 {client.game_state}，加入遊戲")
                return "play"
            else:
                print(f"[Lobby] 伺服器處於 {client.game_state} 階段，將自動切換為觀戰模式")
                client.is_watching = True
                return "play"

        # 觀戰
        elif watch_button_rect and watch_button_rect.collidepoint(mouse_x, mouse_y):
            print(f"[Lobby] 玩家選擇觀戰 GameServer: {url}")
            client.server_url = url
            await client.send_watch(url)        # 呼叫Client 觀戰方法
            await client.start_ws_receiver()    # 呼叫GameServer 訊息監聽 (防重複點擊
            client.sync_game_state()            # 初始化狀態
            return "play"


async def show_lobby(screen, client, handle_quit):
    print("[Debug] show_lobby() 被呼叫")
    pg.display.set_caption("Whack Legends")
    lobby_running = True

    server_list = await client.get_server_list()
    last_refresh_time = time.time()
    while lobby_running:
        screen.fill(gs.BLACK)
        server_buttons = []
        mouse_x, mouse_y = pg.mouse.get_pos()

        if time.time() - last_refresh_time > 1.0:
            server_list = await client.get_server_list()
            last_refresh_time = time.time()

        draw_lobby_title_and_hint(screen)

        for i, server in enumerate(server_list):
            box_rect, watch_button_rect = render_server_status_ui(
                screen, server, 150 + i * 100, mouse_x, mouse_y, i
            )
            server_buttons.append((box_rect, watch_button_rect, server["server_url"]))

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

            elif event.type == pg.KEYDOWN and event.key == pg.K_r:
                print("[Lobby] 玩家按下 R，重新取得 server list")
                server_list = await client.get_server_list()

            elif event.type == pg.MOUSEBUTTONDOWN:
                result = await handle_server_selection(event, server_buttons, client)
                if result == "play":
                    return "play"

        pg.display.flip()
        pg.time.Clock().tick(30)