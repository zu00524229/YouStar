# game_waiting.py
import pygame as pg
# import asyncio
import settings.game_settings as gs

def draw_waiting_screen(screen, events, client):
    ready_clicked = False
    # === 背景文字 ===
    waiting_surface = gs.FONT_SIZE.render("Waiting for players...", True, gs.WHITE)
    waiting_rect = waiting_surface.get_rect(center=(gs.WIDTH / 2, gs.HEIGHT / 2 - 100))
    screen.blit(waiting_surface, waiting_rect)

    # === 教學說明（中文 + 置中） ===
    tutorial_text = [
        "歡迎來到打地鼠遊戲！",
        "點擊地鼠來獲得分數。",
        "小心炸彈地鼠，金色與鑽石地鼠會加高分！",
        "準備好就按下『Ready』吧！"
    ]

    for i, line in enumerate(tutorial_text):
        tutorial_surface = gs.CH_FONT_SIZE.render(line, True, gs.WHITE)
        tutorial_rect = tutorial_surface.get_rect(center=(gs.WIDTH // 2, gs.HEIGHT // 2 - 50 + i * 35))
        screen.blit(tutorial_surface, tutorial_rect)
        
    # === Ready 按鈕區域 ===
    ready_button = pg.Rect(gs.WIDTH // 2 - 100, gs.HEIGHT // 2 + 110, 200, 60)
    mouse_pos = pg.mouse.get_pos()
    is_hover = ready_button.collidepoint(mouse_pos)

    # 按鈕顏色與繪製
    button_color = gs.HOVAR if is_hover else gs.GREEN
    pg.draw.rect(screen, button_color, ready_button)

    # 按鈕文字（置中）
    btn_text = gs.SMALL_FONT_SIZE.render("Ready", True, gs.WHITE)
    btn_rect = btn_text.get_rect(center=ready_button.center)
    screen.blit(btn_text, btn_rect)

    # === 處理滑鼠點擊 Ready 按鈕 ===
    for event in events:
        if event.type == pg.MOUSEBUTTONDOWN and ready_button.collidepoint(event.pos):
            print("[前端] 玩家按下 Ready")
            ready_clicked = True
            # asyncio.create_task(client.send_ready())
            client.send_ready()
            print("[前端] Ready 已發送給後端")
    
    return ready_clicked
