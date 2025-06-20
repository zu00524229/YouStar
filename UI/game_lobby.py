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
        "gameover": "Game Over"
    }
    status_text = f"({server['current_players']}/{server['max_players']})   Status: {phase_map.get(server['game_phase'], server['game_phase'])}"
    status_surface = pg.font.SysFont(None, 32).render(status_text, True, (200, 200, 200))
    surface.blit(status_surface, (box_x + 20, box_y + 45))

    return box_rect

def draw_lobby_title_and_hint(surface):
    title_surface = gs.BIG_FONT_SIZE.render("Game Lobby", True, gs.WHITE)
    surface.blit(title_surface, title_surface.get_rect(center=(gs.WIDTH / 2, 80)))

    hint_surface = pg.font.SysFont(None, 28).render("Click to join. Press R to refresh.", True, (150, 150, 150))
    surface.blit(hint_surface, hint_surface.get_rect(center=(gs.WIDTH / 2, gs.HEIGHT - 50)))
