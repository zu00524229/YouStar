
import settings.game_settings as gs
# 當前觀戰人數
def watching_count(surface, watching_players, is_watching, available_servers, blink):
    # 畫出觀戰人數(左下角)
    watch_surface = gs.SMALL_FONT_SIZE.render(f"Viewers: {watching_players}", True, (180, 200, 220))  
    watch_rect = watch_surface.get_rect(bottomleft=(20, gs.HEIGHT - 20))  # 左下角
    surface.blit(watch_surface, watch_rect)

    # 如果是觀戰者，再顯示提示
    if is_watching:  #  確保你有這個判斷屬性
        # print("[watching_count] 目前是觀戰者 → 顯示『觀戰中...』提示")
        watching_tip = gs.CH_MC_FONT_SMALL.render("觀戰中...", True, (gs.ORANGE))
        tip_rect = watching_tip.get_rect(bottomleft=(watch_rect.right + 10, gs.HEIGHT - 20))  # 接在右邊
        surface.blit(watching_tip, tip_rect)


        # 檢查所有 available_servers 狀態
        for server in available_servers:
            # print(f"[Debug] server={server['server_url']} | players={server['current_players']} / {server['max_players']}")
            print(server)


        # 判斷是否有可加入伺服器
        # has_available_slot = any(
        #     server['current_players'] < server['max_players'] and server['game_phase'] in ['waiting', 'loading']
        #     for server in available_servers
        # )
        # print(f"[Debug] has_available_slot = {has_available_slot} | blink = {blink}")



        # 如果有其他伺服器有空位，再加提示（閃爍）
        available_rooms = []
        for i, server in enumerate(available_servers):
            if server['current_players'] < server['max_players'] and server['game_phase'] in ['waiting', 'loading']:
                room_name = f"GameServer {i + 1}"
                available_rooms.append(room_name)

         # 顯示可加入房間（如有）
        if available_rooms:
            joined_list = " / ".join(available_rooms)
            hint_text = f"房間可加入：{joined_list}"
            hint_surface = gs.CH_MC_FONT_SMALL.render(hint_text, True, gs.ORANGE)
            hint_rect = hint_surface.get_rect(bottomleft=(tip_rect.right + 10, gs.HEIGHT - 20))
            surface.blit(hint_surface, hint_rect)

        else:
            # 顯示灰色提示（無可加入）
            no_room_tip = gs.CH_MC_FONT_SMALL.render("目前無房間可加入", True, (120, 120, 120))
            no_room_rect = no_room_tip.get_rect(bottomleft=(tip_rect.right + 10, gs.HEIGHT - 20))
            surface.blit(no_room_tip, no_room_rect)

    else:
        # 非觀戰者，顯示深灰色提示
        not_watch_tip = gs.CH_MC_FONT_SMALL.render("非觀戰中", True, (100, 100, 100))
        not_watch_rect = not_watch_tip.get_rect(bottomleft=(watch_rect.right + 10, gs.HEIGHT - 20))
        surface.blit(not_watch_tip, not_watch_rect)