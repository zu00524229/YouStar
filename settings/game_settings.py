# game_settings.py 管理遊戲前端變數
import pygame as pg

pg.init()



# 顏色
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 200, 0)
YELLOW = (255, 209, 5)
HOVAR = (158, 79, 0)

# 視窗設定
WIDTH = 840
HEIGHT = 640

# 字型
CH_FONT_PATH = "assets/fonts/NotoSansTC-VariableFont_wght.ttf"
CH_FONT_SIZE = pg.font.Font(CH_FONT_PATH, 28)

# 字型大小

FONT_SIZE = pg.font.SysFont(None, 48)
SMALL_FONT_SIZE = pg.font.SysFont(None, 28)
BIG_FONT_SIZE = pg.font.SysFont(None, 96)
RANK_FONT_SIZE = pg.font.SysFont(None, 24)

# 設定 4x3 格子位置
CELL_SIZE = 160
OFFSET_X = (WIDTH - (CELL_SIZE * 4)) // 2
OFFSET_Y = (HEIGHT - (CELL_SIZE * 3)) // 2 + 30

score_popups = []   # 儲存及時分數，左下飛字提示

# 地鼠格子
GRID_POSITIONS = [
    (OFFSET_X + col * CELL_SIZE + CELL_SIZE // 2,
     OFFSET_Y + row * CELL_SIZE + CELL_SIZE // 2)
    for row in range(3) for col in range(4)
]

# 地鼠種類
MOLE_TYPES = [
    {"name": "Mole", "color": (200, 100, 100), "score": +3},                    # 普通地鼠
    {"name": "Gold Mole", "color": 	(255, 245, 180), "score": +8},                 # 黃金地鼠
    {"name": "Bomb Mole", "color": (92, 92, 92), "score": -5},                  # 炸彈地鼠
    {"name": "Diamond Mole", "color": (0, 255, 255), "score": +15},             # 特殊地鼠
    {"name": "Joker Mole", "color": (158, 79, 0), "score": 0, "score_range": (-15, 15)},   # 小丑地鼠
]

# 特殊地鼠
SPMOLE_TYPES = [{"name": "Diamond Mole", "color": (0, 255, 255), "score": +15}]   # 特殊地鼠



# --- 登入畫面相關設定 ---
LOGIN_BOX_WIDTH = 200
LOGIN_BOX_HEIGHT = 30
LOGIN_GAP = 15

LOGIN_BUTTON_COLOR = (50, 150, 250)
ERROR_RED = (255, 80, 80)
LOGIN_BLUE = (180, 200, 255)

# 登入框位置微調（置中偏移）
center_x_offset = 40  # 你可以調整這個值讓框更居中

# --- 按鈕 ---
ready_button = pg.Rect(400, 400, 200, 60)
