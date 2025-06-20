# login_ui.py
import pygame as pg
import time
import asyncio
import settings.game_settings as gs
import settings.context as ct
from Controllers.login_controller import login_to_control

WHITE, BLACK, BLUE = gs.WHITE, gs.BLACK, gs.LOGIN_BLUE
RED = gs.ERROR_RED
color_inactive = pg.Color('lightskyblue3')
color_active = pg.Color('dodgerblue2')

box_width, box_height = gs.LOGIN_BOX_WIDTH, gs.LOGIN_BOX_HEIGHT
gap = gs.LOGIN_GAP
center_x = gs.WIDTH // 2 - box_width // 2 + gs.center_x_offset
center_y = gs.HEIGHT // 2 - box_height * 2

input_box_user = pg.Rect(center_x, center_y, box_width, box_height)
input_box_pass = pg.Rect(center_x, center_y + box_height + gap, box_width, box_height)
login_button = pg.Rect(center_x, center_y + 2 * (box_height + gap), box_width, box_height)

async def login_screen(screen):
    clock = pg.time.Clock()
    user_text, pass_text = '', ''
    active_user, active_pass = True, False
    message = ''
    running = True
    clicked_login = False

    while running:
        screen.fill(gs.BLACK)
        mouse_pos = pg.mouse.get_pos()

        # 遊戲標題
        title_surface = gs.BIG_FONT_SIZE.render("Whack Legends", True, WHITE)
        title_rect = title_surface.get_rect(center=(gs.WIDTH // 2, 130))
        screen.blit(title_surface, title_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit(); exit()
            elif event.type == pg.MOUSEBUTTONDOWN:
                active_user = input_box_user.collidepoint(event.pos)
                active_pass = input_box_pass.collidepoint(event.pos)
                if login_button.collidepoint(event.pos):
                    clicked_login = True
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_TAB:
                    active_user, active_pass = not active_user, not active_pass
                elif event.key == pg.K_RETURN:
                    clicked_login = True
                else:
                    if active_user:
                        user_text = user_text[:-1] if event.key == pg.K_BACKSPACE else user_text + event.unicode
                    elif active_pass:
                        pass_text = pass_text[:-1] if event.key == pg.K_BACKSPACE else pass_text + event.unicode

        if clicked_login:
            clicked_login = False
            try:
                # 關閉舊連線（若存在）
                if ct.shared_client and ct.shared_client.ws_conn:
                    await ct.shared_client.ws_conn.close()

                client = await login_to_control(user_text, pass_text)

                if client and client.server_list:
                    ct.shared_client = client
                    await client.connect_to_server()
                    return client
                else:
                    message = "登入失敗，請確認帳號密碼或伺服器連線"
            except Exception as e:
                message = f"錯誤：{str(e)}"

        # 顯示輸入框與提示文字
        label_user = gs.SMALL_FONT_SIZE.render("Username:", True, BLUE)
        label_pass = gs.SMALL_FONT_SIZE.render("Password:", True, BLUE)
        screen.blit(label_user, (input_box_user.x - label_user.get_width() - 10, input_box_user.y + 10))
        screen.blit(label_pass, (input_box_pass.x - label_pass.get_width() - 10, input_box_pass.y + 10))

        pg.draw.rect(screen, color_active if active_user else color_inactive, input_box_user, 2)
        pg.draw.rect(screen, color_active if active_pass else color_inactive, input_box_pass, 2)
        screen.blit(gs.SMALL_FONT_SIZE.render(user_text, True, WHITE), (input_box_user.x + 5, input_box_user.y + 5))
        screen.blit(gs.SMALL_FONT_SIZE.render('*' * len(pass_text), True, WHITE), (input_box_pass.x + 5, input_box_pass.y + 5))

        # login 按鈕
        btn_color = gs.HOVAR if login_button.collidepoint(mouse_pos) else gs.LOGIN_BUTTON_COLOR
        pg.draw.rect(screen, btn_color, login_button)
        btn_text = gs.SMALL_FONT_SIZE.render("login", True, WHITE)
        screen.blit(btn_text, (login_button.centerx - btn_text.get_width() // 2,
                               login_button.centery - btn_text.get_height() // 2))

        if message:
            msg_surface = gs.SMALL_FONT_SIZE.render(message, True, RED)
            screen.blit(msg_surface, (gs.WIDTH // 2 - msg_surface.get_width() // 2, login_button.y + 60))

        pg.display.flip()
        clock.tick(30)
