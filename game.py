# game.py → 遊戲主程式
import pygame as pg
import random
from client import GameClient

# 啟動 GameClient → 負責與 ControlServer + GameServer 通訊
client = GameClient("player2", "5678")
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

# 設定 4x3 格子位置
cell_size = 160
offset_x = (width - (cell_size * 4)) // 2
offset_y = (height - (cell_size * 3)) // 2 + 30

score_popups = []   # 儲存及時分數，飛字提示

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

def player_count(surface, current_players):
    players_surface = font.render(f"Players: {current_players}", True, (255, 255, 0))
    players_rect = players_surface.get_rect(bottomright=(width - 20, height - 20))  # 右下角
    surface.blit(players_surface, players_rect)

# 遊戲主迴圈
while running:
    # 從 client 狀態讀取目前遊戲狀態 → 用 lock 確保同步
    with client.state_lock:        
        current_players = client.current_players        # 當前機台玩家人數
        current_game_state = client.game_state          # 根據這個顯示當前畫面狀態
        # 玩家目前遊戲階段（waiting / loading / ready / playing / gameover）      
        
        current_remaining_time = client.remaining_time  # 倒數顯示    
        current_loading_time = client.loading_time      # loading 階段倒數剩餘秒數          
        current_mole_id = client.current_mole_id        # 當前地鼠的唯一編號
        # → 點擊 hit 時要帶這個 id 回報 hit:mole_id:score       
        current_mole_position = client.current_mole_position    # 畫地鼠時決定畫在哪一格
        # 當前活躍地鼠出現在哪一格（grid_positions index）
        current_mole_type_name = client.current_mole_type_name  # 地鼠類型名稱       
        mole_active = client.mole_active                        # 判斷是否可處理點擊

        current_special_mole_position = client.current_special_mole_position   # 特殊地鼠位置
        current_special_mole_type_name = client.current_special_mole_type_name # 特殊地鼠名
        special_mole_active = client.special_mole_active            
        leaderboard_data = client.leaderboard_data              # 排行榜畫面用
        # 最新 leaderboard 資料（list of {username, score}）   
        score = client.score                            # 玩家目前分數    

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
        waiting_rect = waiting_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(waiting_surface, waiting_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

    elif current_game_state == "gameover":
        # 遊戲結束 : 顯示排行榜
        leaderboard_surface = big_font.render("Leaderboard", True, white)
        leaderboard_rect = leaderboard_surface.get_rect(center=(width / 2, 70))
        screen.blit(leaderboard_surface, leaderboard_rect)

        # 畫 leaderboard (歷史高分)
        for idx, entry in enumerate(leaderboard_data[:5]):
            text = f"{idx + 1} {entry['username']} - {entry['score']}"
            entry_surface = font.render(text, True, white)
            screen.blit(entry_surface, (width / 2 - 120, 100 + idx * 50))

        # 畫 Exit 按鈕
        exit_surface = font.render("Exit", True, (255, 255, 255))
        exit_rect = exit_surface.get_rect(center=(width / 2, height / 2 + 200))
        pg.draw.rect(screen, (100, 100, 100), exit_rect.inflate(20, 10))
        screen.blit(exit_surface, exit_rect)

        # 處理點擊 Exit
        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()
            elif event.type == pg.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pg.mouse.get_pos()
                if exit_rect.collidepoint(mouse_x, mouse_y):
                    handle_quit()

    elif current_game_state == "loading":
        # loading 倒數畫面
        loading_surface = font.render(f"Loading..{current_loading_time} s", True, white)
        loading_rect = loading_surface.get_rect(center=(width / 2, height / 2))
        screen.blit(loading_surface, loading_rect)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                handle_quit()

    elif current_game_state == "ready":
        # ready 畫面
        ready_surface = big_font.render("Ready!", True, (255, 255, 0))
        ready_rect = ready_surface.get_rect(center=(width / 2, height / 2))
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
                    question_rect = question_surface.get_rect(center=(x, y))
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
            popup["y_pos"] -= 0.25   # 每 frame 往上 1px
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


    # 畫面更新
    pg.display.flip()
    clock.tick(60)

# 遊戲結束
pg.quit()
