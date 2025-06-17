╔══════════════════╗
║   Client (玩家)   ║
╚══════════════════╝
      │
      │ login
      │
      ▼
╔══════════════════╗
║ Control Server   ║
║   (中控伺服器)    ║
╚══════════════════╝
  │              │
  │ heartbeat    │
  │ status_update│
  ▼              ▼
╔══════════════════╗
║ GameServer 台    ║
╚══════════════════╝

遊戲流程（GameServer內部）：

┌────────────┐
│ game_phase │ ←─── Waiting ←── Post_gameover
└────────────┘
      │ 有玩家進入
      ▼
┌────────────┐
│ Loading    │（倒數10秒）
└────────────┘
      │ 倒數完
      ▼
┌────────────┐
│ Playing    │（60秒，發地鼠、接hit）
└────────────┘
      │ 時間到 or 無人在線
      ▼
┌────────────┐
│ Gameover   │（廣播Leaderboard）
└────────────┘
      │ 等2秒
      ▼
┌────────────┐
│ Post_gameover│ → 回 Waiting
└────────────┘

---

Client → 進入後流程：

1️⃣ login → Control Server → 分配 GameServer URL
2️⃣ 連 GameServer → 發 username
3️⃣ 收 status_update → 畫不同畫面 (waiting / loading / playing / gameover)
4️⃣ playing：
    - 收 mole_update → 畫地鼠
    - 點擊地鼠 → send hit:mole_id:score
5️⃣ gameover → 收 leaderboard_update → 主動送 offline → 回 Waiting

---

**變數備註**：

### Control Server
- gameserver_status → 中控記住目前哪些 GameServer 正常
- player_online_status → 哪些玩家現在在哪個 GameServer

Client → WebSocket → handle_client →
    ├── type = register_gameserver → 註冊 + loop 收 status_update/ping
    ├── type = login → 檢查帳密 + 配 GameServer
    ├── type = offline → 扣人 + 移除 player_online_status
    ├── type = get_leaderboard → 查排行榜

同時背景 → heartbeat_checker：
    → 每 3 秒掃 → 判定 GameServer 是否掉線


中控就像一個 遊戲大廳櫃檯，

有新遊戲機來報到 → 記錄在冊

有玩家來登記 → 分配進房

有玩家離開 → 幫他退房

有人查排行榜 → 回 leaderboard

同時背景會掃 → 哪些遊戲機掛了，不再派人進去


### GameServer
- game_phase → 目前遊戲流程階段
- connected_players → 哪些玩家在線
- current_scores → 目前這局的分數
- leaderboard → 歷史最高分
- current_mole → 現在發出來的地鼠資訊
- phase_changed_event → 通知 mole_sender 可以開始發地鼠

GameServer 啟動
│
├─ register_to_control() → 連 ControlServer 註冊自己
│                          → 開 run_status_loop(ws)
│
├─ 啟動 mole_sender() → 等 phase_changed_event 通知
│
└─ 等待玩家連線 (player_handler)


👉 GameServer 是一台 自走的遊戲機：

有玩家進入 → 自動進 loading / playing / gameover

playing → 會自動發地鼠，收到 hit 更新分數

結束 → 廣播排行榜

中控 & 玩家每秒收到狀態同步 (status_update + ping)


### Client
- assigned_server → 被配到哪台 GameServer
- ws_conn → 跟 GameServer websocket 連線
- game_state → 自己目前畫面狀態
- current_mole_id / position / type / active → 當前地鼠資料
- score → 自己目前分數
- leaderboard_data → 最新排行榜資料

---

時間線理解

Client 啟動 login_to_control
  ↓
ControlServer 回 assigned_server
  ↓
Client 連 GameServer WebSocket
  ↓
ws_receiver_async 啟動

【進入 loop → 不斷收 GameServer 訊息】

GameServer 發 status_update → 更新 game_state / loading_time / remaining_time / leaderboard → 更新畫面
GameServer 發 mole_update → 更新地鼠資料 → 畫地鼠
GameServer 發 leaderboard_update → 更新 leaderboard_data → gameover 畫面 + 主動 offline

【使用者打地鼠 → 發 hit:mole_id:score】


大概Client 流程

Client 是一個「畫面同步器」+「打地鼠控制器」：

同步器 → 不斷收 GameServer 的 status_update / mole_update / leaderboard_update → 改變自己 game_state → 畫畫面

控制器 → 玩家打地鼠時 → 發 hit:mole_id:score 給 GameServer



👉 **一圖概念**就是：

