# login_controller.py
import json
import websockets
import settings.context as ct

class LoginError(Exception):
    pass

async def login_to_control(username, password):
    from UI.client import GameClient  # 延遲 import 避免迴圈依賴
    client = GameClient(username, password)
    success = await _login_async(client)
    return client if success else None

async def _login_async(client):
    try:
        async with websockets.connect(ct.CONTROL_SERVER_WS) as ws:
            # 發送登入資訊
            await ws.send(json.dumps({
                "type": "login",
                "username": client.username,
                "password": client.password
            }))

            response = await ws.recv()
            data = json.loads(response)

            if not data.get("success"):
                raise LoginError(data.get("reason", "Unknown error"))

            client.login_success = True
            print(f"[Login] 登入成功，帳號：{client.username}")

            # 取得 Server 清單
            await ws.send(json.dumps({"type": "get_server_list"}))
            response = await ws.recv()
            data = json.loads(response)

            if data.get("type") == "get_server_list_response":
                client.server_list = data.get("server_list", [])
                print(f"[Login] 已取得 {len(client.server_list)} 台 GameServer")
                return True

    except Exception as e:
        print(f"[Login] 發生例外：{e}")
        return False
