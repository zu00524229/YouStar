# animation.py
import time
import settings.context as ct
import pygame as pg

def add_click_effect(pos):
    """加入滑鼠點擊動畫效果"""
    ct.click_effects.append({
        "pos": pos,
        "start": time.time()
    })

def draw_click_effects(screen):
    """畫出滑鼠點擊動畫效果（泛用於所有畫面）"""
    now = time.time()
    for effect in ct.click_effects[:]:
        elapsed = now - effect["start"]
        if elapsed > 0.2:
            ct.click_effects.remove(effect)
            continue
        alpha = int(255 * (1 - elapsed / 0.2))  # 不透明度
        radius = int(10 + 20 * elapsed)
        pg.draw.circle(screen, (255, 255, 0), effect["pos"], radius, 2)
