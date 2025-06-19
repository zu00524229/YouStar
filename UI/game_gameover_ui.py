# game_gameover_ui.py : Pygame 結束畫面

import pygame as pg
import settings.game_settings as gs


# ✅ 主函式：繪製遊戲結束畫面與互動邏輯
def draw_gameover_screen(screen, leaderboard_data, handle_quit, client, handle_quit_to_lobby):
    # --- 狀態檢查：非 gameover 就不顯示此畫面 ---
    if client.game_state != "gameover":
        print("[前端] 已進入非 gameover 狀態，跳出畫面")
        return

    # --- 第一次進入 gameover，重設 ready 狀態 ---
    if client.game_state == "gameover" and not client.ready_offer_started:
        client.reset_ready_offer()

    ready_rect = None  # 預設為 None，避免尚未定義時出錯

    # --- 畫面標題 ---
    leaderboard_surface = gs.BIG_FONT_SIZE.render("Leaderboard", True, gs.WHITE)
    leaderboard_rect = leaderboard_surface.get_rect(center=(gs.WIDTH / 2, 70))
    screen.blit(leaderboard_surface, leaderboard_rect)

    # --- 顯示排行榜前五名 ---
    for idx, entry in enumerate(leaderboard_data[:5]):
        text = f"{idx + 1} {entry['username']} - {entry['score']}"
        entry_surface = gs.FONT_SIZE.render(text, True, gs.WHITE)
        screen.blit(entry_surface, (gs.WIDTH / 2 - 120, 100 + idx * 50))

    # --- 定義滑鼠位置 ---
    mouse_x, mouse_y = pg.mouse.get_pos()

    # --- Again 按鈕（尚未按 Ready 才顯示）---
    if not client.ready_offer_started:
        ready_surface = gs.FONT_SIZE.render("Again?", True, gs.WHITE)
        ready_rect = ready_surface.get_rect(center=(gs.WIDTH / 2 + 100, gs.HEIGHT / 2 + 200))
        is_hover_ready = ready_rect.collidepoint(mouse_x, mouse_y)
        text_color = gs.HOVAR if is_hover_ready else gs.WHITE
        ready_surface = gs.FONT_SIZE.render("Again?", True, text_color)
        screen.blit(ready_surface, ready_rect)

    # --- Lobby 按鈕（無論是否已按 Ready 都顯示）---
    exit_surface = gs.FONT_SIZE.render("lobby", True, gs.WHITE)
    exit_rect = exit_surface.get_rect(center=(gs.WIDTH / 2 - 100, gs.HEIGHT / 2 + 200))
    is_hover_exit = exit_rect.collidepoint(mouse_x, mouse_y)
    text_color_exit = gs.HOVAR if is_hover_exit else gs.WHITE
    exit_surface = gs.FONT_SIZE.render("lobby", True, text_color_exit)
    screen.blit(exit_surface, exit_rect)

    # --- 處理事件：點擊 quit / again / lobby ---
    for event in pg.event.get():
        if event.type == pg.QUIT:
            handle_quit()

        elif event.type == pg.MOUSEBUTTONDOWN:
            if ready_rect and ready_rect.collidepoint(mouse_x, mouse_y):
                client.ready_mode = "again"  # 前端標記為 Again 模式
                return

            elif exit_rect.collidepoint(mouse_x, mouse_y):
                client.ready_mode = "lobby"
                handle_quit_to_lobby(screen, client)
