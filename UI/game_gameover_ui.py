# game_gameover_ui.py
import pygame as pg
import settings.game_settings as gs
import settings.animation as ani

# 轉換 leaderboard.json 檔案成排序好的排行榜列表
def get_sorted_leaderboard_list_from_file():
    import json, os
    LEADERBOARD_FILE = "leaderboard.json"  # 檔案路徑

    # 如果檔案不存在或為空，回傳空列表
    if not os.path.exists(LEADERBOARD_FILE) or os.path.getsize(LEADERBOARD_FILE) == 0:
        return []

    try:
        with open(LEADERBOARD_FILE, "r") as f:
            raw_data = json.load(f)  # 讀取 json 檔（dict 格式）

        # 將 dict 轉成 list 並依照分數高低排序
        return sorted(
            [{"username": name, "score": score} for name, score in raw_data.items()],
            key=lambda x: x["score"],
            reverse=True  # 分數由高到低
        )
    except json.JSONDecodeError:
        print("[錯誤] leaderboard.json 檔案格式錯誤，自動回傳空列表")
        return []


# 在畫面左上角顯示歷史排行榜（最多顯示前五名）
def draw_final_leaderboard(surface, leaderboard_data):
    font = gs.SMALL_FONT_SIZE   # 使用小字體
    x, y = 20, 50               # 左上角

    # 畫出標題文字「High Scores」
    title_surface = font.render("High Scores", True, (255, 215, 0))
    surface.blit(title_surface, (x, y))
    y += 30

    # 列出前五名玩家與分數
    for i, entry in enumerate(leaderboard_data[:10]):  # 顯示前10名
        text = f"{i+1}. {entry['username']} - {entry['score']}"
        text_surface = font.render(text, True, (255, 255, 255))
        surface.blit(text_surface, (x, y))
        y += 25 # 每列間距


def draw_gameover_screen(screen, handle_quit, client, events):
    # print("[Debug] 畫面中排行榜來源：", client.leaderboard_data[:5])
    if client.game_state not in ["gameover", "post_gameover"]:
        print("[前端] 已進入非 gameover/post_gameover 狀態，跳出畫面")
        return


    # 畫面標題 :Leaderboard
    leaderboard_surface = gs.BIG_FONT_SIZE.render("Leaderboard", True, gs.WHITE)
    leaderboard_rect = leaderboard_surface.get_rect(center=(gs.WIDTH / 2, 70))
    screen.blit(leaderboard_surface, leaderboard_rect)

    # 顯示排行榜前五名
    for idx, entry in enumerate(client.leaderboard_data[:5]):
        text = f"{idx + 1}. {entry['username']} - {entry['score']}"
        entry_surface = gs.FONT_SIZE.render(text, True, gs.WHITE)
        screen.blit(entry_surface, (gs.WIDTH / 2 - 150, 120 + idx * 40))

    # 滑鼠位置
    mouse_x, mouse_y = pg.mouse.get_pos()

    # Lobby 按鈕（永遠顯示）
    exit_surface = gs.FONT_SIZE.render("Lobby", True, gs.WHITE)
    exit_rect = exit_surface.get_rect(center=(gs.WIDTH / 2 - 120, gs.HEIGHT - 80))
    is_hover_exit = exit_rect.collidepoint(mouse_x, mouse_y)
    exit_surface = gs.FONT_SIZE.render("Lobby", True, gs.HOVAR if is_hover_exit else gs.WHITE)
    screen.blit(exit_surface, exit_rect)

    # Again 按鈕
    again_rect = None   # 只有非觀戰顯示
    if not client.is_watching:
        again_surface = gs.FONT_SIZE.render("Again", True, gs.HOVAR if pg.Rect(gs.WIDTH / 2 + 120 - 40, gs.HEIGHT - 80 - 20, 80, 40).collidepoint(mouse_x, mouse_y) else gs.WHITE)
        again_rect = again_surface.get_rect(center=(gs.WIDTH / 2 + 120, gs.HEIGHT - 80))
        screen.blit(again_surface, again_rect)


    # === 處理滑鼠點擊 ===
    for event in events:
        if event.type == pg.QUIT:
            handle_quit()

        elif event.type == pg.MOUSEBUTTONDOWN:
            ani.add_click_effect(event.pos)
            print(f"[Debug] Mouse click at {mouse_x}, {mouse_y}")

            if again_rect and again_rect.collidepoint(mouse_x, mouse_y):
                print("[Debug] Clicked AGAIN")
                client.send_again()     # 呼叫方法 傳送 again 訊號
                return None

            if exit_rect.collidepoint(mouse_x, mouse_y):
                print("[Debug] Clicked LOBBY")
                client.disconnect_from_server()
                return "lobby"

    return None


