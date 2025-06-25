# game_mainloop.py  管理game.py遊戲主循環 與 loading
import pygame as pg
import asyncio
import UI.game_play as pl
import UI.game_gameover_ui as ov
import UI.game_waiting as wait
import settings.game_settings as gs
from UI.client import GameClient

# 觀戰模式(未製作)
async def run_watch_mode(screen, client):
    print("[前端] 進入觀戰模式，目前暫不支援。")
    await asyncio.sleep(0.5)
    return

# loading (等待與加入)
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
    pg.quit()
    exit()

async def safely_close_client(client):
    try:
        if client.ws_conn:
            await client.ws_conn.close()
            print("[debug] 已要求關閉 client WebSocket")
    except Exception as e:
        print(f"[debug] 關閉 WebSocket 發生錯誤: {e}")


# === 返回主大廳，保持 game 開啟 ===
async def handle_quit_to_lobby(screen, client):
    await safely_close_client(client)
    client.ws_conn = None
    client.ws_started = False
    client.ready_offer_started = False
    client.ready_offer_joined_players = set()
    client.game_state = "lobby"
    client.ready_mode = "lobby"


# 當前機臺玩家人數
def player_count(surface, current_players):
    players_surface = gs.FONT_SIZE.render(f"Players: {current_players}", True, (255, 255, 0))
    players_rect = players_surface.get_rect(bottomright=(gs.WIDTH - 20, gs.HEIGHT - 20))
    surface.blit(players_surface, players_rect)

# 等待GameServer 狀態刷新
def wait_until_state_not_gameover(client, delay_ms = 100):
    attempts = 0
    while True:
        if client.game_state != "gameover":
            print("[debug] game_state 已脫離 gameover，跳出等待")
            break
        print("[debug] 初始狀態為 gameover，等待狀態刷新...")
        pg.time.wait(delay_ms)
        attempts += 1
        if attempts > 200:
            print("[警告] 等待超過 20 秒仍為 gameover，強制跳出")
            break

# === 遊戲 async 主循環 ===
async def run_game_loop(screen, client: GameClient):
    await asyncio.sleep(0.2)
    clock = pg.time.Clock()

    wait_until_state_not_gameover(client)

    running = True
    while running:
        events = pg.event.get()
        for event in events:
            if event.type == pg.QUIT:
                handle_quit()

        with client.state_lock:
            current_game_state = client.game_state
            current_loading_time = client.loading_time
            current_remaining_time = client.remaining_time
            current_players = client.current_players
            leaderboard_data = client.leaderboard_data
            score = client.score

        # print(f"[MainLoop] 遊戲狀態：{current_game_state}")
        screen.fill(gs.BLACK)

        
        if current_game_state in ["waiting", "loading", "playing", "gameover"]:
            player_count(screen, current_players)   # 右下角當前 GameServer 人數
        
        if current_game_state == "waiting":
            wait.draw_waiting_screen(screen, events, client)    # 等待畫面

        elif current_game_state == "loading":
            draw_loading_screen(screen, current_loading_time)   # loading畫面

        elif current_game_state == "playing":
            state = client.sync_game_state()
            pl.draw_playing_screen(screen, state, client)
            pl.handle_playing_events(state, client, score, handle_quit)

        elif current_game_state in ["gameover", "post_gameover"]:
            client.ready_mode = None
            while client.ready_mode is None:
                if client.game_state not in ["gameover", "post_gameover"]:
                    print("[前端] 偵測到已離開 gameover 狀態，中止 gameover 畫面迴圈")
                    break

                result = ov.draw_gameover_screen(screen, handle_quit, client)
                pg.display.flip()
                await asyncio.sleep(0.1)

            if result == "again":
                return "again"
            elif result == "watch":
                return "watch"
            elif result == "lobby":
                return "lobby"
            
        elif current_game_state == "lobby":
            print("[MainLoop] 玩家已返回 lobby，準備跳出遊戲迴圈")
            return "lobby"

        else:
            print(f"[警告] 未知的 game_state: {current_game_state}")

        pg.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)

    return "end"
