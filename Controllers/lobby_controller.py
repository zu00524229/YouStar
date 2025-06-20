# lobby_controller.py : 控制大廳邏輯整合
import pygame as pg
import settings.game_settings as gs
from UI.game_lobby import render_server_status_ui, draw_lobby_title_and_hint


async def handle_server_selection(event, server_buttons, client):
    mouse_x, mouse_y = event.pos
    for rect, url in server_buttons:
        if rect.collidepoint(mouse_x, mouse_y):
            print(f"[Lobby] 玩家選擇連線到 GameServer: {url}")
            client.server_url = url
            await client.start_ws_receiver()
            if hasattr(client, "sync_game_state") and callable(client.sync_game_state):
                result = client.sync_game_state()
                if hasattr(result, "__await__"):
                    await result
            return "play"


async def show_lobby(screen, client, handle_quit):
    pg.display.set_caption("Whack Legends")
    lobby_running = True
    server_list = await client.get_server_list()

    while lobby_running:
        screen.fill(gs.BLACK)
        server_buttons = []
        mouse_x, mouse_y = pg.mouse.get_pos()

        # 處理事件
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

        # 畫面顯示
        draw_lobby_title_and_hint(screen)

        for i, server in enumerate(server_list):
            box_rect = render_server_status_ui(screen, server, 150 + i * 100, mouse_x, mouse_y, i)
            server_buttons.append((box_rect, server["server_url"]))

        pg.display.flip()
        pg.time.Clock().tick(30)
