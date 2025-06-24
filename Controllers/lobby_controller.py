# lobby_controller.py : 控制大廳邏輯整合
import pygame as pg
import settings.game_settings as gs
from UI.game_lobby import render_server_status_ui, draw_lobby_title_and_hint


# 處理玩家選擇 GameServer 的事件（滑鼠點擊
async def handle_server_selection(event, server_buttons, client):
    mouse_x, mouse_y = event.pos

    # 檢查點到的是哪一台伺服器
    for rect, url in server_buttons:
        if rect.collidepoint(mouse_x, mouse_y):
            # print(f"[Lobby] 玩家選擇連線到 GameServer: {url}")
            # print(f"[Debug] 點擊連線時拿到的 url = {url}, 類型 = {type(url)}")
            # print(f"[Debug] 當前 client.username 是：{client.username}，型別為：{type(client.username)}")
            client.server_url = url

            print(f"[Lobby] 玩家選擇連線到 GameServer: {url}")
            await client.connect_to_server()    # 呼叫 client 的方法 選擇指定的 GameServer 連線
            await client.start_ws_receiver()    # 呼叫 client 方法 判斷是否可連線
            print(f"[Lobby] 玩家點選 GameServer，呼叫 start_ws_receiver()，client ID: {id(client)}")

            # 呼叫前端狀態同步方法（例如取得遊戲階段等
            if hasattr(client, "sync_game_state") and callable(client.sync_game_state):
                result = client.sync_game_state()
                if hasattr(result, "__await__"):
                    await result

            return "play"    # 告知主畫面可以切換到遊戲畫面

# 顯示 GameServer 清單的 lobby 畫面主迴圈
async def show_lobby(screen, client, handle_quit):
    print("[Debug] show_lobby() 被呼叫")
    pg.display.set_caption("Whack Legends")
    lobby_running = True

    # 取得可用伺服器清單（來自中控 ControlServer）
    server_list = await client.get_server_list()

    while lobby_running:
        screen.fill(gs.BLACK)       # 清空畫面
        server_buttons = []         # 儲存每個 server 對應的框與 URL
        mouse_x, mouse_y = pg.mouse.get_pos()

       # 畫出大廳標題與提示文字
        draw_lobby_title_and_hint(screen)

        # 遍歷每個 GameServer，畫出狀態方框
        for i, server in enumerate(server_list):
            # print(f"[Debug] server = {server}")
            # 取得位置並畫出伺服器資訊 UI，回傳框的位置
            box_rect = render_server_status_ui(screen, server, 150 + i * 100, mouse_x, mouse_y, i)
            server_buttons.append((box_rect, server["server_url"]))

        # 處理玩家的鍵盤 / 滑鼠事件
        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()   # 玩家按下關閉視窗 → 呼叫外部 handle_quit 結束程式

            elif event.type == pg.KEYDOWN and event.key == pg.K_r:
                # 玩家按下 R 鍵 → 重新取得 server 清單
                print("[Lobby] 玩家按下 R，重新取得 server list")
                server_list = await client.get_server_list()

            elif event.type == pg.MOUSEBUTTONDOWN:
                # print("[Debug] Mouse click detected!")
                # 玩家點擊其中一台 GameServer
                result = await handle_server_selection(event, server_buttons, client)
                if result == "play":
                    return "play"   # 切換到遊戲畫面主流程

        # 更新畫面並維持 30 FPS
        pg.display.flip()
        pg.time.Clock().tick(30)
