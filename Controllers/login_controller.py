# login_controller.py
import json
import websockets
import asyncio
import settings.context as ct


# 自訂錯誤類別：登入失敗會丟出這個錯誤
class LoginError(Exception):
    pass

# 傳入 username/password，嘗試登入
async def login_to_control(username, password):
    from UI.client import GameClient                # 延遲 import 避免迴圈依賴
    loop = asyncio.get_running_loop()
    client = GameClient(username, password, loop)   # 建立 GameClient 實體
    success = await _login_async(client)            # 進行非同步登入請求(連絡後台 : WebSocket )
    return client if success else None              # 回傳 client 或 None

# 實際登入邏輯（與 ControlServer 建立連線）
async def _login_async(client):
    try:
        # 與 ControlServer 建立 WebSocket 連線
        async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
            # 傳送登入資訊：帳號＋密碼
            await ws.send(json.dumps({
                "type": "login",
                "username": client.username,
                "password": client.password
            }))

            # 等待回傳登入結果
            response = await ws.recv()
            data = json.loads(response)

            # 若登入失敗，丟出 LoginError（會被 login_ui 畫面接住
            if not data.get("success"):
                raise LoginError(data.get("reason", "Unknown error"))

            # 登入成功 → 設定狀態
            client.login_success = True
            print(f"[Login] 登入成功，帳號：{client.username}")

            # 傳送請求：取得 GameServer 清單
            await ws.send(json.dumps({"type": "get_server_list"}))
            response = await ws.recv()
            data = json.loads(response)

            # 回傳 GameServer 清單（保存在 client.server_list）
            if data.get("type") == "get_server_list_response":
                client.server_list = data.get("server_list", [])
                print(f"[Login] 已取得 {len(client.server_list)} 台 GameServer")
                return True

    except Exception as e:
         # 捕捉連線錯誤、格式錯誤等例外情況
        print(f"[Login] 發生例外：{e}")
        return False
