import pygame as pg
import settings.game_settings as gs

def draw_gameover_screen(screen, handle_quit, client):
    if client.game_state not in ["gameover", "post_gameover"]:
        print("[前端] 已進入非 gameover/post_gameover 狀態，跳出畫面")
        return

    if client.game_state in ["gameover", "post_gameover"] and not client.ready_offer_started:
        client.reset_ready_offer()


    # 畫面標題
    leaderboard_surface = gs.BIG_FONT_SIZE.render("Leaderboard", True, gs.WHITE)
    leaderboard_rect = leaderboard_surface.get_rect(center=(gs.WIDTH / 2, 70))
    screen.blit(leaderboard_surface, leaderboard_rect)

    # 顯示排行榜前五名
    for idx, entry in enumerate(client.leaderboard_data[:5]):
        text = f"{idx + 1}. {entry['username']} - {entry['score']}"
        entry_surface = gs.FONT_SIZE.render(text, True, gs.WHITE)
        screen.blit(entry_surface, (gs.WIDTH / 2 - 150, 120 + idx * 40))

    # 滑鼠位置
    mouse_x, mouse_y = pg.mouse.get_pos()

    # === 下方按鈕 ===
    # Lobby 按鈕（永遠顯示）
    exit_surface = gs.FONT_SIZE.render("Lobby", True, gs.WHITE)
    exit_rect = exit_surface.get_rect(center=(gs.WIDTH / 2 - 120, gs.HEIGHT - 80))
    is_hover_exit = exit_rect.collidepoint(mouse_x, mouse_y)
    exit_surface = gs.FONT_SIZE.render("Lobby", True, gs.HOVAR if is_hover_exit else gs.WHITE)
    screen.blit(exit_surface, exit_rect)

    # Again 邏輯：兩種狀態
    if not client.ready_offer_started:
        # 初始 Ready 按鈕（發起人）
        ready_surface = gs.FONT_SIZE.render("Again", True, gs.WHITE)
        ready_rect = ready_surface.get_rect(center=(gs.WIDTH / 2 + 120, gs.HEIGHT - 80))
        is_hover_ready = ready_rect.collidepoint(mouse_x, mouse_y)
        ready_surface = gs.FONT_SIZE.render("Again", True, gs.HOVAR if is_hover_ready else gs.WHITE)
        screen.blit(ready_surface, ready_rect)
    else:
        # READY? + Ready + Watch 按鈕（出現在相同位置）
        ready_status = gs.FONT_SIZE.render("READY?", True, gs.YELLOW)
        screen.blit(ready_status, (gs.WIDTH / 2 - 40, gs.HEIGHT - 140))

        join_ready_surface = gs.FONT_SIZE.render("Join", True, gs.WHITE)
        watch_surface = gs.FONT_SIZE.render("Watch", True, gs.WHITE)

        join_rect = join_ready_surface.get_rect(center=(gs.WIDTH / 2 - 60, gs.HEIGHT - 80))
        watch_rect = watch_surface.get_rect(center=(gs.WIDTH / 2 + 60, gs.HEIGHT - 80))

        is_hover_join = join_rect.collidepoint(mouse_x, mouse_y)
        is_hover_watch = watch_rect.collidepoint(mouse_x, mouse_y)

        join_ready_surface = gs.FONT_SIZE.render("Join", True, gs.HOVAR if is_hover_join else gs.WHITE)
        watch_surface = gs.FONT_SIZE.render("Watch", True, gs.HOVAR if is_hover_watch else gs.WHITE)

        screen.blit(join_ready_surface, join_rect)
        screen.blit(watch_surface, watch_rect)

    # 事件處理
    for event in pg.event.get():
        if event.type == pg.QUIT:
            handle_quit()

        elif event.type == pg.MOUSEBUTTONDOWN:
            if not client.ready_offer_started and ready_rect.collidepoint(mouse_x, mouse_y):
                client.send_post_game_again()
                client.ready_offer_started = True
                return "again"   # 主程式收到後可判斷

            elif client.ready_offer_started:
                if join_rect.collidepoint(mouse_x, mouse_y):
                    client.send_post_game_again()
                    return "again"
                elif watch_rect.collidepoint(mouse_x, mouse_y):
                    return "watch"

            elif exit_rect.collidepoint(mouse_x, mouse_y):
                client.disconnect_from_server()
                return "lobby"

    return None  # 沒有點擊任何按鈕

