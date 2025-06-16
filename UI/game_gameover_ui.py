# game.py 遊戲結束畫面
import pygame as pg
import settings.game_settings as gs

def draw_gameover_screen(screen, leaderboard_data, handle_quit, client):
#     print("[前端狀態]", {
#     "replay_started": client.replay_offer_started,
#     "replay_time": client.replay_offer_remaining_time,
#     "joined": client.replay_offer_joined_players
# })

    if client.game_state != "gameover":
        print("[前端] 已進入非 gameover 狀態，跳出畫面")
        return
    
    if client.game_state == "gameover" and not client.replay_offer_started:
        client.reset_replay_offer()
    replay_rect = None      # 預設為None
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
    replay_rect = None  # 預設為 None，以防止 hover 時未定義錯誤
    if not client.replay_offer_started:
        is_hover_replay = False
        replay_surface = gs.FONT_SIZE.render("Again?", True, (255, 255, 255))
        replay_rect = replay_surface.get_rect(center=(gs.WIDTH / 2 + 100, gs.HEIGHT / 2 + 200))
        is_hover_replay = replay_rect.collidepoint(mouse_x, mouse_y)

        # 文字變色（亮白 or 藍白）
        text_color = (100, 200, 255) if is_hover_replay else (255, 255, 255)
        replay_surface = gs.FONT_SIZE.render("Again?", True, text_color)
        screen.blit(replay_surface, replay_rect)

    # Exit 按鈕
    exit_surface = gs.FONT_SIZE.render("Exit", True, (255, 255, 255))
    exit_rect = exit_surface.get_rect(center=(gs.WIDTH / 2 - 100, gs.HEIGHT / 2 + 200))
    is_hover_exit = exit_rect.collidepoint(mouse_x, mouse_y)

    text_color_exit = (255, 100, 100) if is_hover_exit else (255, 255, 255)
    exit_surface = gs.FONT_SIZE.render("Exit", True, text_color_exit)
    screen.blit(exit_surface, exit_rect)

    # 處理Replay事件
    for event in pg.event.get():
        if event.type == pg.QUIT:
            handle_quit()

        elif event.type == pg.MOUSEBUTTONDOWN:
            if exit_rect.collidepoint(mouse_x, mouse_y):
                handle_quit()
            elif replay_rect and replay_rect.collidepoint(mouse_x, mouse_y):
                print("[前端] 玩家選擇 Play Again，發送 replay")
                client.send_replay()
                with client.state_lock:
                    client.score = 0

    # 處理觀戰
    # for event in pg.event.get():
    #     if event.type == pg.MOUSEBUTTONDOWN:
    #         if join_rect.collidepoint(mouse_x, mouse_y):
    #             client.send_replay()
    #             client.is_watching = False
    #         elif skip_rect.collidepoint(mouse_x, mouse_y):
    #             client.send_watch_mode()
    #             client.is_watching = True

