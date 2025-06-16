# game.py 遊戲結束畫面
import pygame as pg
import settings.game_settings as gs

def draw_gameover_screen(screen, leaderboard_data, handle_quit, client):
    # 畫面標題
    leaderboard_surface = gs.BIG_FONT_SIZE.render("Leaderboard", True, gs.WHITE)
    leaderboard_rect = leaderboard_surface.get_rect(center=(gs.WIDTH / 2, 70))
    screen.blit(leaderboard_surface, leaderboard_rect)

    # 畫排行榜前五名
    for idx, entry in enumerate(leaderboard_data[:5]):
        text = f"{idx + 1} {entry['username']} - {entry['score']}"
        entry_surface = gs.FONT_SIZE.render(text, True, gs.WHITE)
        screen.blit(entry_surface, (gs.WIDTH / 2 - 120, 100 + idx * 50))

    # Exit 按鈕
    exit_surface = gs.FONT_SIZE.render("Exit", True, (255, 255, 255))
    exit_rect = exit_surface.get_rect(center=(gs.WIDTH / 2 - 100, gs.HEIGHT / 2 + 200))
    pg.draw.rect(screen, (100, 100, 100), exit_rect.inflate(20, 10))
    screen.blit(exit_surface, exit_rect)

    # Replay 按鈕
    replay_surface = gs.FONT_SIZE.render("Play Again", True, (255, 255, 255))
    replay_rect = replay_surface.get_rect(center=(gs.WIDTH / 2 + 100, gs.HEIGHT / 2 + 200))
    pg.draw.rect(screen, (100, 100, 100), replay_rect.inflate(20, 10))
    screen.blit(replay_surface, replay_rect)

    # Hover 效果
    mouse_x, mouse_y = pg.mouse.get_pos()
    is_hover_exit = exit_rect.collidepoint(mouse_x, mouse_y)
    exit_box_color = (150, 150, 150) if is_hover_exit else (100, 100, 100)
    pg.draw.rect(screen, exit_box_color, exit_rect.inflate(20, 10))
    screen.blit(exit_surface, exit_rect)

    is_hover_replay = replay_rect.collidepoint(mouse_x, mouse_y)
    replay_box_color = (150, 150, 150) if is_hover_replay else (100, 100, 100)
    pg.draw.rect(screen, replay_box_color, replay_rect.inflate(20, 10))
    screen.blit(replay_surface, replay_rect)

    # 處理事件
    for event in pg.event.get():
        if event.type == pg.QUIT:
            handle_quit()

        elif event.type == pg.MOUSEBUTTONDOWN:
            if exit_rect.collidepoint(mouse_x, mouse_y):
                handle_quit()
            elif replay_rect.collidepoint(mouse_x, mouse_y):
                print("[前端] 玩家選擇 Play Again，發送 replay")
                client.send_replay()
                with client.state_lock:
                    client.score = 0
