

# game_play_ui.py       :   game.py 遊戲中畫面  
import pygame as pg
import settings.game_settings as gs
import random
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
        popup_surface = popup_font.render(popup["text"], True, (255, 215, 0))
        popup_surface.set_alpha(popup["alpha"])
        screen.blit(popup_surface, (50, popup["y_pos"]))

    # 更新 popup 狀態
    for popup in gs.score_popups:
        popup["y_pos"] -= 0.5
        popup["alpha"] -= 0.5
        popup["alpha"] = max(0, popup["alpha"])

    gs.score_popups[:] = [p for p in gs.score_popups if p["alpha"] > 0]

# 繪製地鼠
def draw_moles(screen, state):
    # 一般地鼠
    if state["mole_active"] and state["current_mole_position"] >= 0:
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

    # 特殊地鼠
    if state["special_mole_active"] and state["current_special_mole_position"] >= 0:
        x, y = gs.GRID_POSITIONS[state["current_special_mole_position"]]
        mole_info = next((m for m in gs.MOLE_TYPES if m["name"] == state["current_special_mole_type_name"]), None)
        if mole_info:
            mole_color = mole_info["color"]
            pg.draw.circle(screen, (gs.WHITE), (x, y), 55)  # 外圈白框
            pg.draw.circle(screen, mole_color, (x, y), 45)      # 內圈地鼠

# 處理打地鼠
def handle_playing_events(state, client, score, handle_quit):
    mole_active = state["mole_active"]
    special_mole_active = state["special_mole_active"]
    current_mole_position = state["current_mole_position"]
    current_special_mole_position = state["current_special_mole_position"]
    current_mole_type_name = state["current_mole_type_name"]
    current_special_mole_type_name = state["current_special_mole_type_name"]


    for event in pg.event.get():
        if event.type == pg.QUIT:
            handle_quit()  # 回遊戲大廳

        elif event.type == pg.MOUSEBUTTONDOWN and mole_active:
            mouse_x, mouse_y = pg.mouse.get_pos()

            # === 打中一般地鼠 ===
            x, y = gs.GRID_POSITIONS[current_mole_position]
            if (mouse_x - x) ** 2 + (mouse_y - y) ** 2 <= 50 ** 2:
                mole_info = next((m for m in gs.MOLE_TYPES if m["name"] == current_mole_type_name), None)
                if mole_info:
                    random_score = random.randint(*mole_info["score_range"]) if "score_range" in mole_info else mole_info["score"]
                    score += random_score
                    print(f"打中了 {current_mole_type_name}：{random_score}")

                    with client.state_lock:
                        client.score = score
                        # client.send_hit()
                    asyncio.run_coroutine_threadsafe(client.send_hit_async(), client.async_loop)

                    state["mole_active"] = False

                    popup_text = f"+{random_score} {current_mole_type_name}" if random_score >= 0 else f"{random_score} {current_mole_type_name}"
                    gs.score_popups.append({"text": popup_text, "y_pos": gs.HEIGHT - 100, "alpha": 255})

            # === 打中特殊地鼠 ===
            elif special_mole_active and current_special_mole_position >= 0:
                x, y = gs.GRID_POSITIONS[current_special_mole_position]
                if (mouse_x - x) ** 2 + (mouse_y - y) ** 2 <= 50 ** 2:
                    mole_info = next((m for m in gs.MOLE_TYPES if m["name"] == current_special_mole_type_name), None)
                    if mole_info:
                        special_score = mole_info["score"]
                        score += special_score
                        print(f"打中了 {current_special_mole_type_name}：{special_score}")

                        with client.state_lock:
                            client.score = score
                        # client.send_special_hit()
                        asyncio.run_coroutine_threadsafe(client.send_special_hit_async(), client.async_loop)

                        with client.state_lock:
                            client.special_mole_active = False

                        popup_text = f"+{special_score} {current_special_mole_type_name}"
                        gs.score_popups.append({"text": popup_text, "y_pos": gs.HEIGHT - 100, "alpha": 255})

def draw_playing_screen(screen, state, client):
    draw_score(screen, client.score)                           # 分數顯示
    draw_time(screen, state["remaining_time"])          # 倒數時間顯示
    draw_live_leaderboard(screen, client.leaderboard_data)     # 即時排行榜
    draw_moles(screen, state)                           # 普通/特殊地鼠顯示
    draw_score_popups(screen)                           # 擊中地鼠的分數彈出動畫
    
    # # ➕ 顯示倒數時間（右上角）
    # time_surface = gs.FONT_SIZE.render(f"Time: {remaining_time}s", True, gs.WHITE)
    # screen.blit(time_surface, (350, 20))  # 可以根據你畫面佈局微調位置

