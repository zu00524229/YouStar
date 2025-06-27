# game_gameover_ui.py
import pygame as pg
import settings.game_settings as gs
import settings.animation as ani

def draw_gameover_screen(screen, handle_quit, client, events):
    if client.game_state not in ["gameover", "post_gameover"]:
        print("[前端] 已進入非 gameover/post_gameover 狀態，跳出畫面")
        return


    # 畫面標題 :Leaderboard
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

    # Lobby 按鈕（永遠顯示）
    exit_surface = gs.FONT_SIZE.render("Lobby", True, gs.WHITE)
    exit_rect = exit_surface.get_rect(center=(gs.WIDTH / 2 - 120, gs.HEIGHT - 80))
    is_hover_exit = exit_rect.collidepoint(mouse_x, mouse_y)
    exit_surface = gs.FONT_SIZE.render("Lobby", True, gs.HOVAR if is_hover_exit else gs.WHITE)
    screen.blit(exit_surface, exit_rect)

    # Again 按鈕（僅發起人用）
    again_surface = gs.FONT_SIZE.render("Again", True, gs.HOVAR if pg.Rect(gs.WIDTH / 2 + 120 - 40, gs.HEIGHT - 80 - 20, 80, 40).collidepoint(mouse_x, mouse_y) else gs.WHITE)
    again_rect = again_surface.get_rect(center=(gs.WIDTH / 2 + 120, gs.HEIGHT - 80))
    screen.blit(again_surface, again_rect)

    # === 處理滑鼠點擊 ===
    for event in events:
        if event.type == pg.QUIT:
            handle_quit()

        elif event.type == pg.MOUSEBUTTONDOWN:
            ani.add_click_effect(event.pos)
            print(f"[Debug] Mouse click at {mouse_x}, {mouse_y}")

            if again_rect.collidepoint(mouse_x, mouse_y):
                print("[Debug] Clicked AGAIN")
                # client.send_post_game_again()  # 傳送 again:<username>
                return None

            if exit_rect.collidepoint(mouse_x, mouse_y):
                print("[Debug] Clicked LOBBY")
                client.disconnect_from_server()
                return "lobby"

    return None


