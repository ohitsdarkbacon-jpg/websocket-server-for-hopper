import asyncio
import websockets
import json
import requests
import time
import os

# ===== CONFIG =====
PLACE_ID = 109983668079237  # Roblox game ID
REUSE_INTERVAL = 3600       # seconds
PORT = int(os.environ.get("PORT", 10000))  # Render dynamic port

server_queue = []
used_servers = {}  # server_id : timestamp

# ===== FETCH SERVERS =====
async def fetch_servers():
    global server_queue, used_servers
    while True:
        try:
            url = f"https://games.roblox.com/v1/games/{PLACE_ID}/servers/Public?limit=100"
            while url:
                res = requests.get(url).json()
                for s in res.get("data", []):
                    sid = s["id"]
                    if s["playing"] < s["maxPlayers"] and sid not in used_servers:
                        server_queue.append(sid)
                        used_servers[sid] = time.time()
                        print(f"[Queue Added] Server ID: {sid}, Players: {s['playing']}/{s['maxPlayers']}")
                cursor = res.get("nextPageCursor")
                if cursor:
                    url = f"https://games.roblox.com/v1/games/{PLACE_ID}/servers/Public?limit=100&cursor={cursor}"
                else:
                    break

            # Cleanup used servers older than 1hr
            now = time.time()
            for sid, ts in list(used_servers.items()):
                if now - ts >= REUSE_INTERVAL:
                    del used_servers[sid]

            print(f"[Queue] {len(server_queue)} servers | [Used] {len(used_servers)}")

        except Exception as e:
            print("[Fetch Error]", e)
        await asyncio.sleep(5)

# ===== HANDLE CLIENTS =====
async def handler(websocket, path):
    client_id = id(websocket)
    print(f"[WS] New client connected: {client_id}")
    try:
        while True:
            # Send a server from the queue
            if server_queue:
                sid = server_queue.pop(0)
                used_servers[sid] = time.time()
                await websocket.send(json.dumps({"server": sid}))
                print(f"[Sent] Server ID {sid} to client {client_id}")
            else:
                await websocket.send(json.dumps({"server": None}))
            await asyncio.sleep(1)  # push servers every second
    except websockets.exceptions.ConnectionClosed:
        print(f"[WS] Client disconnected: {client_id}")

# ===== MAIN =====
async def main():
    # Start server fetch loop
    asyncio.create_task(fetch_servers())
    # Start WebSocket server
    async with websockets.serve(handler, "0.0.0.0", PORT):
        print(f"[Server] Running on port {PORT}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
