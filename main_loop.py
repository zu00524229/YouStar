# game_mainloop.py  管理game.py遊戲主循環 與 loading
import pygame as pg
import asyncio
import time
import UI.game_play as pl
import UI.game_gameover_ui as ov
import UI.game_waiting as wait
import UI.game_watch as gw
import UI.game_highlight as hig
import settings.game_settings as gs
import settings.animation as ani
from UI.client import GameClient


# loading (等待與加入)
def draw_loading_screen(screen, current_loading_time):
    loading_surface = gs.FONT_SIZE.render(f"Loading..{current_loading_time} s", True, gs.WHITE)
    loading_rect = loading_surface.get_rect(center = (gs.WIDTH / 2, gs.HEIGHT / 2))
    screen.blit(loading_surface, loading_rect)

# 處理退出遊戲
def handle_quit():
    print("[前端] 玩家關閉視窗，離開遊戲。")
    pg.quit()
    exit()

# 與大廳 GameServer 連線/段開
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


# 當前機臺玩家人數
def player_count(surface, current_players):
    players_surface = gs.SMALL_FONT_SIZE.render(f"Players: {current_players}", True, (255, 255, 0))
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

    # # 無論是否觀戰，一開始都強制同步 game_state
    # await client.fetch_server_state()  # 真正從 GameServer 抓狀態


    # 如果不是觀戰者才等待刷新狀態
    if not client.is_watching:
        wait_until_state_not_gameover(client)

    running = True
    frame_count = 0 
    while running:
        frame_count += 1
        blink = (frame_count // 30) % 2 == 0    # 每 30 frame 閃爍一次
        
        events = pg.event.get()
        for event in events:
            if event.type == pg.QUIT:
                handle_quit()
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                ani.add_click_effect(pg.mouse.get_pos())

        with client.state_lock:
            current_game_state = client.game_state
            current_loading_time = client.loading_time
            current_remaining_time = client.remaining_time
            current_players = client.current_players
            watching_players = client.watching_players      # 觀戰人數
            leaderboard_data = client.leaderboard_data
            score = client.score

        # print(f"[MainLoop] 遊戲狀態：{current_game_state}")
        screen.fill(gs.BLACK)

        
        if current_game_state in ["waiting", "loading", "playing", "gameover","post_gameover"]:
            player_count(screen, current_players)   # 右下角當前 GameServer 人數
            gw.watching_count(     # 左下角顯示 Watching
                surface=screen,
                watching_players = client.watching_players,
                is_watching=client.is_watching,
                available_servers=client.available_servers,
                blink=blink
            )     
            # print(f"[Debug] game_state = {client.game_state}, type = {type(client.game_state)}")
            # 顯示破紀錄提示（限時 3 秒）
            hig.show_highlight(screen, client)  # 破紀錄廣播

        
        if current_game_state == "waiting":
            result = wait.draw_waiting_screen(screen, events, client)    # 等待畫面
            if result == "lobby":
                return "lobby"  # 通知主程式切換回大廳
            elif result:        # 玩家點了 Ready
                    client.game_state = "loading"

        elif current_game_state == "loading":
            draw_loading_screen(screen, current_loading_time)   # loading畫面

        elif current_game_state == "playing":
            state = client.sync_game_state()
            pl.draw_playing_screen(screen, state, client)

            if not client.is_watching:   # 如果是觀戰模式不觸發地鼠打擊
                pl.handle_playing_events(events, state, client, score, handle_quit)

        elif current_game_state in ["gameover", "post_gameover"]:
            result = ov.draw_gameover_screen(screen, handle_quit, client, events)
            ov.draw_final_leaderboard(screen, ov.get_sorted_leaderboard_list_from_file())       # 左上歷史高分排行

                # --- 如果後端已切進下一場 playing，這邊強制跳回迴圈重新處理 ---
            if client.game_state == "playing":
                print("[MainLoop] 偵測到 replay 倒數結束，自動進入新一局 playing，重設 final_sent")
                client.final_sent = False
                continue  # 回到主迴圈重新處理畫面
            
            # --- 處理 Again 倒數畫面 ---
            if client.game_state == "post_gameover" and client.again_timer > 0:
                text = gs.SMALL_FONT_SIZE.render(f"loading..{client.again_timer} s", True, (255, 0, 0))
                screen.blit(text, (gs.WIDTH / 2 + 120 - 40, gs.HEIGHT - 140))  # 放你想要的位置
            else:
                client.again_timer = 0  # 清除舊殘留（保險用）
                
            if result in ["again", "watch", "lobby"]:
                return result
            
        elif current_game_state == "lobby":
            print("[MainLoop] 玩家已返回 lobby，準備跳出遊戲迴圈")
            return "lobby"

        else:
            print(f"[警告] 未知的 game_state: {current_game_state}")

        ani.draw_message(screen)
        ani.draw_click_effects(screen)
        pg.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)

    return "end"
