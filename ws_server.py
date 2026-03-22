import os
import asyncio
import websockets
import requests
import json
import time

PLACE_ID = 123456789  # 🔴 Put your Roblox game ID here

# ✅ Dynamic port for Render / fallback for local testing
PORT = int(os.environ.get("PORT", 10000))

server_queue = []
used_servers = {}  # server_id : timestamp when used
lock = asyncio.Lock()  # ensures atomic access

REUSE_INTERVAL = 3600  # seconds → 1 hour

# 🔁 Fetch servers continuously
async def fetch_servers():
    global server_queue, used_servers

    while True:
        try:
            url = f"https://games.roblox.com/v1/games/{PLACE_ID}/servers/Public?limit=100"

            while url:
                res = requests.get(url).json()

                async with lock:
                    for s in res.get("data", []):
                        if s["playing"] < s["maxPlayers"]:
                            sid = s["id"]
                            # only add if not currently used
                            if sid not in used_servers:
                                server_queue.append(sid)
                                used_servers[sid] = time.time()

                cursor = res.get("nextPageCursor")
                if cursor:
                    url = f"https://games.roblox.com/v1/games/{PLACE_ID}/servers/Public?limit=100&cursor={cursor}"
                else:
                    break

            # 🔄 Clean up used_servers older than 1hr
            async with lock:
                now = time.time()
                for sid, ts in list(used_servers.items()):
                    if now - ts >= REUSE_INTERVAL:
                        del used_servers[sid]

            print(f"[Queue size]: {len(server_queue)} | Used servers: {len(used_servers)}")

        except Exception as e:
            print("Fetch error:", e)

        await asyncio.sleep(5)

# 🔌 Handle client connections
async def handler(websocket):
    print("Client connected")
    try:
        while True:
            async with lock:
                if len(server_queue) > 0:
                    server = server_queue.pop(0)
                    used_servers[server] = time.time()
                else:
                    server = None

            await websocket.send(json.dumps({"server": server}))
            await asyncio.sleep(1)

    except:
        print("Client disconnected")

# 🚀 Main entry
async def main():
    asyncio.create_task(fetch_servers())

    async with websockets.serve(handler, "0.0.0.0", PORT):
        print(f"WebSocket server running on port {PORT}...")
        await asyncio.Future()  # run forever

# ✅ Fix for Render / event loop issues
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(main())
