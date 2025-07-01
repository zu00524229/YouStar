# context.py        :   gm_server.py 的變數管理
import asyncio
import json
import os
import sys
# print("[context] 成功載入 context.py，CONTROL_SERVER_WS =", CONTROL_SERVER_WS)

loop = None  # 這行只是空變數，無任何影響
shared_client = None
ws_receiver_start_count = 0 # 檢查殭屍連線
control_ws = None  #  用於廣播破紀錄線

# 配置
CONTROL_SERVER_WS = "ws://127.0.0.1:8765"

# ========== 多開 GameServer 支援 ==========
DEFAULT_BASE_PORT = 8000  # 基礎埠號
try:
    port_offset = int(sys.argv[1])
except (IndexError, ValueError):
    port_offset = 0  # 預設為 0

MY_PORT = DEFAULT_BASE_PORT + port_offset
MY_GAME_SERVER_WS = f"ws://127.0.0.1:{MY_PORT}/ws"

# GameServer 狀態
phase_changed_event = asyncio.Event()    # 等待進入 playing → mole_sender 才啟動
connected_players = set()                # 目前在線玩家 username 集合

LEADERBOARD_FILE = "leaderboard.json"    # 玩家歷史高分 {username: score}
leaderboard = {}                         # 玩家分數字典 {username: score}
current_scores = {}                      # 玩家當前當局分數
watch_players = set()                    # 觀戰玩家 集合

again_active = False         # 是否正在 replay 倒數中
again_start_time = None      # 倒數起始時間（可選）

# 遊戲計時
loading_time = 10                        # loading 倒數秒數
loading_start_time = None          

ready_offer_active = False              # 檢查 是否正在提供 ready 選項給玩家
ready_players = set()                   # 當集合人數達標，啟動下一局
observer_players = set()                 # 用來標記這些玩家不會餐與下一輪

# replay 簡易版用
replay_offer_active = False
replay_start_time = 0


GAME_DURATION = 60                       # 遊戲時間 60s
MOLE_SPAWN_INTERVAL = 1.5                # 地鼠出現頻率（秒）
MOLE_SPAWN_INTERVAL_RANGE = (0.8, 1.5)   # 地鼠隨機秒數
game_start_time = None                  
gameover_start_time = None
click_effects = []                      # 滑鼠動畫


# 遊戲階段控制
game_phase = "waiting"                   # 遊戲狀態機: waiting / loading / playing / gameover / post_gameover
player_websockets = {}                   # {username: websocket} → 廣播/單發使用
skip_next_status_update = False          # 避免 post_gameover 時多發一次 status_update (waiting)
post_gameover_cooldown = False           # 是否剛結束過一場 → 防止立即進 loading
no_player_since = None                  # 記錄 playing 中，何時開始沒玩家 → 自動回 waiting


# 當前地鼠資訊
current_mole_id = 0                     # 唯一值
current_mole = {
    "mole_id": 0,
    "position": -1,
    "mole_type": "",
    "active": False
}

# 特殊地鼠邏輯
current_special_mole_id = 0
current_special_mole = {
    "mole_id": 0,
    "position": -1,
    "mole_type": "",
    "active": False
}


def save_leaderboard():
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(leaderboard, f)
    print("[context] leaderboard 已儲存至檔案")

def load_leaderboard():
    global leaderboard
    if os.path.exists(LEADERBOARD_FILE):
        with open(LEADERBOARD_FILE, "r") as f:
            leaderboard = json.load(f)
        print("[context] leaderboard 已從檔案載入")
    else:
        leaderboard = {}
        print("[context] 沒有找到 leaderboard 檔案，初始化為空字典")
