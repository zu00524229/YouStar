# gm_mole.py    :   gm_server 控制地鼠邏輯

import random
import asyncio
# import json
import time
# import websockets
import settings.context as ct
from GameServer.broadcaster import broadcast


# 一般地鼠
async def mole_sender():
    while True:
        print("[GameServer] mole_sender 等待 phase_changed_event (playing)")
        await ct.phase_changed_event.wait()
        print("[GameServer] mole_sender 收到 phase_changed_event → 檢查 game_phase =", ct.game_phase)

        if ct.game_phase == "playing":
            ct.phase_changed_event.clear()
            print("[GameServer] mole_sender 進入 playing loop!")

            while ct.game_phase == "playing":
                # 生成新地鼠
                ct.current_mole_id += 1
                ct.current_mole = {
                    "mole_id": ct.current_mole_id,
                    "position": random.randint(0, 11),
                    "mole_type": random.choice(["Mole", "Gold Mole", "Bomb Mole", "Joker Mole"]),                    
                    "active": True
                }

                await broadcast({
                    "event": "mole_update",
                    "mole": ct.current_mole
                })


                sleep_time = random.uniform(0.6, 1.5)
                start_sleep = time.time()
                while time.time() - start_sleep < sleep_time:
                    if ct.game_phase != "playing":
                        print("[GameServer] mole_sender 偵測到離開 playing, break inner loop")
                        break
                    await asyncio.sleep(0.05)

# 特殊地鼠
async def special_mole_sender():
    while True:
        await ct.phase_changed_event.wait()
        print("[GameServer] special_mole_sender 收到 phase_changed_event → 檢查 game_phase =", ct.game_phase)

        if ct.game_phase == "playing":
            print("[GameServer] special_mole_sender 進入 playing loop!")

            while ct.game_phase == "playing":
                sleep_time = random.uniform(5.0, 10.0)
                await asyncio.sleep(sleep_time)

                if ct.game_phase != "playing":
                    break

                ct.current_special_mole_id += 1

                all_positions = set(range(12))
                occupied_position = {ct.current_mole["position"]}
                available_positions = list(all_positions - occupied_position)

                if not available_positions:
                    print("[GameServer] 沒有可用位置放特殊地鼠，跳過這輪")
                    continue

                ct.current_special_mole = {
                    "mole_id": ct.current_special_mole_id,
                    "position": random.choice(available_positions),
                    "mole_type": "Diamond Mole",
                    "active": True
                }

                await broadcast({
                    "event": "special_mole_update",
                    "mole": ct.current_special_mole
                })



                print(f"[GameServer] 發送 Special Mole ID {ct.current_special_mole_id} at pos {ct.current_special_mole['position']}")

