# animation.py
import time
import settings.context as ct
import settings.game_settings as gs
import pygame as pg


# === 全域變數 ===
_lobby_message = ""
_lobby_message_start = 0

# === 設定伺服器提示訊息 ===
def set_message(msg):
    global _lobby_message, _lobby_message_start
    _lobby_message = msg
    _lobby_message_start = time.time()

# === 清除訊息（可選） ===
def clear_message():
    global _lobby_message, _lobby_message_start
    _lobby_message = ""
    _lobby_message_start = 0


# === 繪製提示訊息（每次畫面都可呼叫） ===
def draw_message(surface, duration=3):
    if time.time() - _lobby_message_start < duration and _lobby_message:
        font = gs.CH_FONT_SIZE
        msg_surface = font.render(_lobby_message, True, (255, 100, 100))
        msg_rect = msg_surface.get_rect(center=(gs.WIDTH // 2, gs.HEIGHT - 100))
        surface.blit(msg_surface, msg_rect)

# """加入滑鼠點擊動畫效果"""
def add_click_effect(pos):
    ct.click_effects.append({
        "pos": pos,
        "start": time.time()
    })

# """畫出滑鼠點擊動畫效果（泛用於所有畫面）"""
def draw_click_effects(screen):
    now = time.time()
    for effect in ct.click_effects[:]:
        elapsed = now - effect["start"]
        if elapsed > 0.2:
            ct.click_effects.remove(effect)
            continue
        alpha = int(255 * (1 - elapsed / 0.2))  # 不透明度
        radius = int(10 + 20 * elapsed)
        pg.draw.circle(screen, (255, 255, 0), effect["pos"], radius, 2)


# """顯示地鼠被擊中時的動畫效果（如 HIT 文字與紅圈）"""
def draw_hit_effects(screen, state):
    now = time.time()
    for effect in state["hit_effects"][:]:  # 複製一份避免中途修改錯誤
        pos = gs.GRID_POSITIONS[effect["position"]]
        elapsed = now - effect["start_time"]

        if elapsed < 0.2:
            hit_text = gs.BIG_FONT_SIZE.render("HIT!", True, (255, 0, 0))
            screen.blit(hit_text, (pos[0] - 20, pos[1] - 40))
            pg.draw.circle(screen, (255, 0, 0), pos, 65, 3)
        else:
            state["hit_effects"].remove(effect)


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

