# mole_thread.py    :   gm_server 控制地鼠邏輯
import threading
import asyncio
import time
import random
import settings.context as ct
from settings.game_settings import MOLE_TYPES
from GameServer.broadcaster import broadcast

# 地鼠產生執行緒
def mole_sender_thread():
    print("[MoleThread] 啟動地鼠 sender thread")
    while True:
        if ct.game_phase == "playing":
            ct.current_mole_id += 1

            mole = random.choice(MOLE_TYPES)    

            score = mole["score"]
            if mole["name"] == "Joker Mole" and "score_range" in mole:
                score = random.randint(*mole["score_range"])

            ct.current_mole = {
                "mole_id": ct.current_mole_id,              # 唯一值
                "position": random.randint(0, 11),          # 隨機位置
                "mole_type": mole["name"],                  # 類型
                "score": score,                             # 分數
                "color": mole["color"],                     # 顏色（若前端有用）
                "active": True,                             # 是否有效
                "spawn_time": time.time(),                  # 出現時間
                "duration": 1.8                             # 存活時間（可自訂）
            }

            # 廣播給所有玩家
            try:
                asyncio.run(broadcast({"event": "mole_update", "mole": ct.current_mole}))
                print(f"[MoleThread] 廣播地鼠：{ct.current_mole}")
            except RuntimeError as e:
                print(f"[MoleThread] 廣播失敗：{e}")

            time.sleep(1.5)  # 控制出現頻率
        else:
            time.sleep(0.2)  # 非 playing 階段稍作休息
