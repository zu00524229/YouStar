 let ws;
        // 當按下connect 按鈕時會呼叫此函數
        function connect() {
            // 建立 WebScoket 連線，目標是GameServer 的 ws://localhost:8001/ws
            ws = new WebSocket("ws://localhost:8001/ws");

            // 當連線成功，onopen 事件會被觸發
            ws.onopen = () => {
                console.log("連線成功");     // 輸出
                ws.send("player1");         // 傳送玩家的username 給 GameServer
            };

            // 當 GameServer 傳回訊息時，onmessage 事件會被觸發
            ws.onmessage = (msg) => {
                // 將收到的訊息內容 (msg.data) 顯示在 Console 裡
                console.log("收到 Server 訊息:", msg.data);
                document.getElementById("log").innerHTML += `<div>${msg.data}</div>`;
            };

            // 連線關閉(玩家斷線/手動關閉/網路中斷)
            ws.onclose = () => {
                console.log("斷線了！");
            };
        }

        function sendMsg() {
            // 檢查目前 ws 是否存在，且處於 OPEN 狀態
            if (ws && ws.readyState === WebSocket.OPEN) {
                // 傳送 "打地鼠！" 這個訊息給 GameServer
                // GameServer 收到後可以印出，或進行遊戲處理邏輯
                ws.send("打地鼠！");
                console.log("送出 打地鼠!")
            }
        }

        function disconnect() {
            if (ws) {
                // 關閉 WebSocket 連線，會觸發 ws.onclose()
                ws.close();
            }
        }
