# login 遊戲登入畫面 login_ui.py
import pygame as pg
from UI.client import GameClient
import time
import json
import asyncio
import websockets
import settings.game_settings as gs
import settings.context as ct

pg.init()

screen = pg.display.set_mode((gs.WIDTH, gs.HEIGHT))
pg.display.set_caption("Whack Legends")

# FONT = gs.FONT_SIZE
WHITE, BLACK, BLUE = gs.WHITE, gs.BLACK, gs.LOGIN_BLUE
color_inactive = pg.Color('lightskyblue3')
color_active = pg.Color('dodgerblue2')
RED = gs.ERROR_RED

box_width, box_height = gs.LOGIN_BOX_WIDTH, gs.LOGIN_BOX_HEIGHT
gap = gs.LOGIN_GAP

# 動態置中
center_x = gs.WIDTH // 2 - box_width // 2 + gs.center_x_offset
center_y = gs.HEIGHT // 2 - box_height * 2

input_box_user = pg.Rect(center_x, center_y, box_width, box_height)
input_box_pass = pg.Rect(center_x, center_y + box_height + gap, box_width, box_height)
login_button = pg.Rect(center_x, center_y + 2 * (box_height + gap), box_width, box_height)


clock = pg.time.Clock()

def login_screen():
    user_text, pass_text = '', ''
    active_user, active_pass = True, False
    message = ''
    running = True

    while running:
        screen.fill(gs.BLACK)
        mouse_pos = pg.mouse.get_pos()

        # --- 顯示遊戲標題 ---
        title_text = "Whack Legends"
        title_surface = gs.BIG_FONT_SIZE.render(title_text, True, WHITE)
        title_rect = title_surface.get_rect(center=(gs.WIDTH // 2, 130))
        screen.blit(title_surface, title_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                exit()

            elif event.type == pg.MOUSEBUTTONDOWN:
                active_user = input_box_user.collidepoint(event.pos)
                active_pass = input_box_pass.collidepoint(event.pos)

                if login_button.collidepoint(event.pos):
                    clicked_login = True
                else:
                    clicked_login = False

            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_TAB:
                    active_user, active_pass = not active_user, not active_pass
                    clicked_login = False

                elif event.key == pg.K_RETURN:
                    clicked_login = True
                else:
                    clicked_login = False

                    if active_user:
                        if event.key == pg.K_BACKSPACE:
                            user_text = user_text[:-1]
                        else:
                            user_text += event.unicode
                    elif active_pass:
                        if event.key == pg.K_BACKSPACE:
                            pass_text = pass_text[:-1]
                        else:
                            pass_text += event.unicode
            else:
                clicked_login = False

            # === 登入流程整合處理 ===
            if clicked_login:
                clicked_login = False
                client = login_to_control(user_text, pass_text)
                if client and client.server_list:
                    print(f"[Debug] 登入後的 client.server_list 有幾台: {len(client.server_list)}")
                    # client.assigned_server = client.server_list[0]["server_url"]
                    client.server_url = client.server_list[0]["server_url"]
                    client.start_ws_receiver()
                    return client
                elif client:
                    print("[錯誤] 無可用 GameServer")
                    message = "No available game server. Please try again later."
                else:
                    message = "Login failed. Please check your username or password."

        # 計算提示字寬度，用來做右對齊
        label_user_text = "Username:"
        label_pass_text = "Password:"
        label_user = gs.SMALL_FONT_SIZE.render(label_user_text, True, BLUE)
        # label_user = gs.BIG_FONT_SIZE.render(label_user_text, True, BLUE)
        label_pass = gs.SMALL_FONT_SIZE.render(label_pass_text, True, BLUE)
        # label_pass = gs.BIG_FONT_SIZE.render(label_pass_text, True, BLUE)

        label_offset = 10  # 字與框之間的距離

        # 提示文字 X 位置靠右對齊輸入框左邊
        label_user_x = input_box_user.x - label_user.get_width() - label_offset
        label_pass_x = input_box_pass.x - label_pass.get_width() - label_offset

        # Y 對齊到框框中間（向下偏 5 看起來會剛好）
        screen.blit(label_user, (label_user_x, input_box_user.y + 10))
        screen.blit(label_pass, (label_pass_x, input_box_pass.y + 10))

        hover_login = login_button.collidepoint(mouse_pos)
        btn_color = (30, 130, 230) if hover_login else gs.LOGIN_BUTTON_COLOR
        pg.draw.rect(screen, btn_color, login_button)

        # 輸入框與文字
        pg.draw.rect(screen, color_active if active_user else color_inactive, input_box_user, 2)
        pg.draw.rect(screen, color_active if active_pass else color_inactive, input_box_pass, 2)
        screen.blit(gs.SMALL_FONT_SIZE.render(user_text, True, WHITE), (input_box_user.x + 5, input_box_user.y + 5))
        screen.blit(gs.SMALL_FONT_SIZE.render('*' * len(pass_text), True, WHITE), (input_box_pass.x + 5, input_box_pass.y + 5))

        # 登入按鈕
        pg.draw.rect(screen, gs.LOGIN_BUTTON_COLOR, login_button)
        btn_text = gs.SMALL_FONT_SIZE.render("login", True, WHITE)
        screen.blit(btn_text, (login_button.centerx - btn_text.get_width() // 2,
                               login_button.centery - btn_text.get_height() // 2))

        # 錯誤訊息
        if message:
            msg_surface = gs.SMALL_FONT_SIZE.render(message, True, RED)
            screen.blit(msg_surface, (gs.WIDTH // 2 - msg_surface.get_width() // 2, login_button.y + 60))

        pg.display.flip()
        clock.tick(30)


_control_loop = None  # 全域事件迴圈，只初始化一次

def login_to_control(username, password):
    global _control_loop

    if not _control_loop:
        _control_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_control_loop)

    client = GameClient(username, password)
    _control_loop.run_until_complete(_login_async(client))
    # print(f"[Debug] login_to_control 結束時 client.server_list 長這樣：{client.server_list}")
    return client if client.login_success else None


async def _login_async(client):
    try:
        async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
            await ws.send(json.dumps({
                "type": "login",
                "username": client.username,
                "password": client.password
            }))

            response = await ws.recv()
            data = json.loads(response)

            if data.get("type") == "login_response" and data.get("success"):
                print(f"[前端] 登入成功，準備取得 GameServer 列表")
                client.login_success = True

                await ws.send(json.dumps({"type": "get_server_list"}))
                response = await ws.recv()
                data = json.loads(response)

                if data.get("type") == "get_server_list_response":
                    client.server_list = data.get("server_list", [])
                    # print(f"[Debug] client.server_list = {client.server_list}")
                    print(f"[前端] 取得 GameServer 列表，共 {len(client.server_list)} 台：")
                    for i, server in enumerate(client.server_list):
                        print(f"  [{i}] {server['server_url']} | players: {server['current_players']}/{server['max_players']} | phase: {server['game_phase']}")

            else:
                print(f"[前端] 登入失敗: {data.get('reason')}")

    except Exception as e:
        if "received 1000" in str(e):
            print(f"[登入] login_async 正常結束 (code 1000)，不視為錯誤")
        else:
            print(f"[登入] 發生錯誤: {e}")
