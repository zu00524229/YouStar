# UI/lobby_ui.py
import pygame as pg
import settings.game_settings as gs


def render_server_status_ui(surface, server, box_y, mouse_x, mouse_y, index):
    box_width = 600
    box_height = 80
    box_x = (gs.WIDTH - box_width) // 2
    box_rect = pg.Rect(box_x, box_y, box_width, box_height)

    # Hover 效果
    is_hover = box_rect.collidepoint(mouse_x, mouse_y)
    box_color = gs.HOVAR if is_hover else (60, 60, 60)

    # 畫框與邊線
    pg.draw.rect(surface, box_color, box_rect)
    pg.draw.rect(surface, (200, 200, 200), box_rect, 2)

    # 顯示文字
    server_name_surface = gs.FONT_SIZE.render(f"GameServer {index + 1}", True, gs.WHITE)
    surface.blit(server_name_surface, (box_x + 20, box_y + 10))

    phase_map = {
        "waiting": "Waiting",
        "loading": "Loading",
        "ready": "Ready",
        "playing": "Playing",
        "gameover": "Game Over",
        "post_gameover": "Post GameOver"
    }

    status_text = f"({server['current_players']}/{server['max_players']})   Status: {phase_map.get(server['game_phase'], server['game_phase'])}"
    status_surface = pg.font.SysFont(None, 32).render(status_text, True, (200, 200, 200))
    surface.blit(status_surface, (box_x + 20, box_y + 45))

    # 觀戰按鈕
    watch_button_rect = None
    if server["game_phase"] in ["playing", "gameover", "post_gameover"]:
        watching_players = server.get("watching_players", 0)
        watch_button_rect = draw_watch_button(surface, box_x + 480, box_y + 20, mouse_x, mouse_y, watching_players)

    # 回傳畫面區域 + 按鈕
    return box_rect, watch_button_rect

# 大廳標題
def draw_lobby_title_and_hint(surface):
    title_surface = gs.CH_MC_TITLE.render("遊戲大廳", True, gs.WHITE)
    surface.blit(title_surface, title_surface.get_rect(center=(gs.WIDTH / 2, 80)))

    hint_surface = pg.font.SysFont(None, 28).render("Click to join. Press R to refresh.", True, (150, 150, 150))
    surface.blit(hint_surface, hint_surface.get_rect(center=(gs.WIDTH / 2, gs.HEIGHT - 50)))



# 觀戰按鈕UI
def draw_watch_button(surface, x, y, mouse_x, mouse_y, watching_players=0):
    button_rect = pg.Rect(x, y, 100, 30)
    is_hovered = button_rect.collidepoint(mouse_x, mouse_y)

    color = (180, 180, 255) if is_hovered else (100, 100, 255)
    pg.draw.rect(surface, color, button_rect, border_radius=5)

    font = pg.font.SysFont(None, 24)
    text_surface = font.render("Watch", True, (255, 255, 255))
    surface.blit(text_surface, text_surface.get_rect(center=button_rect.center))

    #  顯示觀戰人數在按鈕右側 + 標籤
    if watching_players > 0:
        label_surface = font.render(f"({watching_players}) watch", True, (0, 255, 255))
        label_rect = label_surface.get_rect(midleft=(button_rect.right + 10, button_rect.centery))
        surface.blit(label_surface, label_rect)

    return button_rect


