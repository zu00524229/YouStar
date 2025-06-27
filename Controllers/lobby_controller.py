# lobby_controller.py : 控制大廳邏輯整合
import pygame as pg
import settings.game_settings as gs
import asyncio
import time
from UI.game_lobby import render_server_status_ui, draw_lobby_title_and_hint
import settings.animation as ani


# 處理玩家選擇 GameServer 的事件（滑鼠點擊
async def handle_server_selection(event, server_buttons, client):
    mouse_x, mouse_y = event.pos

    for box_rect, watch_button_rect, url in server_buttons:
        # 觀戰邏輯:只有點到 watch_button_rect 才進入
        if watch_button_rect and watch_button_rect.collidepoint(mouse_x, mouse_y):
            print(f"[Lobby] 玩家選擇連線到 GameServer: {url}")
            client.server_url = url
            client.is_watching = True       # 觀戰者
            client.score = 0                # 分數0
            await client.send_watch(url)
            # await client.connect_to_server()
            await client.start_ws_receiver()
            print(f"[Lobby] 玩家點選 GameServer，呼叫 start_ws_receiver()，client ID: {id(client)}")
            client.sync_game_state()
            return "play"

       # 一般點框邏輯：只允許 waiting/loading 時加入
        elif box_rect.collidepoint(mouse_x, mouse_y):
            # 查詢目前這個伺服器的狀態（用 client.get_server_list()
            server_list = await client.get_server_list()
            matching = [s for s in server_list if s['server_url'] == url]
            if matching:
                server_state = matching[0].get("game_phase", "")
                if server_state in ["waiting", "loading"]:
                    print(f"[Lobby] 玩家選擇連線到 GameServer: {url}")
                    client.server_url = url
                    client.is_watching = False      # 非觀戰者
                    await client.connect_to_server()
                    await client.start_ws_receiver()
                    client.sync_game_state()
                    print(f"[Lobby] 伺服器處於 {server_state}，進入遊戲模式")
                    return "play"
                else:
                    print(f"[Lobby] 選擇遊戲伺服器時機錯誤：{client.game_state} 階段，請點 Watch 按鈕觀戰")
                    # 可考慮加提示音或畫面提示
                    return None
            else:
                print("[Lobby] 找不到該伺服器資訊，請重試")
                return None

async def show_lobby(screen, client, handle_quit):
    print("[Debug] show_lobby() 被呼叫")
    pg.display.set_caption("Whack Legends")
    lobby_running = True

    server_list = await client.get_server_list()
    print("[Debug] 目前伺服器列表：", server_list)
    last_refresh_time = time.time()
    while lobby_running:
        events = pg.event.get()
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

        for event in events:
            if event.type == pg.QUIT:
                handle_quit()

            elif event.type == pg.KEYDOWN and event.key == pg.K_r:
                print("[Lobby] 玩家按下 R，重新取得 server list")
                server_list = await client.get_server_list()

            elif event.type == pg.MOUSEBUTTONDOWN:
                ani.add_click_effect(event.pos)
                result = await handle_server_selection(event, server_buttons, client)
                if result == "play":
                    return "play"

        ani.draw_click_effects(screen)
        pg.display.flip()
        pg.time.Clock().tick(30)