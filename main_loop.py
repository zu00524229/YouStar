# game_mainloop.py  遊戲主循環 與 loading
import pygame as pg
import asyncio
import UI.game_play_ui as pl
import UI.game_gameover_ui as ov
import settings.game_settings as gs

# 觀戰模式(未製作)
def run_watch_mode(screen, client):
    # 可用預設畫面或未來補上觀戰邏輯
    print("[前端] 進入觀戰模式，目前暫不支援。")
    return

def draw_loading_screen(screen, current_loading_time):
    loading_surface = gs.FONT_SIZE.render(f"Loading..{current_loading_time} s", True, gs.WHITE)
    loading_rect = loading_surface.get_rect(center = (gs.WIDTH / 2, gs.HEIGHT / 2))
    screen.blit(loading_surface, loading_rect)

    for event in pg.event.get():
        if event.type == pg.QUIT:
            handle_quit()

# 處理退出遊戲
def handle_quit():
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

            if client.ready_mode == "again":
                return "again"
            elif client.ready_mode == "watch":
                return "watch"
        
        else:
            print(f"[警告] 未知的 game_state: {current_game_state}")
            
        pg.display.flip()
        clock.tick(60)

    return "end"

