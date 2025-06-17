# game.py : 遊戲主程式
import pygame as pg
# import random
import asyncio
from UI.client import GameClient
import time
import settings.game_settings as gs
import UI.game_lobby as lob
import UI.game_play_ui as play_ui
import UI.game_gameover_ui as gameover_ui
import UI.login_ui as log
import websockets

# 啟動 GameClient → 負責與 ControlServer + GameServer 通訊
# client = GameClient("player1", "1234")
# client.start()

# 初始化 pygame 畫面
pg.init()

# 使用 login.py 登入介面獲得 client
client = log.login_screen()
client.start_ws_receiver()
# client.start()  # 記得這是正式啟動連線與 ws_receiver 的地方！


screen = pg.display.set_mode((gs.WIDTH, gs.HEIGHT))
pg.display.set_caption("Whack Legends")

running = True
clock = pg.time.Clock()


# _original_connect = websockets.connect

# def debug_connect(uri, *args, **kwargs):
#     print(f"[debug patch] websockets.connect 被呼叫，URI = {uri!r}")
#     return _original_connect(uri, *args, **kwargs)

# websockets.connect = debug_connect


# 處理退出遊戲
def handle_quit():
    global running
    running = False
    print("[前端] 玩家關閉視窗，離開遊戲。")
    pg.quit()   # 主動呼叫 pg.quit()，不用靠最後一行
    exit()

def safely_close_client(client):
    try:
        if client.ws_conn:
            loop = client.ws_conn.loop  # 拿到 ws_conn 所屬的 loop
            loop.call_soon_threadsafe(asyncio.create_task, client.ws_conn.close())
            print("[debug] 已要求關閉 client WebSocket")
    except Exception as e:
        print(f"[debug] 關閉 WebSocket 發生錯誤: {e}")


# === 返回主大廳，保持 game 開啟 ===
def handle_quit_to_lobby(screen, client):
    safely_close_client(client)  # 改為同步呼叫
    # --- 強制中斷與 GameServer 的連線（或重設）
    # asyncio.run(safely_close_client(client))  # 確保連線被清掉
    client.ws_conn = None
    client.ws_started = False  # 重設讓下一場可以再啟用 receiver
    client.ready_offer_started = False
    client.ready_offer_joined_players = set()
    
    # --- 返回 lobby 畫面
    lob.show_lobby(screen, client, handle_quit)


# 當前機台玩家人數
def player_count(surface, current_players):
    players_surface = gs.FONT_SIZE.render(f"Players: {current_players}", True, (255, 255, 0))
    players_rect = players_surface.get_rect(bottomright=(gs.WIDTH - 20, gs.HEIGHT - 20))  # 右下角
    surface.blit(players_surface, players_rect)

while not client.login_success:
    print("[大廳] 等待登入完成...")
    time.sleep(0.1)

lob.show_lobby(screen, client, handle_quit)  # 秀遊戲大廳
# 遊戲主迴圈
while running:
    # === 遊戲狀態同步 ===
    state = client.sync_game_state()

    # 遊戲階段 & 時間
    current_game_state = state["game_state"]
    current_players = state["current_players"]
    current_remaining_time = state["remaining_time"]
    current_loading_time = state["loading_time"]

    # 一般地鼠
    current_mole_id = state["current_mole_id"]
    current_mole_position = state["current_mole_position"]
    current_mole_type_name = state["current_mole_type_name"]
    mole_active = state["mole_active"]

    # 特殊地鼠
    current_special_mole_position = state["current_special_mole_position"]
    current_special_mole_type_name = state["current_special_mole_type_name"]
    special_mole_active = state["special_mole_active"]

    
    # 分數與排行榜
    leaderboard_data = state["leaderboard_data"]
    score = state["score"]

    # 時間顯示
    time_surface = gs.FONT_SIZE.render(f"Time: {current_remaining_time}s", True, gs.WHITE)

    screen.fill(gs.BLACK)

# =============================================================================== #
    # === 畫面顯示 ===
    # 當前玩家人數
    if current_game_state in ["waiting", "loading", "playing", "gameover"]:
        player_count(screen, current_players)
    if current_game_state == "waiting":
        # 等待玩家進入
        waiting_surface = gs.FONT_SIZE.render(f"Waiting for players...", True, gs.WHITE)
        waiting_rect = waiting_surface.get_rect(center = (gs.WIDTH / 2, gs.HEIGHT / 2))
        screen.blit(waiting_surface, waiting_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

    # 遊戲結束時畫面
    if current_game_state == "gameover":
        gameover_ui.draw_gameover_screen(screen, leaderboard_data, handle_quit, client, handle_quit_to_lobby)

    # loading 倒數畫面
    elif current_game_state == "loading":
        loading_surface = gs.FONT_SIZE.render(f"Loading..{current_loading_time} s", True, gs.WHITE)
        loading_rect = loading_surface.get_rect(center = (gs.WIDTH / 2, gs.HEIGHT / 2))
        screen.blit(loading_surface, loading_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

    # 遊戲中畫面
    if current_game_state == "playing":
        play_ui.draw_playing_screen(screen, state, score, leaderboard_data, current_remaining_time)
        play_ui.handle_playing_events(state, client, score, handle_quit)

    if client.ready_offer_remaining_time > 0:
        # 倒數時間
        ready_offer_surface = gs.BIG_FONT_SIZE.render(
            f"ready? {client.ready_offer_remaining_time} s", True, (255, 165, 0))
        ready_offer_rect = ready_offer_surface.get_rect(center=(gs.WIDTH / 2, gs.HEIGHT / 2 - 120))
        screen.blit(ready_offer_surface, ready_offer_rect)

        # 顯示人數
        joined_count = len(client.ready_offer_joined_players)
        joined_text = f"{joined_count} player{'s' if joined_count != 1 else ''} ready"
        joined_surface = gs.FONT_SIZE.render(joined_text, True, (gs.WHITE))
        joined_rect = joined_surface.get_rect(center=(gs.WIDTH / 2, gs.HEIGHT / 2 - 60))
        screen.blit(joined_surface, joined_rect)

        # 滑鼠位置
        mouse_x, mouse_y = pg.mouse.get_pos()

        # ready 按鈕
        join_text = "ready"
        join_surface = gs.FONT_SIZE.render(join_text, True, (gs.WHITE))
        join_rect = join_surface.get_rect(center=(gs.WIDTH / 2 - 100, gs.HEIGHT / 2 + 50))
        is_hover_join = join_rect.collidepoint(mouse_x, mouse_y)            # hover 效果
        join_color = (100, 200, 255) if is_hover_join else (gs.WHITE)  # hover 顏色
        join_surface = gs.FONT_SIZE.render(join_text, True, join_color)
        screen.blit(join_surface, join_rect)

        # Watch 按鈕
        skip_text = "Watch"
        skip_surface = gs.FONT_SIZE.render(skip_text, True, (gs.WHITE))
        skip_rect = skip_surface.get_rect(center=(gs.WIDTH / 2 + 100, gs.HEIGHT / 2 + 50))
        is_hover_skip = skip_rect.collidepoint(mouse_x, mouse_y)            # hover 效果
        skip_color = (255, 100, 100) if is_hover_skip else (gs.WHITE)  # hover 顏色
        skip_surface = gs.FONT_SIZE.render(skip_text, True, skip_color)
        screen.blit(skip_surface, skip_rect)

        # 處理 ready Offer 按鈕點擊
        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

            elif event.type == pg.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pg.mouse.get_pos()
                if join_rect.collidepoint(mouse_x, mouse_y):
                    print("[前端] 玩家選擇參加 ready，發送 join_ready")
                    client.send_join_ready()
                elif skip_rect.collidepoint(mouse_x, mouse_y):
                    print("[前端] 玩家選擇跳過 ready（觀戰）")



    # 畫面更新
    pg.display.flip()
    clock.tick(60)

# 遊戲結束
pg.quit()
