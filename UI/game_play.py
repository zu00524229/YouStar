

# game_play_ui.py       :   game.py 遊戲中畫面  
import pygame as pg
import settings.game_settings as gs
import random
import time
import asyncio

# 玩家時間
def draw_time(screen, remaining_time):
    time_surface = gs.FONT_SIZE.render(f"Time: {remaining_time}s", True, gs.WHITE)
    screen.blit(time_surface, (350, 20))

# 玩家分數
def draw_score(screen, score):
    score_surface = gs.FONT_SIZE.render(f"Score: {score}", True, gs.WHITE)
    screen.blit(score_surface, (20, 20))

# 處理及時排行榜
def draw_live_leaderboard(screen, leaderboard_data):
    right_x = gs.WIDTH - 150
    top_y = 30
    line_height = 35

    leaderboard_title_surface = gs.FONT_SIZE.render("Rank", True, (255, 255, 0))
    screen.blit(leaderboard_title_surface, (right_x, top_y))

    for idx, entry in enumerate(leaderboard_data):
        text = f"{entry['username']} : {entry['score']}"
        entry_surface = gs.RANK_FONT_SIZE.render(text, True, (gs.WHITE))
        screen.blit(entry_surface, (right_x, top_y + (idx + 1) * line_height))

# 繪製飛字提示
def draw_score_popups(screen):
    popup_font = pg.font.SysFont(None, 36)
    for popup in gs.score_popups:
        color = popup.get("color", (255, 215, 0))
        popup_surface = popup_font.render(popup["text"], True, color)
        popup_surface.set_alpha(popup["alpha"])             # 設定透明度
        screen.blit(popup_surface, (50, popup["y_pos"]))    # 顯示畫面

    # 更新 popup 狀態
    for popup in gs.score_popups:
        popup["y_pos"] -= 0.5   # 向上移動
        popup["alpha"] -= 0.5   # 逐漸透明
        popup["alpha"] = max(0, popup["alpha"])     # 確保透明度不為負

    # 清理掉已完全消失的飛字
    gs.score_popups[:] = [p for p in gs.score_popups if p["alpha"] > 0]

# 繪製地鼠
def draw_moles(screen, state):
    now = time.time()

    # === 一般地鼠 ===
    if (state["mole_active"] 
        and state["current_mole_position"] >= 0 
        and now - state.get("current_mole_spawn_time", 0) <= state.get("current_mole_duration", 1.2)):

        x, y = gs.GRID_POSITIONS[state["current_mole_position"]]
        mole_info = next((m for m in gs.MOLE_TYPES if m["name"] == state["current_mole_type_name"]), None)

        if mole_info:
            mole_color = mole_info["color"]
            pg.draw.circle(screen, mole_color, (x, y), 50)

            if state["current_mole_type_name"] == "Joker Mole":
                question_font = pg.font.SysFont(None, 72)
                question_surface = question_font.render("?", True, (gs.WHITE))
                question_rect = question_surface.get_rect(center=(x, y))
                screen.blit(question_surface, question_rect)

    # === 特殊地鼠 ===（此處暫不加時間限制）
    if state["special_mole_active"] and state["current_special_mole_position"] >= 0:
        x, y = gs.GRID_POSITIONS[state["current_special_mole_position"]]
        mole_info = next((m for m in gs.MOLE_TYPES if m["name"] == state["current_special_mole_type_name"]), None)
        if mole_info:
            mole_color = mole_info["color"]
            pg.draw.circle(screen, (gs.WHITE), (x, y), 55)  # 外圈白框
            pg.draw.circle(screen, mole_color, (x, y), 45)  # 內圈地鼠


# 點擊冷卻控制
last_click_time = 0
click_cooldown = 0.2  # 每次打擊至少間隔 0.2 秒，避免連點送出

# 處理打地鼠判定
def handle_playing_events(state, client, score, handle_quit):
    global last_click_time
        
    # 如果是觀戰模式 直接return
    if client.is_watching:
        return


    mole_active = state.get("mole_active")
    special_mole_active = state.get("special_mole_active")
    current_mole_position = state.get("current_mole_position")
    current_special_mole_position = state.get("current_special_mole_position")
    current_mole_type_name = state.get("current_mole_type_name")
    current_special_mole_type_name = state.get("current_special_mole_type_name")
    current_mole_score = state.get("current_mole_score")
    current_mole_id = state.get("current_mole_id")
    current_special_mole_id = state.get("current_special_mole_id")

    for event in pg.event.get():
        if event.type == pg.QUIT:
            handle_quit()

        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            now = time.time()
            if now - last_click_time < click_cooldown:
                print("[前端] 點擊太快，忽略")
                return
            last_click_time = now

            mouse_x, mouse_y = pg.mouse.get_pos()

            # === 一般地鼠判定 ===
            if mole_active and current_mole_position is not None:
                x, y = gs.GRID_POSITIONS[current_mole_position]
                dist_sq = (mouse_x - x) ** 2 + (mouse_y - y) ** 2

                if dist_sq <= 60 ** 2:
                    print(f"[前端] 命中一般地鼠 ID={current_mole_id} Score={current_mole_score}")
                    asyncio.create_task(client.send_hit(current_mole_id))       # 只告訴後端打中哪隻地鼠

            # === 特殊地鼠判定 ===
            if special_mole_active and current_special_mole_position is not None:
                x, y = gs.GRID_POSITIONS[current_special_mole_position]
                dist_sq = (mouse_x - x) ** 2 + (mouse_y - y) ** 2

                if dist_sq <= 60 ** 2:
                    special_score = next((m["score"] for m in gs.MOLE_TYPES if m["name"] == current_special_mole_type_name), 0)
                    print(f"[前端] 命中特殊地鼠 ID={current_special_mole_id} Score={special_score}")
                    asyncio.create_task(client.send_special_hit(current_special_mole_id))


def draw_playing_screen(screen, state, client):
    mouse_x, mouse_y = pg.mouse.get_pos()
    
    draw_score(screen, client.score)                            # 分數顯示
    draw_time(screen, state["remaining_time"])                  # 倒數時間顯示
    draw_live_leaderboard(screen, client.leaderboard_data)      # 即時排行榜
    draw_moles(screen, state)                                   # 普通/特殊地鼠顯示
    draw_score_popups(screen)                                   # 擊中地鼠的分數彈出動畫
    
    # 顯示一般地鼠的打擊判定區（紅色）
    if state["mole_active"] and state["current_mole_position"] >= 0:
        x, y = gs.GRID_POSITIONS[state["current_mole_position"]]
        pg.draw.circle(screen, (255, 0, 0), (x, y), 60, 2)  # 紅色邊框，半徑60（與邏輯一致）

    # 顯示特殊地鼠的打擊判定區（青藍色）
    if state["special_mole_active"] and state["current_special_mole_position"] >= 0:
        sx, sy = gs.GRID_POSITIONS[state["current_special_mole_position"]]
        pg.draw.circle(screen, (0, 255, 255), (sx, sy), 60, 2)  # 青藍色邊框

    # 顯示滑鼠當前位置（黃十字）
    pg.draw.line(screen, (255, 255, 0), (mouse_x - 10, mouse_y), (mouse_x + 10, mouse_y), 1)
    pg.draw.line(screen, (255, 255, 0), (mouse_x, mouse_y - 10), (mouse_x, mouse_y + 10), 1)
    