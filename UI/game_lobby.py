# game_lobby.py     :   game.py 的遊戲大廳邏輯
# import threading
# import asyncio
import pygame as pg
import settings.game_settings as gs

# 大廳伺服器排版
def render_server_status(surface, server, box_y, mouse_x, mouse_y, index):
    box_width = 600
    box_height = 80
    box_x = (gs.WIDTH - box_width) // 2

    box_rect = pg.Rect(box_x, box_y, box_width, box_height)

    # 判斷是否 hover
    is_hover = box_rect.collidepoint(mouse_x, mouse_y)
    box_color = (gs.HOVAR) if is_hover else (60, 60, 60)

    # 畫方框
    pg.draw.rect(surface, box_color, box_rect)
    pg.draw.rect(surface, (200, 200, 200), box_rect, 2)  # 外框線

    # Server 名字用大字
    server_name_surface = gs.FONT_SIZE.render(f"GameServer {index + 1}", True, (gs.WHITE))
    server_name_rect = server_name_surface.get_rect(topleft=(box_x + 20, box_y + 10))
    surface.blit(server_name_surface, server_name_rect)

    # 小字: 玩家數 / Status
    phase_map = {
        "waiting": "Waiting",
        "loading": "Loading",
        "ready": "Ready",
        "playing": "Playing",
        "gameover": "Game Over"
    }
    status_text = f"({server['current_players']}/{server['max_players']})   Status: {phase_map.get(server['game_phase'], server['game_phase'])}"

    small_font_render = pg.font.SysFont(None, 32)
    status_surface = small_font_render.render(status_text, True, (200, 200, 200))
    status_rect = status_surface.get_rect(topleft=(box_x + 20, box_y + 45))
    surface.blit(status_surface, status_rect)

    return box_rect

# --- 大廳畫面 ---
def show_lobby(screen, client, handle_quit):
    pg.display.set_caption("Whack Legends")
    lobby_running = True


    while lobby_running:
        server_list = client.get_server_list()  # 初次取得（避免每幀都 call）
        screen.fill(gs.BLACK)

        # === 處理事件 ===
        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_r:  # 按 R 鍵刷新 server_list
                    print("[Lobby] 玩家按下 R，重新取得 server list")
                    server_list = client.get_server_list()

            elif event.type == pg.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pg.mouse.get_pos()
                for rect, url in server_buttons:
                    if rect.collidepoint(mouse_x, mouse_y):
                        print(f"[Lobby] 玩家選擇連線到 GameServer: {url}")
                        client.server_url = url
                        client.start_ws_receiver()
                        client.sync_game_state()    # 強制同步最新狀態，避免停留在舊的gameserver
                        return "play"               # 明確回傳 play


        # === 畫面顯示 ===
        title_surface = gs.BIG_FONT_SIZE.render("Game Lobby", True, (gs.WHITE))
        title_rect = title_surface.get_rect(center=(gs.WIDTH / 2, 80))
        screen.blit(title_surface, title_rect)

        server_buttons = []
        box_width, box_height = 600, 80
        mouse_x, mouse_y = pg.mouse.get_pos()

        for i, server in enumerate(server_list):
            box_rect = render_server_status(screen, server, 150 + i * (box_height + 20), mouse_x, mouse_y, i)
            server_buttons.append((box_rect, server["server_url"]))

        hint_surface = pg.font.SysFont(None, 28).render("Click to join. Press R to refresh.", True, (150, 150, 150))
        hint_rect = hint_surface.get_rect(center=(gs.WIDTH / 2, gs.HEIGHT - 50))
        screen.blit(hint_surface, hint_rect)

        pg.display.flip()
        pg.time.Clock().tick(30)

