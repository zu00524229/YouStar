import pygame as pg
import asyncio
from UI.client import GameClient
import time
import settings.game_settings as gs
import UI.game_lobby as lob
import UI.game_play_ui as pl
import UI.game_gameover_ui as ov
import UI.login_ui as log
import websockets

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

def run_game_loop(screen, client):
    running = True
    clock = pg.time.Clock()

    while running:
        events = pg.event.get()
        for event in events:
            if event.type == pg.QUIT:
                handle_quit()

        state = client.sync_game_state()
        current_game_state = state["game_state"]
        current_players = state["current_players"]
        current_remaining_time = state["remaining_time"]
        current_loading_time = state["loading_time"]
        leaderboard_data = state["leaderboard_data"]
        score = state["score"]

        screen.fill(gs.BLACK)

        if current_game_state in ["waiting", "loading", "playing", "gameover"]:
            player_count(screen, current_players)

        if current_game_state == "waiting":
            waiting_surface = gs.FONT_SIZE.render("Waiting for players...", True, gs.WHITE)
            waiting_rect = waiting_surface.get_rect(center=(gs.WIDTH / 2, gs.HEIGHT / 2))
            screen.blit(waiting_surface, waiting_rect)

        elif current_game_state == "loading":
            draw_loading_screen(screen, current_loading_time)

        elif current_game_state == "playing":
            pl.draw_playing_screen(screen, state, score, leaderboard_data, current_remaining_time)
            pl.handle_playing_events(state, client, score, handle_quit)

        elif current_game_state == "gameover":
            ov.draw_gameover_screen(screen, leaderboard_data, handle_quit, client, handle_quit_to_lobby)

        pg.display.flip()
        clock.tick(60)

    return "end"


def draw_loading_screen(screen, current_loading_time):
    loading_surface = gs.FONT_SIZE.render(f"Loading..{current_loading_time} s", True, gs.WHITE)
    loading_rect = loading_surface.get_rect(center = (gs.WIDTH / 2, gs.HEIGHT / 2))
    screen.blit(loading_surface, loading_rect)

    for event in pg.event.get():
        if event.type == pg.QUIT:
            handle_quit()

def draw_ready_offer_ui(screen, client, events):
    ready_surface = gs.BIG_FONT_SIZE.render(
        f"ready? {client.ready_offer_remaining_time} s", True, (255, 165, 0))
    screen.blit(ready_surface, ready_surface.get_rect(center=(gs.WIDTH / 2, gs.HEIGHT / 2 - 120)))

    joined_count = len(client.ready_offer_joined_players)
    joined_text = f"{joined_count} player{'s' if joined_count != 1 else ''} ready"
    joined_surface = gs.FONT_SIZE.render(joined_text, True, gs.WHITE)
    screen.blit(joined_surface, joined_surface.get_rect(center=(gs.WIDTH / 2, gs.HEIGHT / 2 - 60)))

    mouse_x, mouse_y = pg.mouse.get_pos()

    join_rect = pg.Rect(gs.WIDTH / 2 - 140, gs.HEIGHT / 2 + 30, 80, 40)
    skip_rect = pg.Rect(gs.WIDTH / 2 + 60, gs.HEIGHT / 2 + 30, 80, 40)

    join_color = (100, 200, 255) if join_rect.collidepoint(mouse_x, mouse_y) else gs.WHITE
    skip_color = (255, 100, 100) if skip_rect.collidepoint(mouse_x, mouse_y) else gs.WHITE

    join_text = gs.FONT_SIZE.render("ready", True, join_color)
    skip_text = gs.FONT_SIZE.render("Watch", True, skip_color)

    screen.blit(join_text, join_rect.move(10, 10))
    screen.blit(skip_text, skip_rect.move(10, 10))

    for event in events:
        if event.type == pg.MOUSEBUTTONDOWN:
            if join_rect.collidepoint(mouse_x, mouse_y):
                print("[前端] 玩家選擇參加 ready，發送 join_ready")
                client.send_join_ready()
            elif skip_rect.collidepoint(mouse_x, mouse_y):
                print("[前端] 玩家選擇跳過 ready（觀戰）")

