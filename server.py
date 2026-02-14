'''
---------------------------------
Server For Socket Programming
---------------------------------
__updated__ = '2025-10-18'
Author: Luke Vrbanac
Email: lwvrbanac@gmail.com
---------------------------------
'''
"""
- Uses Path.cwd() instead of __file__ for directories
- Same protocol: NAME, status, list, get <file>, exit
- Max 3 clients
"""

import socket
import threading
from datetime import datetime
from pathlib import Path

HOST = "0.0.0.0"
PORT = 37200            # change if "address in use"
MAX_CLIENTS = 3
BUFF = 4096

# Repo folder for downloadable files (relative to current working dir)
BASE_DIR = Path.cwd()
REPO_DIR = BASE_DIR / "server_repo"
REPO_DIR = Path.cwd() / "server_repo"
REPO_DIR.mkdir(parents=True, exist_ok=True)

# ---- Shared state (protected by locks) ----
client_counter_lock = threading.Lock()
client_counter = 0  # used to assign Client01, Client02, ...

cache_lock = threading.Lock()
# cache[name] = {
#   "addr": ("ip", port),
#   "connected_at": datetime,
#   "finished_at": datetime | None
# }
cache = {}


def ensure_repo():
    REPO_DIR.mkdir(parents=True, exist_ok=True)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def assign_client_name():
    global client_counter
    with client_counter_lock:
        client_counter += 1
        return f"Client{client_counter:02d}"


def safe_sendline(conn, line: str):
    try:
        conn.sendall((line + "\n").encode("utf-8", errors="replace"))
    except Exception:
        # If sending fails (client dropped), let handler unwind.
        pass


def recvline(conn):
    """
    Read a single line (ending with '\n') from the socket.
    Returns None on disconnect or error.
    """
    data = bytearray()
    try:
        while True:
            chunk = conn.recv(1)
            if not chunk:
                return None
            data += chunk
            if chunk == b"\n":
                break
    except Exception:
        return None
    return data.decode("utf-8", errors="replace").rstrip("\r\n")


def list_repo_files():
    ensure_repo()
    files = [p.name for p in REPO_DIR.iterdir() if p.is_file()]
    files.sort()
    return files


def _safe_join_repo(filename: str) -> Path:
    """
    Prevent path traversal: ensure requested file stays under REPO_DIR.
    """
    candidate = (REPO_DIR / filename).resolve()
    repo_root = REPO_DIR.resolve()
    if repo_root in candidate.parents or candidate == repo_root / candidate.name:
        return candidate
    # Fallback to a non-existent path under repo to trigger "not found"
    return repo_root / "__INVALID__"


def handle_get(conn, filename):
    path = _safe_join_repo(filename)
    if not path.is_file():
        safe_sendline(conn, "ERROR File not found")
        return
    size = path.stat().st_size
    safe_sendline(conn, f"FILESIZE {size}")
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(BUFF)
                if not chunk:
                    break
                conn.sendall(chunk)
        # Optional terminator (client treats it as optional)
        safe_sendline(conn, "FILEEND")
    except Exception:
        # If the client disconnects mid-transfer, just stop.
        pass


def render_status():
    with cache_lock:
        if not cache:
            return "No clients connected yet."
        lines = []
        header = f"{'Name':<10} {'IP:Port':<22} {'Connected At':<20} {'Finished At':<20}"
        lines.append(header)
        lines.append("-" * len(header))
        for name, info in cache.items():
            ip_port = f"{info['addr'][0]}:{info['addr'][1]}"
            connected = info['connected_at'].strftime("%Y-%m-%d %H:%M:%S")
            finished = info['finished_at'].strftime("%Y-%m-%d %H:%M:%S") if info['finished_at'] else "-"
            lines.append(f"{name:<10} {ip_port:<22} {connected:<20} {finished:<20}")
        return "\n".join(lines)


def client_thread(conn, addr):
    name = assign_client_name()

    # Register in cache
    with cache_lock:
        cache[name] = {
            "addr": addr,
            "connected_at": datetime.now(),
            "finished_at": None,
        }

    try:
        # Send assigned name to client, expect echo back
        safe_sendline(conn, f"NAME {name}")
        line = recvline(conn)
        if line is None or not line.startswith("NAME "):
            safe_sendline(conn, "ERROR Expected: NAME <your_name>")
            return

        while True:
            line = recvline(conn)
            if line is None:
                break
            cmd = line.strip()
            if not cmd:
                continue

            low = cmd.lower()

            if low == "exit":
                safe_sendline(conn, "BYE")
                break

            elif low == "list":
                files = list_repo_files()
                if files:
                    safe_sendline(conn, "FILES " + " | ".join(files))
                else:
                    safe_sendline(conn, "FILES <empty>")

            elif low.startswith("get "):
                _, _, filename = cmd.partition(" ")
                filename = filename.strip()
                if not filename:
                    safe_sendline(conn, "ERROR Usage: get <filename>")
                else:
                    handle_get(conn, filename)

            elif low == "status":
                report = render_status()
                safe_sendline(conn, "STATUS-BEGIN")
                for l in report.splitlines():
                    safe_sendline(conn, l)
                safe_sendline(conn, "STATUS-END")

            else:
                # Echo with ACK
                safe_sendline(conn, f"{cmd} ACK")

    finally:
        # Mark finished in cache
        with cache_lock:
            if name in cache and cache[name]["finished_at"] is None:
                cache[name]["finished_at"] = datetime.now()
        try:
            conn.close()
        except Exception:
            pass


def main():
    print(f"[{now_str()}] Server starting on {HOST}:{PORT} (max {MAX_CLIENTS} clients).", flush=True)
    ensure_repo()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()

        while True:
            conn, addr = s.accept()
            # Enforce capacity before spinning a thread
            with cache_lock:
                current = sum(1 for info in cache.values() if info["finished_at"] is None)
            if current >= MAX_CLIENTS:
                try:
                    safe_sendline(conn, f"BUSY Server is at capacity ({MAX_CLIENTS}). Try again later.")
                finally:
                    conn.close()
                continue

            t = threading.Thread(target=client_thread, args=(conn, addr), daemon=True)
            t.start()


if __name__ == "__main__":
    main()
