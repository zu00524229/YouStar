# game_waiting.py
import pygame as pg
# import asyncio
import settings.game_settings as gs
import settings.animation as ani

def draw_waiting_screen(screen, events, client):
    ready_clicked = False
    go_lobby_clicked = False    # 初始設回False
    # === 背景文字 ===
    waiting_surface = gs.CH_MC_SIZE.render("準備啟動...", True, gs.WHITE)
    waiting_rect = waiting_surface.get_rect(center=(gs.WIDTH / 2, gs.HEIGHT / 2 - 100))
    screen.blit(waiting_surface, waiting_rect)

    # === 教學說明（中文 + 置中） ===
    tutorial_text = [
        "歡迎來到打地鼠遊戲！",
        "點擊地鼠來獲得分數。",
        "小心炸彈地鼠，金色會加高分！",
        "或是想試試手氣，褐色的賭博地鼠!",
        "準備好就按下『Ready』吧！"
    ]

    for i, line in enumerate(tutorial_text):
        tutorial_surface = gs.CH_MC_SIZE.render(line, True, gs.WHITE)
        tutorial_rect = tutorial_surface.get_rect(center=(gs.WIDTH // 2, gs.HEIGHT // 2 - 50 + i * 35))
        screen.blit(tutorial_surface, tutorial_rect)

    # === 地鼠種類與分數顯示（底部說明） ===
    start_x = 120           # 每個地鼠說明的起始 x 位置
    y = 80                  # 垂直位置（畫面頂部往下 80 像素）
    spacing = 140           # 每組圓形 + 文字之間的水平距離
    radius = 15             # 圓形半徑，越大圓越大，可以調整這個數字來改大小

    for i, mole in enumerate(gs.MOLE_TYPES):
        x = start_x + i * spacing
        pg.draw.circle(screen, mole["color"], (x, y), radius)
        score = mole.get("score_range", mole["score"])  # 小丑地鼠用 -15~15 顯示
        score_str = f"{score[0]}~{score[1]}" if isinstance(score, tuple) else f"{score:+d}"
        text = f" : {score_str}"
        text_surface = gs.SMALL_FONT_SIZE.render(text, True, gs.WHITE)
        screen.blit(text_surface, (x + 20, y - 10)) # 文字在圓形右側水平對齊
        
    # === Ready 按鈕區域 ===
    button_width, button_height = 100, 30
    # Ready 按鈕位置往左移
    ready_button = pg.Rect(
        gs.WIDTH // 2 - 120,     # 向左偏移
        gs.HEIGHT // 2 + 140,
        button_width,
        button_height
    )
    mouse_pos = pg.mouse.get_pos()
    is_hover = ready_button.collidepoint(mouse_pos)

    # 按鈕顏色與繪製
    button_color = gs.HOVAR if is_hover else gs.GREEN
    pg.draw.rect(screen, button_color, ready_button, border_radius=12)

    # 按鈕文字（置中）
    btn_text = gs.SMALL_FONT_SIZE.render("Ready", True, gs.WHITE)
    btn_rect = btn_text.get_rect(center=ready_button.center)
    screen.blit(btn_text, btn_rect)

    # === LOBBY 按鈕 ===
    # Lobby 按鈕位置往右移
    lobby_button = pg.Rect(
        gs.WIDTH // 2 + 20,      # 向右偏移
        gs.HEIGHT // 2 + 140,
        100,
        30
    )

    is_hover_lobby = lobby_button.collidepoint(mouse_pos)
    pg.draw.rect(screen, gs.HOVAR if is_hover_lobby else gs.WHITE, lobby_button, border_radius=12)
    lobby_text = gs.SMALL_FONT_SIZE.render("Lobby", True, gs.BLACK)
    screen.blit(lobby_text, lobby_text.get_rect(center=lobby_button.center))

    # === 處理滑鼠點擊 Ready 按鈕 ===
    for event in events:
        if event.type == pg.MOUSEBUTTONDOWN:
            if ready_button.collidepoint(event.pos):
                if client.is_watching:
                    print("[提示] 觀戰者不能按 Ready，請返回大廳重新加入")
                    ani.set_message("請回大廳重新加入成為玩家或等待新玩家加入")  # 顯示視覺訊息
                else:
                    print("[前端] 玩家按下 Ready")
                    ready_clicked = True
                    client.send_ready()
                print("[前端] Ready 已發送給後端")
            elif lobby_button.collidepoint(event.pos):
                print("[前端] 玩家選擇返回lobby")
                client.disconnect_from_server()
                go_lobby_clicked = True
    
    if go_lobby_clicked:
        return "lobby"
    return ready_clicked
