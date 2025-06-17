# game.py → 遊戲主程式
import pygame as pg
import random
from client import GameClient
import threading
import asyncio
import time

# 啟動 GameClient → 負責與 ControlServer + GameServer 通訊
client = GameClient("player1", "1234")
client.start()


# 初始化 pygame 畫面
pg.init()

white = (255, 255, 255)
black = (0, 0, 0)

width = 840
height = 640
screen = pg.display.set_mode((width, height))
pg.display.set_caption("打地鼠")

Rank_font = pg.font.SysFont(None, 24)
font = pg.font.SysFont(None, 48)
big_font = pg.font.SysFont(None, 96)
small_font = pg.font.SysFont(None, 36)

# 設定 4x3 格子位置
cell_size = 160
offset_x = (width - (cell_size * 4)) // 2
offset_y = (height - (cell_size * 3)) // 2 + 30

score_popups = []   # 儲存及時分數，左下飛字提示

grid_positions = []
for row in range(3):
    for col in range(4):
        x = offset_x + col * cell_size + cell_size // 2
        y = offset_y + row * cell_size + cell_size // 2
        grid_positions.append((x, y))

# 地鼠種類
MOLE_TYPES = [
    {"name": "Mole", "color": (200, 100, 100), "score": +3},                    # 普通地鼠
    {"name": "Gold Mole", "color": (255, 215, 0), "score": +8},                 # 黃金地鼠
    {"name": "Bomb Mole", "color": (92, 92, 92), "score": -5},                  # 炸彈地鼠
    {"name": "Diamond Mole", "color": (0, 255, 255), "score": +15},             # 特殊地鼠
    {"name": "Joker Mole", "color": (158, 79, 0), "score": 0, "score_range": (-15, 15)},   # 小丑地鼠
]

running = True
clock = pg.time.Clock()

# 處理退出遊戲
def handle_quit():
    global running
    running = False
    print("[前端] 玩家關閉視窗，離開遊戲。")
    pg.quit()   # ⭐ 主動呼叫 pg.quit()，不用靠最後一行
    exit()

# 大廳伺服器排版
def render_server_status(surface, server, box_y, mouse_x, mouse_y, index):
    box_width = 600
    box_height = 80
    box_x = (width - box_width) // 2

    box_rect = pg.Rect(box_x, box_y, box_width, box_height)

    # 判斷是否 hover
    is_hover = box_rect.collidepoint(mouse_x, mouse_y)
    box_color = (100, 100, 100) if is_hover else (60, 60, 60)

    # 畫方框
    pg.draw.rect(surface, box_color, box_rect)
    pg.draw.rect(surface, (200, 200, 200), box_rect, 2)  # 外框線

    # Server 名字用大字
    server_name_surface = font.render(f"GameServer {index + 1}", True, (255, 255, 255))
    server_name_rect = server_name_surface.get_rect(topleft=(box_x + 20, box_y + 10))
    surface.blit(server_name_surface, server_name_rect)

    # 小字: 玩家數 / Status
    phase_map = {
        "waiting": "Waiting",
        "loading": "Loading",
        "ready": "Ready",
        "playing": "Playing",
        "gameover": "Game Over"
    }
    status_text = f"({server['current_players']}/{server['max_players']})   Status: {phase_map.get(server['game_phase'], server['game_phase'])}"

    small_font_render = pg.font.SysFont(None, 32)
    status_surface = small_font_render.render(status_text, True, (200, 200, 200))
    status_rect = status_surface.get_rect(topleft=(box_x + 20, box_y + 45))
    surface.blit(status_surface, status_rect)

    return box_rect


# 當前機台玩家人數
def player_count(surface, current_players):
    players_surface = font.render(f"Players: {current_players}", True, (255, 255, 0))
    players_rect = players_surface.get_rect(bottomright=(width - 20, height - 20))  # 右下角
    surface.blit(players_surface, players_rect)

# --- 大廳畫面 ---
def show_lobby():
    pg.display.set_caption("Game Lobby")
    lobby_running = True
    server_list = client.get_server_list() # 先取得，R 才能刷新

    while lobby_running:
        screen.fill((30, 30, 30))

        # 取得 server list
        server_list = client.get_server_list()

        # 畫出標題
        title_surface = big_font.render("Game Lobby", True, (255, 255, 255))
        title_rect = title_surface.get_rect(center=(width/2, 80))
        screen.blit(title_surface, title_rect)

        # 畫出每台 GameServer 狀態（帶框 + hover 效果）
        server_buttons = []
        box_width = 600
        box_height = 80
        box_x = (width - box_width) // 2

        mouse_x, mouse_y = pg.mouse.get_pos()

        for i, server in enumerate(server_list):
            box_rect = render_server_status(screen, server, 150 + i * (box_height + 20), mouse_x, mouse_y, i)
            server_buttons.append((box_rect, server["server_url"]))

        # 畫提示
        small_font_render = pg.font.SysFont(None, 28)
        hint_surface = small_font_render.render("Click on a server to join. Press R to refresh.", True, (150, 150, 150))
        hint_rect = hint_surface.get_rect(center=(width/2, height - 50))
        screen.blit(hint_surface, hint_rect)

        pg.display.flip()

        # 處理事件
        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_r:
                    pass  # R → 重新整理 server_list

            elif event.type == pg.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pg.mouse.get_pos()
                for box_rect, server_url in server_buttons:
                    if box_rect.collidepoint(mouse_x, mouse_y):
                        # 點擊進入該 server
                        client.assigned_server = server_url
                        print(f"[前端] 選擇連線到 GameServer: {server_url}")
                        threading.Thread(target=lambda: asyncio.run(client.ws_receiver_async()), daemon=True).start()
                        lobby_running = False
                        break

while not client.login_success:
    print("[大廳] 等待登入完成...")
    time.sleep(0.1)

show_lobby()
# 遊戲主迴圈
while running:
    # 從 client 狀態讀取目前遊戲狀態 → 用 lock 確保同步
    with client.state_lock:        
        current_players = client.current_players                                # 當前機台玩家人數
        current_game_state = client.game_state                                  # 根據這個顯示當前畫面狀態
        # 玩家目前遊戲階段（waiting / loading / ready / playing / gameover）      
        
        current_remaining_time = client.remaining_time                          # 倒數顯示    
        current_loading_time = client.loading_time                              # loading 階段倒數剩餘秒數          
        current_mole_id = client.current_mole_id                                # 當前地鼠的唯一編號
        # 點擊 hit 時要帶這個 id 回報 hit:mole_id:score       
        current_mole_position = client.current_mole_position                    # 畫地鼠時決定畫在哪一格
        # 當前活躍地鼠出現在哪一格（grid_positions index）
        current_mole_type_name = client.current_mole_type_name                  # 地鼠類型名稱       
        mole_active = client.mole_active                                        # 判斷是否可處理點擊

        current_special_mole_position = client.current_special_mole_position    # 特殊地鼠位置
        current_special_mole_type_name = client.current_special_mole_type_name  # 特殊地鼠名
        special_mole_active = client.special_mole_active            
        leaderboard_data = client.leaderboard_data                              # 排行榜畫面用
        # 最新 leaderboard 資料（list of {username, score}）   
        score = client.score                                                    # 玩家目前分數    

    # 時間顯示
    time_surface = font.render(f"Time: {current_remaining_time}s", True, white)

    screen.fill(black)

# =============================================================================== #
    # === 畫面顯示 ===
    # 當前玩家人數
    if current_game_state in ["waiting", "loading", "playing", "gameover"]:
        player_count(screen, current_players)

    if current_game_state == "waiting":
        # 等待玩家進入
        waiting_surface = font.render(f"Waiting for players...", True, white)
        waiting_rect = waiting_surface.get_rect(center = (width / 2, height / 2))
        screen.blit(waiting_surface, waiting_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

    elif current_game_state == "gameover":
        # 遊戲結束 : 顯示排行榜
        leaderboard_surface = big_font.render("Leaderboard", True, white)
        leaderboard_rect = leaderboard_surface.get_rect(center = (width / 2, 70))
        screen.blit(leaderboard_surface, leaderboard_rect)

        # 畫 leaderboard (歷史高分)
        for idx, entry in enumerate(leaderboard_data[:5]):
            text = f"{idx + 1} {entry['username']} - {entry['score']}"
            entry_surface = font.render(text, True, white)
            screen.blit(entry_surface, (width / 2 - 120, 100 + idx * 50))

        # 畫 Exit 按鈕
        exit_surface = font.render("Exit", True, (255, 255, 255))
        exit_rect = exit_surface.get_rect(center=(width / 2 - 100, height / 2 + 200))
        pg.draw.rect(screen, (100, 100, 100), exit_rect.inflate(20, 10))
        screen.blit(exit_surface, exit_rect)

        # 畫 Replay 按鈕
        replay_surface = font.render("Play Again", True, (255, 255, 255))
        replay_rect = replay_surface.get_rect(center=(width / 2 + 100, height / 2 + 200))
        pg.draw.rect(screen, (100, 100, 100), replay_rect.inflate(20, 10))
        screen.blit(replay_surface, replay_rect)


        # 畫按鈕
        mouse_x, mouse_y = pg.mouse.get_pos()

        # Exit hover
        is_hover_exit = exit_rect.collidepoint(mouse_x, mouse_y)
        exit_box_color = (150, 150, 150) if is_hover_exit else (100, 100, 100)
        pg.draw.rect(screen, exit_box_color, exit_rect.inflate(20, 10))
        screen.blit(exit_surface, exit_rect)

        # 處理點擊 Exit / Play Again
        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

            elif event.type == pg.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pg.mouse.get_pos()
                if exit_rect.collidepoint(mouse_x, mouse_y):
                    handle_quit()
                elif event.type == pg.MOUSEBUTTONDOWN:
                    mouse_x, mouse_y = pg.mouse.get_pos()
                    if exit_rect.collidepoint(mouse_x, mouse_y):
                        handle_quit()
                    elif replay_rect.collidepoint(mouse_x, mouse_y):
                        print("[前端] 玩家選擇 Play Again，發送 replay")
                        client.send_replay()
                        # ⚠️ 手動 reset local score
                        with client.state_lock:
                            client.score = 0

    elif current_game_state == "loading":
        # loading 倒數畫面
        loading_surface = font.render(f"Loading..{current_loading_time} s", True, white)
        loading_rect = loading_surface.get_rect(center = (width / 2, height / 2))
        screen.blit(loading_surface, loading_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

    elif current_game_state == "ready":
        # ready 畫面
        ready_surface = big_font.render("Ready!", True, (255, 255, 0))
        ready_rect = ready_surface.get_rect(center = (width / 2, height / 2))
        screen.blit(ready_surface, ready_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

    elif current_game_state == "playing":
        # 遊戲進行中 → 顯示分數 + 時間 + 地鼠
        score_surface = font.render(f"Score: {score}", True, white)
        screen.blit(score_surface, (20, 20))
        screen.blit(time_surface, (350, 20))

        # === 右上角即時排行榜 ===
        right_x = width - 150   # 右邊邊距
        top_y = 30              # 從畫面頂端下來一點開始畫
        line_height = 35        # 每一行間距

        leaderboard_title_surface = font.render("Rank", True, (255, 255, 0))
        screen.blit(leaderboard_title_surface, (right_x, top_y))

        for idx, entry in enumerate(leaderboard_data):
            text = f"{entry['username']} : {entry['score']}"
            entry_surface = Rank_font.render(text, True, (255, 255, 255))
            screen.blit(entry_surface, (right_x, top_y + (idx + 1) * line_height))

        # 畫地鼠
        if mole_active and current_mole_position >= 0:
            x, y = grid_positions[current_mole_position]
            # mole_color = next(m["color"] for m in MOLE_TYPES if m["name"] == current_mole_type_name)
            # pg.draw.circle(screen, mole_color, (x, y), 50)
            mole_info = next((m for m in MOLE_TYPES if m["name"] == current_mole_type_name), None)

            if mole_info:
                mole_color = mole_info["color"]
                pg.draw.circle(screen, mole_color, (x, y), 50)

                if current_mole_type_name == "Joker Mole":
                    question_font = pg.font.SysFont(None, 72)
                    question_surface = question_font.render("?", True, (255, 255, 255))
                    question_rect = question_surface.get_rect(center = (x, y))
                    screen.blit(question_surface, question_rect)
            else:
                print(f"[前端] 警告：未知地鼠類型 '{current_mole_type_name}' → 不畫地鼠")

        # 畫特殊地鼠
        if special_mole_active and current_special_mole_position >= 0:
            x, y = grid_positions[current_special_mole_position]
            
            mole_info = next((m for m in MOLE_TYPES if m["name"] == current_special_mole_type_name), None)
            if mole_info:
                mole_color = mole_info["color"]
                # pg.draw.circle(screen, mole_color, (x, y), 50)

            # 畫外圈白框 (例如 55 半徑)
                pg.draw.circle(screen, (255, 255, 255), (x, y), 55)
                # 畫內圈實心特殊地鼠 (例如 45 半徑)
                pg.draw.circle(screen, mole_color, (x, y), 45)

        # 擊中分數飛字提示
        popup_font = pg.font.SysFont(None, 36)
        for popup in score_popups:
            popup_surface = popup_font.render(popup["text"], True, (255, 215, 0))
            popup_surface.set_alpha(popup["alpha"])
            screen.blit(popup_surface, (50, popup["y_pos"]))

        # 更新 popup 狀態（往上漂、透明度變低）
        for popup in score_popups:
            popup["y_pos"] -= 0.5   # 每 frame 往上 速度px
            popup["alpha"] -= 0.5   # 每 frame 透明度降低
            popup["alpha"] = max(0, popup["alpha"])  # 不低於 0

        # 清理消失的 popup
        score_popups[:] = [p for p in score_popups if p["alpha"] > 0]


        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

            elif event.type == pg.MOUSEBUTTONDOWN and mole_active:
                # 判斷是否打中一般地鼠
                mouse_x, mouse_y = pg.mouse.get_pos()
                x, y = grid_positions[current_mole_position]

                if (mouse_x - x) ** 2 + (mouse_y - y) ** 2 <= 50 ** 2:
                    print(f"打中了 {current_mole_type_name}！")

                    # 計算得分
                    # mole_info = next(m for m in MOLE_TYPES if m["name"] == current_mole_type_name)
                    mole_info = next((m for m in MOLE_TYPES if m["name"] == current_mole_type_name), None)

                    if "score_range" in mole_info:
                        random_score = random.randint(mole_info["score_range"][0], mole_info["score_range"][1])
                        score += random_score
                        print(f"Joker Mole 獲得分數: {random_score}!")
                    else:
                        random_score = mole_info["score"]
                        score += random_score
                        print(f"{current_mole_type_name} 獲得分數: {random_score}!")

                    # 更新 client.score → 發送 hit
                    with client.state_lock:
                        client.score = score
                    client.send_hit()

                    mole_active = False

                    # 處理飛字提示
                    if random_score >= 0:
                        popup_text = f"+{random_score} {current_mole_type_name}"
                    else:
                        popup_text = f"{random_score} {current_mole_type_name}"   # 負數直接顯示
                    score_popups.append({
                        "text": popup_text,
                        "y_pos": height - 100,    # 初始 y 座標（下方）
                        "alpha": 255,             # 初始透明度
                    })
                
                # 再檢查特殊地鼠
                elif special_mole_active and current_special_mole_position >= 0:
                    x, y = grid_positions[current_special_mole_position]
                    if (mouse_x - x) ** 2 + (mouse_y - y) ** 2 <= 50 ** 2:
                        print(f"打中了 {current_special_mole_type_name}！")

                        mole_info = next((m for m in MOLE_TYPES if m["name"] == current_special_mole_type_name), None)
                        if mole_info:
                            special_score = mole_info["score"]
                            score += special_score
                            print(f"{current_special_mole_type_name} 獲得分數: {special_score}!")

                        # 更新 client.score → 發送 hit
                        with client.state_lock:
                            client.score = score
                        client.send_special_hit()  

                        # 特殊地鼠消失
                        with client.state_lock:
                            client.special_mole_active = False

                        # 飛字提示
                        popup_text = f"+{special_score} {current_special_mole_type_name}"
                        score_popups.append({
                            "text": popup_text,
                            "y_pos": height - 100,
                            "alpha": 255,
                        })

    if client.replay_offer_remaining_time > 0:
        replay_offer_surface = big_font.render(f"Replay? {client.replay_offer_remaining_time} s", True, (255, 165, 0))
        replay_offer_rect = replay_offer_surface.get_rect(center=(width / 2, height / 2 - 120))
        screen.blit(replay_offer_surface, replay_offer_rect)

        joined_text = f"{client.replay_offer_joined_players}/{client.replay_offer_total_players} players ready"
        joined_surface = font.render(joined_text, True, (255, 255, 255))
        joined_rect = joined_surface.get_rect(center=(width / 2, height / 2 - 60))
        screen.blit(joined_surface, joined_rect)

        # 畫 "參加 Replay" 按鈕
        join_surface = font.render("Join Replay", True, (255, 255, 255))
        join_rect = join_surface.get_rect(center=(width / 2 - 100, height / 2 + 50))

        # 畫 "Skip Replay" 按鈕
        skip_surface = font.render("Skip", True, (255, 255, 255))
        skip_rect = skip_surface.get_rect(center=(width / 2 + 100, height / 2 + 50))

        # Hover 效果
        mouse_x, mouse_y = pg.mouse.get_pos()
        is_hover_join = join_rect.collidepoint(mouse_x, mouse_y)
        is_hover_skip = skip_rect.collidepoint(mouse_x, mouse_y)

        join_box_color = (255, 165, 0) if is_hover_join else (180, 100, 50)
        skip_box_color = (255, 165, 0) if is_hover_skip else (180, 100, 50)

        pg.draw.rect(screen, join_box_color, join_rect.inflate(20, 10))
        screen.blit(join_surface, join_rect)

        pg.draw.rect(screen, skip_box_color, skip_rect.inflate(20, 10))
        screen.blit(skip_surface, skip_rect)

        # 處理 Replay Offer 按鈕點擊
        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

            elif event.type == pg.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pg.mouse.get_pos()
                if join_rect.collidepoint(mouse_x, mouse_y):
                    print("[前端] 玩家選擇參加 Replay，發送 join_replay")
                    client.send_join_replay()
                elif skip_rect.collidepoint(mouse_x, mouse_y):
                    print("[前端] 玩家選擇跳過 Replay（觀戰）")



    # 畫面更新
    pg.display.flip()
    clock.tick(60)

# 遊戲結束
pg.quit()
