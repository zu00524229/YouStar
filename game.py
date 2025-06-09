import pygame as pg
import random
import time
import requests

LOGIN_URL = "http://127.0.0.1:8000/login"

username = "player1"
password = "1234"

response = requests.post(LOGIN_URL, json = {
    "username": username,
    "password": password
})
assigned_server = None
if response.status_code == 200:
    data = response.json()
    if "assigned_server" in data:
        assigned_server = data["assigned_server"]
        print(f"[前端]登入成功，分配到 GameServer: {assigned_server}")
        game_state = "playing"
    else:
        print(f"[前端]等待中... {data}")
        game_state = "waiting"
else:
    print(f"[前端]Loading...{response.text}")
    game_state = "waiting"


# 初始化 pygame
pg.init()

white = (255, 255, 255)   # 白色
black = (0, 0, 0)         # 黑色
bomb = (92, 92, 92)       # 灰色
# 設定視窗大小
width = 640
height = 480
screen = pg.display.set_mode((width, height))
pg.display.set_caption("打地鼠")

# 設定字型
font = pg.font.SysFont(None, 48)
big_font = pg.font.SysFont(None, 96)

# 建立畫布背景 (這裡雖然建立了 bg 但目前沒用，可以省略也OK)
bg = pg.Surface(screen.get_size())
bg = bg.convert()

# 格子大小
cell_size = 150

# 起點偏移 (置中) → +30 是為了讓格子往下移，不會擋到上方分數/時間
offset_x = (width - (cell_size * 3)) // 2
offset_y = (height - (cell_size * 3)) // 2 + 30

# 計算 3x3 格子中心座標 → 存到 grid_positions
grid_positions = []
for row in range(3):
    for col in range(3):
        x = offset_x + col * cell_size + cell_size // 2
        y = offset_y + row * cell_size + cell_size // 2
        grid_positions.append((x, y))

# 地鼠種類
MOLE_TYPES = [
    {"name": "普通地鼠", "color": (200, 100, 100), "score": +1},
    {"name": "黃金地鼠", "color": (255, 215, 0), "score": +5},
    {"name": "炸彈地鼠", "color": (bomb), "score": -3},
    {"name": "賭博地鼠", "color": (128, 0, 128), "score": 0, "score_range": (-7, 15)},
]

# 遊戲狀態變數
current_mole_type = None  # 目前地鼠
mole_index = None         # 當前地鼠在哪一格 (0~8)，None 代表目前沒有地鼠
mole_visible = False      # 是否有地鼠出現
score = 0                 # 玩家分數
start_time = time.time()  # 遊戲開始時間
game_duration = 60        # 遊戲總時間 (秒)
game_state = "playing"
remaining_wait_time = 10
leaderboard_data = []     # 排行榜


# 地鼠下一次出現時間 → 初始化為 1 秒後
next_mole_time = time.time() + 1

# 遊戲主迴圈
running = True
clock = pg.time.Clock()

while running:
    elapsed_time = time.time() - start_time             # 剩餘時間
    remaining_time = max(0, int(game_duration - elapsed_time))

    screen.fill((black))

    if game_state == "waiting":
        waiting_surface = font.render(f"Loading..{remaining_wait_time} s", True, (white))
        waiting_rect = waiting_surface.get_rect(center = (width / 2, height / 2))
        screen.blit(waiting_surface, waiting_rect)
    elif game_state == "playing":
       
        # 填滿背景顏色
        screen.fill((black))

        # 顯示分數 
        score_surface = font.render(f"Score: {score}", True, (white))
        screen.blit(score_surface, (20, 20))    # 分數顯示位置

        # 顯示剩餘時間
        
        time_surface = font.render(f"Time: {remaining_time}s", True, (white))
        screen.blit(time_surface, (350, 20))    # 剩餘時間顯示位置

        # 判斷是否需要出新地鼠
        if time.time() >= next_mole_time and remaining_time > 0:
            mole_index = random.randint(0, 8)  # 隨機 0~8 選一格出現地鼠
            mole_visible = True
            current_mole_type = random.choice(MOLE_TYPES) # 隨機一種地鼠
            # 下次出新地鼠的時間 → 0.5 ~ 1.5 秒之後
            next_mole_time = time.time() + random.uniform(0.5, 1.5)

        # 畫地鼠 (如果有地鼠出現)
        if mole_visible and mole_index is not None:
            x, y = grid_positions[mole_index]
            mole_color = current_mole_type["color"]
            pg.draw.circle(screen, mole_color, (x, y), 50)  

        # 處理事件 (鍵盤、滑鼠、退出)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False  # 點右上角 X → 結束遊戲

            elif event.type == pg.MOUSEBUTTONDOWN and mole_visible:
                mouse_x, mouse_y = pg.mouse.get_pos()
                x, y = grid_positions[mole_index]

                # 判斷是否點中地鼠 (計算滑鼠座標與地鼠圓心的距離)
                if (mouse_x - x) ** 2 + (mouse_y - y) ** 2 <= 50 ** 2:
                    print(f"打中了 {current_mole_type['name']}！")
                    if "score_range" in current_mole_type:
                        random_score = random.randint(current_mole_type["score_range"][0], current_mole_type["score_range"][1])
                        score += random_score
                        print(f"賭博地鼠獲得分數: {random_score}!")
                    else:
                        score += current_mole_type["score"] # 加減該地鼠分數

                    mole_visible = False  # 地鼠打掉後隱藏

        # 檢查遊戲是否結束
        if game_state == "playing" and remaining_time <= 0:
            game_over_surface = big_font.render("Time out", True, (255, 0, 0))  # 紅字提示
            text_rect = game_over_surface.get_rect(center = (width / 2, height / 2))
            screen.blit(game_over_surface, text_rect)
            screen.fill((black))  # 清空畫面

             # 調用排行榜
            if assigned_server:
                print("[前端] 取得排行榜中...")
                try:
                    response = requests.get("http://127.0.0.1:8000/get_leaderboard", params={
                        "gameserver_url": assigned_server  
                    })
                    if response.status_code == 200:
                        leaderboard_data = response.json()["leaderboard"]
                        print("[前端] getTop!", leaderboard_data)
                    else:
                        print("[前端] NotTop!", response.text)

                except Exception as e:
                    print("[前端] 取得排行榜異常", e)
            else:
                print("[前端] 沒有 assigned_server，略過排行榜")

            # 顯示排行榜畫面
            leaderboard_surface = big_font.render("Leaderboard", True, white)
            leaderboard_rect = leaderboard_surface.get_rect(center = (width / 2, 50))
            screen.blit(leaderboard_surface, leaderboard_rect)
            

            # 顯示前 5 名
            for idx, entry in enumerate(leaderboard_data[:5]):
                text = f"{idx+1}. {entry['username']} - {entry['score']}"
                entry_surface = font.render(text, True, white)
                screen.blit(entry_surface, (width / 2 - 150, 100 + idx * 50))

            # 顯示最終分數
            final_score_surface = font.render(f"Final Score: {score}", True, white)
            final_score_rect = final_score_surface.get_rect(center = (width / 2, height / 2 + 120))
            screen.blit(final_score_surface, final_score_rect)

            tip_surface = font.render("exit", True, (white))
            tip_rect = tip_surface.get_rect(center = (width / 2, height / 2 + 180))
            screen.blit(tip_surface, tip_rect)
            pg.display.flip()
            # pg.time.wait(3000)  # 停留 3 秒

            waiting_for_exit = True
            while waiting_for_exit:
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        waiting_for_exit = False    # 關閉
                    elif event.type == pg.MOUSEBUTTONUP:
                        waiting_for_exit = False
            running = False  # 跳出主迴圈，結束遊戲

    # 更新畫面
    pg.display.flip()
    clock.tick(60)  # 每秒最多跑 60 FPS → 流暢更新畫面

# 關閉 pygame
pg.quit()
