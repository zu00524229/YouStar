# game_gameover_ui.py       :   game.py 遊戲結束畫面
import pygame as pg
import settings.game_settings as gs

def draw_gameover_screen(screen, leaderboard_data, handle_quit, client, handle_quit_to_lobby):
#     print("[前端狀態]", {
#     "ready_started": client.ready_offer_started,
#     "ready_time": client.ready_offer_remaining_time,
#     "joined": client.ready_offer_joined_players
# })

    if client.game_state != "gameover":
        print("[前端] 已進入非 gameover 狀態，跳出畫面")
        return
    
    if client.game_state == "gameover" and not client.ready_offer_started:
        client.reset_ready_offer()
    ready_rect = None      # 預設為None
    # 畫面標題
    leaderboard_surface = gs.BIG_FONT_SIZE.render("Leaderboard", True, gs.WHITE)
    leaderboard_rect = leaderboard_surface.get_rect(center=(gs.WIDTH / 2, 70))
    screen.blit(leaderboard_surface, leaderboard_rect)

    # 畫排行榜前五名
    for idx, entry in enumerate(leaderboard_data[:5]):
        text = f"{idx + 1} {entry['username']} - {entry['score']}"
        entry_surface = gs.FONT_SIZE.render(text, True, gs.WHITE)
        screen.blit(entry_surface, (gs.WIDTH / 2 - 120, 100 + idx * 50))

    # 滑鼠位置要一開始就定義好
    mouse_x, mouse_y = pg.mouse.get_pos()

    # Again 按鈕
    ready_rect = None  # 預設為 None，以防止 hover 時未定義錯誤
    if not client.ready_offer_started:
        is_hover_ready = False
        ready_surface = gs.FONT_SIZE.render("Again?", True, (gs.WHITE))
        ready_rect = ready_surface.get_rect(center=(gs.WIDTH / 2 + 100, gs.HEIGHT / 2 + 200))
        is_hover_ready = ready_rect.collidepoint(mouse_x, mouse_y)

        # 文字變色（亮白 or 藍白）
        text_color = (100, 200, 255) if is_hover_ready else (gs.WHITE)
        ready_surface = gs.FONT_SIZE.render("Again?", True, text_color)
        screen.blit(ready_surface, ready_rect)

    # Relobby 按鈕
    exit_surface = gs.FONT_SIZE.render("lobby", True, (gs.WHITE))
    exit_rect = exit_surface.get_rect(center=(gs.WIDTH / 2 - 100, gs.HEIGHT / 2 + 200))
    is_hover_exit = exit_rect.collidepoint(mouse_x, mouse_y)

    text_color_exit = (255, 100, 100) if is_hover_exit else (gs.WHITE)
    exit_surface = gs.FONT_SIZE.render("lobby", True, text_color_exit)
    screen.blit(exit_surface, exit_rect)

    # 處理ready事件
    for event in pg.event.get():
        if event.type == pg.QUIT:
            handle_quit()

        elif event.type == pg.MOUSEBUTTONDOWN:
            if again_rect.collidepoint(mouse_x, mouse_y):
                client.ready_mode = "again"
                return  # 直接結束畫面，由主程式處理

            elif watch_rect.collidepoint(mouse_x, mouse_y):
                client.ready_mode = "watch"
                return

            elif lobby_rect.collidepoint(mouse_x, mouse_y):
                handle_quit_to_lobby(screen, client)

