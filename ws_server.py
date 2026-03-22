# ws_server.py
from websocket_server import WebsocketServer
import requests
import json
import threading
import time
import os

# ===== CONFIG =====
PLACE_ID = 109983668079237  # 🔴 Put your Roblox game ID here

# Render dynamic port or default for local
PORT = int(os.environ.get("PORT", 10000))

# 1-hour reuse interval for servers
REUSE_INTERVAL = 3600

# Queue and used servers
server_queue = []
used_servers = {}  # server_id : timestamp

lock = threading.Lock()


# ===== FETCH SERVERS =====
def fetch_servers():
    global server_queue, used_servers
    while True:
        try:
            url = f"https://games.roblox.com/v1/games/{PLACE_ID}/servers/Public?limit=100"
            while url:
                res = requests.get(url).json()
                with lock:
                    for s in res.get("data", []):
                        sid = s["id"]
                        # Only add if not used in the last 1 hour
                        if s["playing"] < s["maxPlayers"] and sid not in used_servers:
                            server_queue.append(sid)
                            used_servers[sid] = time.time()
                cursor = res.get("nextPageCursor")
                if cursor:
                    url = f"https://games.roblox.com/v1/games/{PLACE_ID}/servers/Public?limit=100&cursor={cursor}"
                else:
                    break

            # Cleanup used_servers older than 1 hour
            now = time.time()
            with lock:
                for sid, ts in list(used_servers.items()):
                    if now - ts >= REUSE_INTERVAL:
                        del used_servers[sid]

            print(f"[Queue] {len(server_queue)} servers | [Used] {len(used_servers)}")
        except Exception as e:
            print("[Fetch Error]", e)

        time.sleep(5)  # wait 5 seconds before next fetch


# ===== WEBSOCKET HANDLERS =====
def new_client(client, server):
    print(f"[WS] New client connected: {client['id']}")


def client_left(client, server):
    print(f"[WS] Client disconnected: {client['id']}")


def send_server_to_client(client, server):
    global server_queue, used_servers
    with lock:
        if server_queue:
            sid = server_queue.pop(0)
            used_servers[sid] = time.time()
        else:
            sid = None
    server.send_message(client, json.dumps({"server": sid}))


# ===== SERVER LOOP =====
def tick(server):
    while True:
        for c in server.clients:
            send_server_to_client(c, server)
        time.sleep(1)  # push every 1 second


# ===== RUN SERVER =====
def run_server():
    ws_server = WebsocketServer(port=PORT, host='0.0.0.0')
    ws_server.set_fn_new_client(new_client)
    ws_server.set_fn_client_left(client_left)

    # Start server tick in background thread
    threading.Thread(target=tick, args=(ws_server,), daemon=True).start()
    ws_server.run_forever()


# ===== START EVERYTHING =====
if __name__ == "__main__":
    # Start server fetching thread
    threading.Thread(target=fetch_servers, daemon=True).start()
    print(f"[Server] Roblox-compatible WS server running on port {PORT}")
    run_server()
