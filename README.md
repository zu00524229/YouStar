## 多人打地鼠系統總結報告

### 本次專案印象最深刻的收穫

本次專案最深的印象來自於解決「打地鼠延遲」與「事件重複觸發」問題：

- 發現 `time.sleep()` 阻塞導致畫面與 WebSocket 無法同步，轉為使用 `asyncio.sleep()` 配合 `async def` 的方式改善卡頓與延遲。
- 釐清 `async` 與 `threading` 的分工與協作，懂得如何執行緒中觸發 `asyncio.run_coroutine_threadsafe` 來達成非同步通訊。
- 最後發現 `event.pos` 在主迴圈與事件處理中被多次讀取與處理，導致點擊事件重複觸發，透過條件判斷與結構優化後徹底解決。


---

### 系統架構核心總覽

#### ☁ Control Server（中控伺服器）

- 管理所有 GameServer 狀態與心跳
- 記錄玩家登入資訊與在線狀態（player_online_status）
- 分配 GameServer URL 給 Client
- 提供排行榜查詢與離線管理


#### GameServer（遊戲主機）

- 獨立處理每一局地鼠遊戲邏輯：`waiting → loading → playing → gameover → post_gameover`
- 發送 status_update / mole_update / leaderboard_update 給所有玩家
- 接收打擊與最終分數，更新 current_scores 與 leaderboard
- 檢查是否無人在線、倒數完成等條件，自動切換階段

#### Client（玩家端）

- 登入後接收 ControlServer 分配 GameServer
- 建立與 GameServer WebSocket 連線並啟動接收循環（ws_receiver）
- 根據 `game_state` 轉換畫面（waiting, loading, playing, gameover）
- 收到地鼠出現資訊後繪圖，點擊後發送 `hit:mole_id:score`
- 顯示即時分數與排行榜畫面
- 加強 WebSocket 自動重連機制：使用 ws_receiver_with_reconnect() 補強非同步錯誤與斷線保護，確保前端不會因短暫連線失敗而整體當機。
---

### 已實現的核心功能

- 多人登入系統：帳號密碼登入，中控分配 GameServer
- 遊戲大廳功能：顯示 GameServer 列表，選擇進入
- 遊戲流程自動切換：waiting → loading（倒數）→ playing（打地鼠）→ gameover（排行榜）
- 多人分數同步：地鼠同步出現，分數互不搶奪（同時打擊可分別得分）
- 地鼠類型擴充（一般與特殊地鼠）與隨機位置避開
- 重連保護：Client 自動偵測 WebSocket 斷線與狀態異常
- 殭屍連線檢查：GameServer 定期檢查已斷線玩家並清理

---

### 尚未實現 / 待補功能

- Again 邀請機制：由發起者廣播，讓其他玩家選擇是否加入下一局
- 觀戰者自動加入：Replay 時，觀戰者可以加入下一輪而非留在觀戰狀態
- 重複登入保護：同帳號若重複登入，需通知前一個登入實例並強制離線或提示
- 多 GameServer 登入保護：若同一帳號試圖進入不同 GameServer，需由中控協調轉移通知
- 資料傳輸加密機制：目前為 WebSocket 明文傳輸，未來可考慮 TLS 或自訂加密封裝

---

### 補充

- 使用 `phase_changed_event` 精準控制地鼠生成時機
- 統一廣播模組 `broadcaster.py`，提高可維護性
- `context.py` 作為單一遊戲狀態管理中心，避免跨模組變數混亂

---
