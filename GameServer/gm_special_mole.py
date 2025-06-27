# gm_special_mole    :   gm_server 控制地鼠邏輯

import random
import asyncio
import time
import settings.context as ct
import settings.game_settings as gs
from GameServer.broadcaster import broadcast

# === 特殊地鼠產生器 ===
def special_mole_sender_thread():
    while True:
        # print("[GameServer] special_mole_sender 等待 phase_changed_event（僅在 playing 啟動）")
        # ct.phase_changed_event.wait()

        if ct.game_phase != "playing":
            ct.phase_changed_event.clear()
            continue

        print("[GameServer] special_mole_sender 進入 playing loop!")
        while ct.game_phase == "playing":
            sleep_time = random.uniform(5.0, 8.0)
            # asyncio.sleep(sleep_time)

            if ct.game_phase != "playing":
                break

            # 避開目前的「一般地鼠」位置
            ct.current_special_mole["active"] = False
            ct.current_special_mole_id += 1

            all_positions = set(range(12))
            occupied_position = {ct.current_mole["position"]}
            available_positions = list(all_positions - occupied_position)

            if not available_positions:
                print("[GameServer] 沒有可用位置放特殊地鼠，跳過這輪")
                continue
            
            mole_data = gs.SPMOLE_TYPES[0]

            ct.current_special_mole = {
                "mole_id": ct.current_special_mole_id,
                "position": random.choice(available_positions),
                "mole_type": mole_data["name"],
                "score": mole_data["score"],
                "color": mole_data["color"],
                "spawn_time": time.time(),
                "duration": 3.0,
                "active": True
            }

            print(f"[GameServer] 發送 Special Mole ID {ct.current_special_mole_id} at pos {ct.current_special_mole['position']}")
            print(f"[Debug] 特殊地鼠位置: {ct.current_special_mole['position']} | 一般地鼠位置: {ct.current_mole['position']}")

            broadcast({
                "event": "special_mole_update",
                "mole": ct.current_special_mole
            })

