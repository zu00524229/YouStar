# context.py        :   gm_server.py 的變數管理
import asyncio
# 配置
CONTROL_SERVER_WS = "ws://127.0.0.1:8765"
print("[context] 成功載入 context.py，CONTROL_SERVER_WS =", CONTROL_SERVER_WS)
MY_GAME_SERVER_WS = "ws://127.0.0.1:8001/ws"

# GameServer 狀態
phase_changed_event = asyncio.Event()    # 等待進入 playing → mole_sender 才啟動
connected_players = set()                # 目前在線玩家 username 集合
leaderboard = {}                         # 玩家最高分字典 {username: score}
current_scores = {}                      # 玩家當前當局分數

# 遊戲計時
loading_time = 10                        # loading 倒數秒數
loading_start_time = None          

ready_offer_active = False              # 檢查 是否正在提供 ready 選項給玩家
ready_offer_start_time = None           # 用來計算ready倒數時間
# ready_offer_duration = 10               # 提供ready時間
ready_players = set()                   # 當集合人數達標，啟動下一局
observer_players = set()                 # 用來標記這些玩家不會餐與下一輪

GAME_DURATION = 60                       # 遊戲時間 60s
game_start_time = None
gameover_start_time = None


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

# 遊戲階段控制
game_phase = "waiting"                   # 遊戲狀態機: waiting / loading / playing / gameover / post_gameover
player_websockets = {}                   # {username: websocket} → 廣播/單發使用
skip_next_status_update = False          # 避免 post_gameover 時多發一次 status_update (waiting)
post_gameover_cooldown = False           # 是否剛結束過一場 → 防止立即進 loading
no_player_since = None   # 記錄 playing 中，何時開始沒玩家 → 自動回 waiting

