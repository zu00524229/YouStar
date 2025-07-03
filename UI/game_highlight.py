
import settings.game_settings as gs
import time
import pygame as pg

# 破紀錄廣播
def show_highlight(screen, client):
    if client.highlight_message and time.time() - client.highlight_time < 5:    # 顯示秒數 5 秒
        font = gs.CH_MC_SIZE
        text_surface = font.render(client.highlight_message, True, (255, 0, 0))  # 紅字

        text_width = text_surface.get_width()
        text_height = text_surface.get_height()

        # 畫黃色背景框（比文字大一點）
        bar_height = text_height + 20 # 上下 padding 各 10 px
        bar_rect = pg.Rect(0, 0, gs.WIDTH, bar_height)

        pg.draw.rect(screen, gs.YELLOW, bar_rect)  # 黃底

        text_x = (gs.WIDTH - text_width) // 2
        text_y = 10
        # 把紅字畫上去
        screen.blit(text_surface, (text_x, text_y))